import os

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import CreateRunRequest, InjectEventRequest, InstructionRequest
from temporal import get_client, workflow_id

app = FastAPI(title="AI Order Supervisor API", version="0.1.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TASK_QUEUE = "supervisor-task-queue"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/runs")
async def create_run(req: CreateRunRequest):
    client = await get_client()
    try:
        handle = await client.start_workflow(
            "OrderSupervisorWorkflow",          # string name = sandbox-safe
            req.order_id,
            id=workflow_id(req.order_id),
            task_queue=TASK_QUEUE,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"order_id": req.order_id, "workflow_id": handle.id}


@app.post("/runs/{order_id}/events")
async def inject_event(order_id: str, req: InjectEventRequest):
    handle = (await get_client()).get_workflow_handle(workflow_id(order_id))
    try:
        await handle.signal(
            "order_event",
            {"event_id": req.event_id, "type": req.type, "payload": req.payload},
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"signalled": req.event_id, "type": req.type}


@app.post("/runs/{order_id}/instruction")
async def send_instruction(order_id: str, req: InstructionRequest):
    handle = (await get_client()).get_workflow_handle(workflow_id(order_id))
    try:
        await handle.signal("instruction", req.text)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"delivered": True}


@app.get("/runs/{order_id}")
async def run_status(order_id: str):
    handle = (await get_client()).get_workflow_handle(workflow_id(order_id))
    try:
        status = await handle.query("status")
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"order_id": order_id, "status": status}

@app.get("/runs/{order_id}/activities")
async def run_activities(order_id: str):
    """Return the run's activity log from Postgres."""

    with psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DB", "order_supervisor"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
    ) as conn:
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