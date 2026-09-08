from dataclasses import dataclass


@dataclass
class ChatSpec:
    messages: list[dict]
    purpose: str
    max_tokens: int = 300


@dataclass
class Usage:
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    fallback_used: bool


@dataclass
class ChatResult:
    content: str
    usage: Usage


class GatewayError(Exception):
    pass
