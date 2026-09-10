import os

from temporalio.client import Client

_client: Client | None = None


async def get_client() -> Client:
    """Connect once on first request. Import-safe when Temporal is down."""
    global _client
    if _client is None:
        host = os.environ.get("TEMPORAL_HOST", "localhost").strip()
        port = os.environ.get("TEMPORAL_PORT", "7233").strip()
        _client = await Client.connect(f"{host}:{port}")
    return _client


async def reset_client() -> None:
    """Reset cached client so reconnect happens on next call."""
    global _client
    _client = None


def workflow_id(order_id: str) -> str:
    """The contract both API and worker agree on: one order = one workflow."""
    return f"order-supervisor-{order_id}"