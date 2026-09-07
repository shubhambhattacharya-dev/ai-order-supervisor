import asyncio
import logging

from temporalio.client import Client
from workflows.order_supervisor import OrderSupervisorWorkflow


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s "
           "%(filename)s:%(lineno)d %(message)s",
)

logger = logging.getLogger(__name__)


async def send_event(handle, event: dict) -> None:
    event_id = event.get("event_id")
    event_type = event.get("type")

    if not event_id or not event_type:
        raise ValueError(
            f"Invalid event: event_id and type are required. "
            f"Received: {event}"
        )

    try:
        await handle.signal("order_event", event)

        logger.info(
            "Event signalled successfully",
            extra={
                "event_id": event_id,
                "event_type": event_type,
            },
        )

    except Exception:
        logger.exception(
            "Failed to signal order event",
            extra={
                "event_id": event_id,
                "event_type": event_type,
            },
        )
        raise


async def main():
    order_id = "ORD-1"
    workflow_id = f"order-supervisor-{order_id}"

    try:
        logger.info(
            "Connecting to Temporal",
            extra={"order_id": order_id},
        )

        client = await Client.connect("localhost:7233")

        logger.info(
            "Starting order supervisor",
            extra={
                "order_id": order_id,
                "workflow_id": workflow_id,
            },
        )

        handle = await client.start_workflow(
            OrderSupervisorWorkflow.run,
            order_id,
            id=workflow_id,
            task_queue="supervisor-task-queue",
        )

        logger.info(
            "Supervisor started",
            extra={
                "order_id": order_id,
                "workflow_id": workflow_id,
            },
        )

        # Event 1
        await asyncio.sleep(1)

        await send_event(
            handle,
            {
                "event_id": "e1",
                "type": "STATUS_UPDATE",
                "payload": {
                    "status": "packed",
                },
            },
        )

        # Event 2
        await asyncio.sleep(1)

        await send_event(
            handle,
            {
                "event_id": "e2",
                "type": "PAYMENT_DELAYED",
                "payload": {
                    "delay_hours": 4,
                },
            },
        )

        # Duplicate event
        await asyncio.sleep(1)

        await send_event(
            handle,
            {
                "event_id": "e2",
                "type": "PAYMENT_DELAYED",
                "payload": {
                    "delay_hours": 4,
                },
            },
        )

        # Terminal event
        await asyncio.sleep(2)

        await send_event(
            handle,
            {
                "event_id": "e3",
                "type": "COMPLETED",
                "payload": {
                    "delivered_at": "2026-09-07T19:00:00",
                },
            },
        )

        # Wait only after sending the terminal event.
        logger.info(
            "Waiting for supervisor to complete",
            extra={"order_id": order_id},
        )

        result = await handle.result()

        logger.info(
            "Supervisor completed successfully",
            extra={
                "order_id": order_id,
                "result": result,
            },
        )

        print(f"Result: {result}")

    except Exception:
        logger.exception(
            "Supervisor client failed",
            extra={
                "order_id": order_id,
                "workflow_id": workflow_id,
            },
        )
        raise


if __name__ == "__main__":
    asyncio.run(main())