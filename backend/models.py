from pydantic import BaseModel, Field

class CreateRunRequest(BaseModel):
    """Start a supervisor run for one order."""
    order_id: str = Field(min_length=1, max_length=64)
    supervisor_id: int | None = None

class InjectEventRequest(BaseModel):
    """Inject one external event into a live run."""
    event_id: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)

class InstructionRequest(BaseModel):
    """Send operator guidance to a live run."""
    text: str = Field(min_length=1, max_length=500)

class SupervisorConfig(BaseModel):
    """A reusable supervisor template (name, instruction, actions)."""
    name: str = Field(min_length=1, max_length=80)
    base_instruction: str = Field(min_length=1, max_length=2000)
    allowed_actions: list[str] = Field(default_factory=list)
    default_wake_minutes: int = Field(default=60, ge=1, le=240)
