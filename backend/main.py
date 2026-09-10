import asyncio
import json
import os

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

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


@app.get("/supervisors/{supervisor_id}")
async def get_supervisor(supervisor_id: int):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, base_instruction, allowed_actions,
                       default_wake_minutes
                FROM supervisor_configs WHERE id = %s
                """,
                (supervisor_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="supervisor not found")

    return {
        "id": row[0],
        "name": row[1],
        "base_instruction": row[2],
        "allowed_actions": row[3],
        "default_wake_minutes": row[4],
    }


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


@app.post("/runs/{order_id}/instructions")
async def send_instruction_alias(order_id: str, req: InstructionRequest):
    """Brief-suggested plural alias for /instruction."""
    return await send_instruction(order_id, req)


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


@app.get("/runs/{order_id}/decisions")
async def run_decisions(order_id: str):
    """LLM decision records for one run (observability)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_id, provider, model, action, reason,
                       prompt_tokens, completion_tokens, latency_ms,
                       fallback_used, trace_url, created_at
                FROM decisions WHERE order_id = %s
                ORDER BY id DESC LIMIT 200
                """,
                (order_id,),
            )
            rows = cur.fetchall()

    return {
        "order_id": order_id,
        "decisions": [
            {
                "id": r[0], "event_id": r[1], "provider": r[2], "model": r[3],
                "action": r[4], "reason": r[5], "prompt_tokens": r[6],
                "completion_tokens": r[7], "latency_ms": float(r[8] or 0),
                "fallback_used": r[9],
                "trace_url": r[10],
                "created_at": r[11].isoformat(),
            }
            for r in rows
        ],
    }


@app.get("/runs/{order_id}/final")
async def run_final(order_id: str):
    """The persisted end-of-run report (summary, learnings, feedback)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT summary, actions_taken, learnings, feedback, created_at
                FROM final_outputs WHERE order_id = %s
                """,
                (order_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="final output not ready")

    return {
        "order_id": order_id,
        "summary": row[0],
        "actions_taken": row[1],
        "learnings": row[2],
        "feedback": row[3],
        "created_at": row[4].isoformat(),
    }


@app.get("/analytics/decisions")
async def analytics_decisions():
    """Recent LLM decisions across all runs, for the observability page."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, order_id, event_id, provider, model, action, reason,
                       prompt_tokens, completion_tokens, latency_ms,
                       fallback_used, trace_url, created_at
                FROM decisions ORDER BY id DESC LIMIT 100
                """
            )
            rows = cur.fetchall()

    decisions = [
        {
            "id": r[0], "order_id": r[1], "event_id": r[2], "provider": r[3],
            "model": r[4], "action": r[5], "reason": r[6], "prompt_tokens": r[7],
            "completion_tokens": r[8], "latency_ms": float(r[9] or 0),
            "fallback_used": r[10], "trace_url": r[11],
            "created_at": r[12].isoformat(),
        }
        for r in rows
    ]

    return {
        "decisions": decisions,
        "total_tokens": sum(
            d["prompt_tokens"] + d["completion_tokens"] for d in decisions
        ),
        "avg_latency_ms": (
            round(sum(d["latency_ms"] for d in decisions) / len(decisions), 1)
            if decisions
            else 0
        ),
        "fallback_count": sum(1 for d in decisions if d["fallback_used"]),
    }


@app.get("/observability")
async def observability():
    """Langfuse connection info for the console's observability page."""
    host = os.environ.get("LANGFUSE_HOST", "").strip()
    traces_url = os.environ.get("LANGFUSE_TRACES_URL", "").strip() or (
        f"{host}/traces" if host else None
    )
    enabled = bool(traces_url)

    return {
        "enabled": enabled,
        "host": host or None,
        "traces_url": traces_url,
    }


@app.get("/runs/{order_id}/stream")
async def stream_run(order_id: str):
    """Server-Sent Events: pushes the run's status the moment it changes."""

    async def event_gen():
        last_payload = None
        while True:
            try:
                handle = (await get_client()).get_workflow_handle(
                    workflow_id(order_id)
                )
                status = await handle.query("status")
                payload = json.dumps(
                    {"order_id": order_id, "status": status or {}}
                )
            except Exception:
                payload = json.dumps({"order_id": order_id, "status": None})

            if payload != last_payload:
                last_payload = payload
                yield f"data: {payload}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/analytics/stream")
async def stream_analytics():
    """SSE: pushes the decisions feed whenever a new decision lands."""

    async def event_gen():
        last_payload = None
        while True:
            try:
                data = await analytics_decisions()
                payload = json.dumps(data)
                if payload != last_payload:
                    last_payload = payload
                    yield f"data: {payload}\n\n"
            except Exception:
                pass
            await asyncio.sleep(3)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
