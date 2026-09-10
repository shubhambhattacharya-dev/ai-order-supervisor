import logging
import os
import time

from .providers import OpenAICompatAdapter
from .spec import ChatResult, ChatSpec, GatewayError, Usage


logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class Gateway:
    def __init__(self, adapters: list):
        self.adapters = adapters

    async def complete(self, spec: ChatSpec) -> ChatResult:
        if not self.adapters:
            raise GatewayError("no provider configured")

        last_error = None

        for index, adapter in enumerate(self.adapters):
            started = time.perf_counter()

            try:
                content, usage_info = await adapter.complete(spec)
                latency_ms = (time.perf_counter() - started) * 1000

                return ChatResult(
                    content=content,
                    usage=Usage(
                        provider=adapter.name,
                        model=getattr(adapter, "model", "fake"),
                        prompt_tokens=usage_info.get("prompt_tokens", 0),
                        completion_tokens=usage_info.get("completion_tokens", 0),
                        latency_ms=latency_ms,
                        fallback_used=index > 0,
                    ),
                )

            except GatewayError as exc:
                last_error = exc

                logger.warning(
                    "Provider failed, trying next",
                    extra={
                        "provider": adapter.name,
                        "error": str(exc),
                    },
                )

        raise GatewayError(
            f"all providers failed, last error: {last_error}"
        )


def build_gateway() -> Gateway:
    adapters = []

    groq_key = os.environ.get("GROQ_API_KEY")
    groq_model = os.environ.get(
        "LLM_PRIMARY_MODEL",
        "openai/gpt-oss-120b",
    )

    if groq_key:
        adapters.append(
            OpenAICompatAdapter(
                "groq",
                GROQ_BASE_URL,
                groq_key,
                groq_model,
            )
        )
    else:
        logger.warning(
            "GROQ_API_KEY missing — groq adapter disabled"
        )

    tr_key = os.environ.get("TOKENROUTER_API_KEY")

    tr_base = os.environ.get(
        "TOKENROUTER_BASE_URL",
        "https://tokenrouter.com/v1",
    )

    tr_model = os.environ.get(
        "TOKENROUTER_MODEL",
        "z-ai/glm-5.3-free",
    )

    if tr_key:
        adapters.append(
            OpenAICompatAdapter(
                "tokenrouter",
                tr_base,
                tr_key,
                tr_model,
            )
        )
    else:
        logger.warning(
            "TOKENROUTER_API_KEY missing — tokenrouter adapter disabled"
        )

    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    openrouter_base = os.environ.get(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    )

    openrouter_model = os.environ.get(
         "OPENROUTER_MODEL",
    "openrouter/free",
    )

    if openrouter_key:
        adapters.append(
            OpenAICompatAdapter(
                "openrouter",
                openrouter_base,
                openrouter_key,
                openrouter_model,
            )
        )
    else:
        logger.warning(
            "OPENROUTER_API_KEY missing — openrouter adapter disabled"
        )

    return Gateway(adapters)