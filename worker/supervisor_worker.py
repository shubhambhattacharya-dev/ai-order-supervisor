import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from logging_setup import setup_logging
from workflows.order_supervisor import OrderSupervisorWorkflow


async def main():
    setup_logging()

    client = await Client.connect("localhost:7233")

    async with Worker(
        client,
        task_queue="supervisor-task-queue",
        workflows=[OrderSupervisorWorkflow],
    ):
        print("Supervisor worker started...")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())