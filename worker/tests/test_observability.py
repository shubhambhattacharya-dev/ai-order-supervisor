from unittest import mock

import observability
from llm.spec import Usage


def test_record_decision_normalizes_dataclass_usage():
    """Live gateway results use a Usage dataclass, not a JSON dictionary."""
    usage = Usage(
        provider="groq",
        model="llama-test",
        prompt_tokens=12,
        completion_tokens=4,
        latency_ms=18.75,
        fallback_used=False,
    )

    with mock.patch.object(observability, "get_langfuse", return_value=object()), mock.patch.object(
        observability,
        "_emit",
        return_value={"trace_url": "https://langfuse.example/trace/test"},
    ) as emit:
        trace_url = observability.record_decision(
            order_id="ORD-TRACE",
            event={"event_id": "evt-trace", "type": "PAYMENT_DELAYED"},
            decision={"action": "message_payments_team"},
            provider="groq",
            usage=usage,
        )

    assert trace_url == "https://langfuse.example/trace/test"
    assert emit.call_args.args[4] == {
        "model": "llama-test",
        "prompt_tokens": 12,
        "completion_tokens": 4,
        "latency_ms": 18.8,
        "fallback_used": False,
    }
