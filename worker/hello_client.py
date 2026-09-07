import asyncio

from temporalio.client import Client

from workflows.hello_workflow import GreetingWorkflow


async def main():
    client = await Client.connect("localhost:7233")

    result = await client.execute_workflow(
        GreetingWorkflow.run,
        "World",
        id="hello-1",
        task_queue="hello-task-queue",
    )

    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())