import asyncio
import time

from temporalio.client import Client

from workflows.order_supervisor import OrderSupervisorWorkflow


async def main():
    client = await Client.connect("localhost:7233")

    order_id = f"ORD-{int(time.time())}"
    workflow_id = f"order-supervisor-{order_id}"

    # Start the long-running supervisor (does NOT wait for it to finish)
    handle = await client.start_workflow(
        OrderSupervisorWorkflow.run,
        order_id,
        id=workflow_id,
        task_queue="supervisor-task-queue",
    )
    print(f"Supervisor started for {order_id} (workflow {workflow_id})")

    # Event 1: normal status update -> workflow wakes, decides, sleeps
    await asyncio.sleep(1)
    await handle.signal("order_event", {
        "event_id": "e1",
        "type": "STATUS_UPDATE",
        "payload": {"status": "packed"},
    })
    print("Signalled e1 STATUS_UPDATE")

    # Event 2: a delay event -> decide maps it to a team message
    await asyncio.sleep(1)
    await handle.signal("order_event", {
        "event_id": "e2",
        "type": "PAYMENT_DELAYED",
        "payload": {"delay_hours": 4},
    })
    print("Signalled e2 PAYMENT_DELAYED")

    # Event 3: duplicate of e2 -> worker logs "Ignoring duplicate event"
    await asyncio.sleep(1)
    await handle.signal("order_event", {
        "event_id": "e2",
        "type": "PAYMENT_DELAYED",
        "payload": {"delay_hours": 4},
    })
    print("Signalled e2 again (duplicate - should be deduped)")

    # Peek at live state through the status query
    status = await handle.query(OrderSupervisorWorkflow.status)
    print(f"Status mid-run: {status}")

    # Event 4: terminal -> rules complete the workflow
    await asyncio.sleep(1)
    await handle.signal("order_event", {
        "event_id": "e3",
        "type": "COMPLETED",
        "payload": {"delivered_at": "2026-09-07T19:00:00"},
    })
    print("Signalled e3 COMPLETED")

    # NOW wait for the final result
    result = await handle.result()
    print(f"Result: {result}")

    status = await handle.query(OrderSupervisorWorkflow.status)
    print(f"Status at end: {status}")


if __name__ == "__main__":
    asyncio.run(main())
