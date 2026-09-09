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