"""Timeline contract tests: every processed event records EVENT -> DECISION -> ACTION.

Run: uv run pytest tests/test_timeline.py -v

These test the workflow class directly (no Temporal server needed):
_apply_decision is driven with stubbed activities, which is enough to verify
the timeline contract — the order and content of event/decision/action entries.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest import mock

from temporalio import workflow

from workflows.order_supervisor import OrderSupervisorWorkflow


def _apply(decision: dict) -> OrderSupervisorWorkflow:
    """Run _apply_decision for one PAYMENT_DELAYED event with stubbed activities."""

    async def fake_execute_activity(name, args=None, **kwargs):
        if name == "record_action":
            return {
                "order_id": args[0],
                "action": args[1],
                "reason": args[2],
                "event_id": args[3],
            }
        raise ValueError(f"unexpected activity {name}")

    wf = OrderSupervisorWorkflow()
    wf.order_id = "ORD-TL"
    event = {"event_id": "e1", "type": "PAYMENT_DELAYED", "payload": {"delay_hours": 4}}

    with mock.patch.object(
        workflow, "execute_activity", side_effect=fake_execute_activity
    ), mock.patch.object(
        workflow,
        "now",
        return_value=datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc),
    ):
        asyncio.run(wf._apply_decision("ORD-TL", event, "PAYMENT_DELAYED", decision))

    return wf


def test_decision_entry_exists_between_event_and_action():
    wf = _apply(
        {
            "action": "message_payments_team",
            "reason": "Payment delay needs review",
            "wake_after_minutes": 120,
        }
    )

    types = [t["type"] for t in wf.timeline]

    # EVENT -> DECISION -> ACTION, in order.
    assert types == ["event", "decision", "action"], types

    decision = wf.timeline[1]
    assert decision["event_id"] == "e1"
    assert decision["event_type"] == "PAYMENT_DELAYED"
    assert decision["action"] == "message_payments_team"
    assert decision["reason"] == "Payment delay needs review"

    # The decision entry carries wake minutes when present.
    assert decision["wake_after_minutes"] == 120

    # Action is recorded separately (activity result + timeline entry).
    assert wf.timeline[2]["action"] == "message_payments_team"
    assert len(wf.actions_taken) == 1


def test_no_action_decision_still_recorded():
    wf = _apply({"action": "no_action", "reason": "Nothing to do"})

    types = [t["type"] for t in wf.timeline]
    assert types == ["event", "decision"], types
    assert wf.timeline[1]["action"] == "no_action"
    assert "wake_after_minutes" not in wf.timeline[1]
    assert len(wf.actions_taken) == 0


def test_sleep_decision_carries_wake_minutes():
    wf = _apply(
        {
            "action": "sleep_until",
            "reason": "Recheck later",
            "wake_after_minutes": 60,
        }
    )

    types = [t["type"] for t in wf.timeline]
    assert types == ["event", "decision"], types
    assert wf.timeline[1]["wake_after_minutes"] == 60
    assert wf.wake_seconds == 3600
