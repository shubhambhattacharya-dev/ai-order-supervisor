import os

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import CreateRunRequest, InjectEventRequest, InstructionRequest, SupervisorConfig
from temporal import get_client, workflow_id

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = FastAPI(title="AI Order Supervisor API", version="0.2.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TASK_QUEUE = "supervisor-task-queue"

DEFAULT_INSTRUCTION = (
    "You are supervising one e-commerce order end to end. "
    "Proactively notify the right team on delays, keep the customer informed, "
    "sleep between checks, and escalate anything ambiguous."
)

def _workflow_error(exc: Exception) -> HTTPException:
    """Return an actionable status for Temporal workflow operations."""
    detail = str(exc)
    if "already completed" in detail.lower():
        return HTTPException(
            status_code=409,
            detail="This run has already completed or been cancelled and cannot accept changes.",
        )
    if "failed state" in detail.lower() or "not ready" in detail.lower():
        return HTTPException(
            status_code=503,
            detail="This workflow is recovering from a failed task. Try again after restarting the worker.",
        )
    if "not found" in detail.lower():
        return HTTPException(status_code=404, detail="The requested workflow was not found.")
    return HTTPException(status_code=502, detail="The workflow service could not complete this request.")


def _db() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DB", "order_supervisor"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


# ------------------------------------------------------------- supervisors -
@app.get("/supervisors")
async def list_supervisors():
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS supervisor_configs (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    base_instruction TEXT NOT NULL,
                    allowed_actions TEXT[] NOT NULL DEFAULT '{}',
                    default_wake_minutes INT NOT NULL DEFAULT 60,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                INSERT INTO supervisor_configs (name, base_instruction)
                VALUES (%s, %s)
                ON CONFLICT (name) DO NOTHING
                """,
                ("Default Ops Supervisor", DEFAULT_INSTRUCTION),
            )
            conn.commit()
            cur.execute(
                """
                SELECT id, name, base_instruction, allowed_actions,
                       default_wake_minutes
                FROM supervisor_configs ORDER BY id
                """
            )
            rows = cur.fetchall()

    return [
        {
            "id": r[0],
            "name": r[1],
            "base_instruction": r[2],
            "allowed_actions": r[3],
            "default_wake_minutes": r[4],
        }
        for r in rows
    ]


@app.post("/supervisors")
async def create_supervisor(cfg: SupervisorConfig):
    with _db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO supervisor_configs
                        (name, base_instruction, allowed_actions, default_wake_minutes)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        cfg.name,
                        cfg.base_instruction,
                        cfg.allowed_actions,
                        cfg.default_wake_minutes,
                    ),
                )
                new_id = cur.fetchone()[0]
                conn.commit()
            except psycopg.errors.UniqueViolation:
                raise HTTPException(
                    status_code=409, detail="supervisor name already exists"
                )

    return {"id": new_id, "name": cfg.name}


# -------------------------------------------------------------- runs CRUD --
@app.post("/runs")
async def create_run(req: CreateRunRequest):
    client = await get_client()

    instruction = DEFAULT_INSTRUCTION

    if req.supervisor_id:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT base_instruction FROM supervisor_configs WHERE id = %s",
                    (req.supervisor_id,),
                )
                row = cur.fetchone()

        if row:
            instruction = row[0]

    try:
        handle = await client.start_workflow(
            "OrderSupervisorWorkflow",          # string name = sandbox-safe
            req.order_id,
            id=workflow_id(req.order_id),
            task_queue=TASK_QUEUE,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if req.supervisor_id:
        await handle.signal("instruction", instruction)

    return {"order_id": req.order_id, "workflow_id": handle.id}


@app.get("/runs")
async def list_runs():
    client = await get_client()
    runs = []

    async for wf in client.list_workflows(
        query="WorkflowType = 'OrderSupervisorWorkflow'",
    ):
        runs.append(
            {
                "order_id": wf.id.replace("order-supervisor-", ""),
                "workflow_id": wf.id,
                "run_id": wf.run_id,
                "status": (
                    wf.status.name
                    if hasattr(wf.status, "name")
                    else str(wf.status)
                ),
                "start_time": wf.start_time.isoformat() if wf.start_time else None,
            }
        )
        if len(runs) >= 20:
            break

    return {"runs": runs}


@app.post("/runs/{order_id}/events")
async def inject_event(order_id: str, req: InjectEventRequest):
    handle = (await get_client()).get_workflow_handle(workflow_id(order_id))
    try:
        await handle.signal(
            "order_event",
            {"event_id": req.event_id, "type": req.type, "payload": req.payload},
        )
    except Exception as exc:
        raise _workflow_error(exc)
    return {"signalled": req.event_id, "type": req.type}


@app.post("/runs/{order_id}/instruction")
async def send_instruction(order_id: str, req: InstructionRequest):
    handle = (await get_client()).get_workflow_handle(workflow_id(order_id))
    try:
        await handle.signal("instruction", req.text)
    except Exception as exc:
        raise _workflow_error(exc)
    return {"delivered": True}


@app.post("/runs/{order_id}/pause")
async def pause_run(order_id: str):
    handle = (await get_client()).get_workflow_handle(workflow_id(order_id))
    try:
        await handle.signal("pause")
    except Exception as exc:
        raise _workflow_error(exc)
    return {"paused": True}


@app.post("/runs/{order_id}/resume")
async def resume_run(order_id: str):
    handle = (await get_client()).get_workflow_handle(workflow_id(order_id))
    try:
        await handle.signal("resume")
    except Exception as exc:
        raise _workflow_error(exc)
    return {"resumed": True}


@app.post("/runs/{order_id}/terminate")
async def terminate_run(order_id: str):
    handle = (await get_client()).get_workflow_handle(workflow_id(order_id))
    try:
        await handle.cancel()
    except Exception as exc:
        raise _workflow_error(exc)
    return {"terminated": True}


@app.get("/runs/{order_id}")
async def run_status(order_id: str):
    handle = (await get_client()).get_workflow_handle(workflow_id(order_id))
    try:
        status = await handle.query("status")
    except Exception as exc:
        raise _workflow_error(exc)
    return {"order_id": order_id, "status": status}


@app.get("/runs/{order_id}/memory")
async def run_memory(order_id: str):
    handle = (await get_client()).get_workflow_handle(workflow_id(order_id))
    try:
        status = await handle.query("status")
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "order_id": order_id,
        "memory": status.get("memory", []),
        "instructions": status.get("instructions", 0),
    }


@app.get("/runs/{order_id}/activities")
async def run_activities(order_id: str):
    """Return the run's activity log from Postgres."""

    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, order_id, event_id, activity_type, action, reason, created_at
                FROM activity_records
                WHERE order_id = %s
                ORDER BY id DESC
                LIMIT 200
                """,
                (order_id,),
            )

            rows = [
                {
                    "id": r[0],
                    "order_id": r[1],
                    "event_id": r[2],
                    "activity_type": r[3],
                    "action": r[4],
                    "reason": r[5],
                    "created_at": r[6].isoformat(),
                }
                for r in cur.fetchall()
            ]

    return {
        "order_id": order_id,
        "activities": rows,
        "count": len(rows),
    }
