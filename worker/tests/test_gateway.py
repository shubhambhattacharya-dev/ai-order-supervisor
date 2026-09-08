import asyncio
import json

import pytest

from activities.decide import _validate_decision
from llm.gateway import Gateway
from llm.providers import FakeAdapter, OpenAICompatAdapter
from llm.spec import ChatSpec, GatewayError

SPEC = ChatSpec(messages=[{"role": "user", "content": "decide"}], purpose="decide")
VALID = json.dumps({"action": "message_payments_team", "reason": "x", "wake_after_minutes": 120})
INVALID = json.dumps({"action": "refund_customer"})


def run(coro):
    return asyncio.run(coro)


class RaisingAdapter:
    name = "down"

    async def complete(self, spec):
        raise GatewayError("down: simulated outage")


class TestChainWalk:
    def test_fallback_on_provider_failure(self):
        g = Gateway([RaisingAdapter(), FakeAdapter([VALID])])
        result = run(g.complete(SPEC))
        assert result.usage.provider == "fake"
        assert result.usage.fallback_used is True

    def test_primary_success_no_fallback(self):
        g = Gateway([FakeAdapter([VALID]), RaisingAdapter()])
        result = run(g.complete(SPEC))
        assert result.usage.fallback_used is False

    def test_all_fail_raises_gateway_error(self):
        g = Gateway([RaisingAdapter(), RaisingAdapter()])
        with pytest.raises(GatewayError):
            run(g.complete(SPEC))

    def test_empty_chain_raises(self):
        with pytest.raises(GatewayError):
            run(Gateway([]).complete(SPEC))


class TestAdapterContract:
    def test_fake_pops_then_repeats(self):
        fa = FakeAdapter([VALID, INVALID])
        assert json.loads(run(fa.complete(SPEC)))["action"] == "message_payments_team"
        assert json.loads(run(fa.complete(SPEC)))["action"] == "refund_customer"
        assert json.loads(run(fa.complete(SPEC)))["action"] == "refund_customer"

    def test_invalid_response_fails_validation(self):
        with pytest.raises(ValueError):
            _validate_decision(json.loads(INVALID))

    def test_dead_endpoint_wrapped_as_gateway_error(self):
        ad = OpenAICompatAdapter("test-prov", "http://localhost:9/v1", "k", "m")
        with pytest.raises(GatewayError):
            run(ad.complete(SPEC))