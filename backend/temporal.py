from temporalio.client import Client

_client:Client|None=None


async def get_client()->Client:
    """Connect once on first request. Import-safe when Temporal is down."""
    global _client
    if _client is None:
        _client=await Client.connect("localhost:7233")
        
    return _client


def workflow_id(order_id: str)-> str:
    """The contract both API and worker agree on: one order = one workflow."""

    return f"order-supervisor-{order_id}"