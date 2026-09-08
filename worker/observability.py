"""Langfuse v4 tracing for agent decisions.

Zero-risk by design:
- Not configured (empty LANGFUSE_PUBLIC_KEY/SECRET_KEY) -> complete no-op.
- Any Langfuse failure is swallowed and logged at DEBUG: tracing must never
  break a decision.

Langfuse v4 note: the SDK is OpenTelemetry-based. We use the top-level
@observe decorator (verified against langfuse 4.15.x) - it creates the trace
span and captures the function's input arguments and return value
automatically. update_current_span then attaches provider/cost metadata, and
get_trace_url() returns a link you can log for the demo.

Configure in .env (repo root):
    LANGFUSE_PUBLIC_KEY=pk-lf-...
    LANGFUSE_SECRET_KEY=sk-lf-...
    LANGFUSE_HOST=http://localhost:3002
Then open http://localhost:3002 -> Traces to watch decisions arrive.
"""

import atexit
import logging
import os

logger = logging.getLogger(__name__)

_client = None
_init_attempted = False


def get_langfuse():
    """Create the Langfuse client once. Returns None when unconfigured."""
    global _client, _init_attempted

    if _client is not None:
        return _client

    if _init_attempted:
        return None

    _init_attempted = True

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()

    if not public_key or not secret_key:
        logger.info("Langfuse keys not set - tracing disabled (this is fine)")
        return None

    try:
        from langfuse import Langfuse

        _client = Langfuse(
            host=os.environ.get("LANGFUSE_HOST", "http://localhost:3002"),
        )

        logger.info("Langfuse tracing enabled")

        atexit.register(_flush)

        return _client

    except Exception as exc:
        logger.warning("Langfuse init failed, tracing disabled: %s", exc)
        return None


def _flush():
    try:
        if _client is not None:
            _client.flush()
    except Exception:
        pass


try:
    from langfuse import observe
except Exception:
    observe = None


def _emit(order_id: str, event: dict, decision: dict, provider: str, usage: dict):
    """Runs as a Langfuse-observed span when tracing is enabled.

    @observe captures the arguments as trace input and the return value as
    trace output automatically.
    """
    url = None

    client = get_langfuse()

    if client is not None:
        try:
            client.update_current_span(
                metadata={
                    "order_id": order_id,
                    "event_type": (event or {}).get("type"),
                    "provider": provider,
                    **(usage or {}),
                },
                level="DEFAULT" if provider != "table-fallback" else "WARNING",
            )
            url = client.get_trace_url()
        except Exception as exc:
            logger.debug("span metadata failed (ignored): %s", exc)

    return {"decision": decision, "trace_url": url}


if observe is not None:
    _emit = observe(name="agent-decision")(_emit)


def record_decision(
    *,
    order_id: str,
    event: dict,
    decision: dict,
    provider: str,
    usage: dict | None = None,
) -> str | None:
    """Record one agent decision as a Langfuse trace.

    Called from the decide activity after a decision (LLM or table fallback)
    is final. Never raises. Returns the trace URL when tracing is enabled,
    otherwise None - log it so the demo video can click through.
    """
    try:
        if get_langfuse() is None:
            return None

        if usage:
            usage = {
                "model": usage.get("model"),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "latency_ms": round(usage.get("latency_ms", 0), 1),
                "fallback_used": usage.get("fallback_used"),
            }

        result = _emit(order_id, event, decision, provider, usage or {})

        return (result or {}).get("trace_url")

    except Exception as exc:
        logger.debug("Langfuse record failed (ignored): %s", exc)
        return None
