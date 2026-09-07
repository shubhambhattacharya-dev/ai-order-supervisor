import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from workflows.hello_workflow import GreetingWorkflow


async def main():
    client = await Client.connect("localhost:7233")

    async with Worker(
        client,
        task_queue="hello-task-queue",
        workflows=[GreetingWorkflow],
    ):
        print("Worker started...")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())