from pydantic import BaseModel, Field

class CreateRunRequest(BaseModel):
    """Start a supervisor run for one order."""
    order_id: str = Field(min_length=1, max_length=64)

class InjectEventRequest(BaseModel):
    """Inject one external event into a live run."""
    event_id: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)

class InstructionRequest(BaseModel):
    """Send operator guidance to a live run."""
    text: str = Field(min_length=1, max_length=500)