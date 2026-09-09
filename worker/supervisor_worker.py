import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from activities import actions, decide, final_output
from logging_setup import setup_logging
from workflows.order_supervisor import OrderSupervisorWorkflow

import asyncio
import os



from pathlib import Path
from dotenv import dotenv_values   # needs: uv add python-dotenv

# Load repo-root .env first, then worker/.env overrides (non-empty values only).
for _env_path in (Path(__file__).parent.parent / ".env", Path(__file__).parent / ".env"):
    if _env_path.exists():
        os.environ.update(
            {k: v for k, v in dotenv_values(_env_path).items() if v}
        )


async def main():
    setup_logging()

    client = await Client.connect("localhost:7233")

    async with Worker(
        client,
        task_queue="supervisor-task-queue",
        workflows=[OrderSupervisorWorkflow],
        activities=[
    decide.decide,
    actions.record_action,
    final_output.final_output,
]
    ):
        print("Supervisor worker started...")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
