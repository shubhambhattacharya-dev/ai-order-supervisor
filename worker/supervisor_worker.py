import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from activities import actions, decide
from logging_setup import setup_logging
from workflows.order_supervisor import OrderSupervisorWorkflow

import asyncio
import os



from pathlib import Path
from dotenv import dotenv_values   # needs: uv add python-dotenv

env = dotenv_values(Path(__file__).parent / ".env")
os.environ.update({k: v for k, v in env.items() if v})


async def main():
    setup_logging()

    client = await Client.connect("localhost:7233")

    async with Worker(
        client,
        task_queue="supervisor-task-queue",
        workflows=[OrderSupervisorWorkflow],
        activities=[decide.decide, actions.record_action],
    ):
        print("Supervisor worker started...")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
