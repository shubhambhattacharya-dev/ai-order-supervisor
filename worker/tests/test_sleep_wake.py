"""Sleep/wake behavior tests (Scene 5): act-now, sleep-later, validation, dedup, wakes.

Run: uv run pytest tests/test_sleep_wake.py -v
"""

import asyncio
from datetime import datetime, timezone
from unittest import mock

from temporalio import workflow

from activities.decide import _table_decision, _validate_decision
from workflows.order_supervisor import OrderSupervisorWorkflow


# --- A/B: the two responsibilities -----------------------------------------


def test_payment_delayed_still_acts_now():
    """Requirement 12A: an important event still gets a business action."""
    d = _table_decision("PAYMENT_DELAYED")
    assert d["action"] == "message_payments_team"
    assert "wake_after_minutes" not in d


def test_safe_recheck_scenario_sleeps():
    """Requirement 12B: a no-immediate-work scenario returns sleep_until."""
    d = _table_decision("SCHEDULED_WAKEUP")
    assert d["action"] == "sleep_until"
    assert isinstance(d["wake_after_minutes"], int)
    assert 1 <= d["wake_after_minutes"] <= 240

    d2 = _table_decision("NO_UPDATE_FOR_N_HOURS")
    assert d2["action"] == "sleep_until"


def test_shipment_delayed_is_business_action_not_sleep():
    """Requirement 7: not every event sleeps - shipment_delayed still acts."""
    d = _table_decision("SHIPMENT_DELAYED")
    assert d["action"] == "message_logistics_team"


# --- C: wake_after_minutes validation --------------------------------------


def test_sleep_requires_valid_wake_minutes():
    """Requirement 12C: wake_after_minutes is validated (1..240)."""
    d = _validate_decision(
        {"action": "sleep_until", "reason": "ok", "wake_after_minutes": 2}
    )
    assert d["wake_after_minutes"] == 2

    for bad in (None, 0, -5, "soon", 2.5, True):
        try:
            _validate_decision(
                {"action": "sleep_until", "reason": "x", "wake_after_minutes": bad}
            )
            raised = False
        except ValueError:
            raised = True
        assert raised, f"wake_after_minutes={bad!r} should be rejected"

    d = _validate_decision(
        {"action": "sleep_until", "reason": "ok", "wake_after_minutes": 9999}
    )
    assert d["wake_after_minutes"] == 240

    d = _validate_decision(
        {"action": "message_customer", "reason": "x", "wake_after_minutes": 30}
    )
    assert "wake_after_minutes" not in d


# --- D/E/F: workflow-level wake, scheduled wake, dedup --------------------


def _make_wf():
    wf = OrderSupervisorWorkflow()
    wf.order_id = "ORD-SW"
    return wf


async def test_duplicate_event_is_ignored():
    """Requirement 12F: duplicate event IDs are deduplicated."""
    import logging

    wf = _make_wf()
    with mock.patch.object(
        workflow, "logger", logging.getLogger("test-workflow")
    ), mock.patch.object(
        workflow,
        "now",
        return_value=datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc),
    ):
        await wf.order_event(
            {"event_id": "e1", "type": "PAYMENT_DELAYED", "payload": {}}
        )
        first = len(wf.events)
        await wf.order_event(
            {"event_id": "e1", "type": "PAYMENT_DELAYED", "payload": {}}
        )
    assert len(wf.events) == first == 1
    assert len(wf.processed_event_ids) == 1


async def test_sleep_until_sets_durable_timer_state():
    """sleep_until decision -> wake_seconds set (durable timer data)."""
    wf = _make_wf()
    event = {"event_id": "e1", "type": "SCHEDULED_WAKEUP", "payload": {}}

    with mock.patch.object(
        workflow,
        "now",
        return_value=datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc),
    ):
        await wf._apply_decision(
            "ORD-SW",
            event,
            "SCHEDULED_WAKEUP",
            {
                "action": "sleep_until",
                "reason": "Recheck later",
                "wake_after_minutes": 2,
            },
        )

    assert wf.wake_seconds == 120
    assert wf.wake_deadline is not None
    types = [t["type"] for t in wf.timeline]
    assert types == ["event", "decision"]
    assert wf.timeline[1]["action"] == "sleep_until"
    assert wf.timeline[1]["wake_after_minutes"] == 2
    assert len(wf.actions_taken) == 0


async def test_business_action_schedules_follow_up_wake():
    """An action must not leave the supervisor waiting for a new signal forever."""
    import logging

    wf = _make_wf()
    event = {"event_id": "e-action", "type": "PAYMENT_DELAYED", "payload": {}}

    async def fake_activity(*args, **kwargs):
        return {"action": "message_payments_team"}

    with mock.patch.object(
        workflow,
        "now",
        return_value=datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc),
    ), mock.patch.object(
        workflow, "execute_activity", side_effect=fake_activity
    ), mock.patch.object(
        workflow, "logger", logging.getLogger("test-workflow")
    ):
        await wf._apply_decision(
            "ORD-SW",
            event,
            "PAYMENT_DELAYED",
            {"action": "message_payments_team", "reason": "Payment needs review"},
        )

    assert wf.actions_taken
    assert wf.wake_seconds == 2 * 60  # DEFAULT_WAKE_MINUTES follow-up recheck
    assert wf.wake_deadline is not None


def test_new_supervisor_waits_for_its_first_event():
    """An untouched order is active, not sleeping on a timer."""
    wf = _make_wf()

    assert wf.wake_seconds is None
    assert wf.wake_deadline is None


async def test_routine_signal_is_logged_without_interrupting_sleep():
    """Routine status updates are visible but do not wake the agent early."""
    import logging

    wf = _make_wf()
    wf.wake_seconds = 60 * 60
    wf.wake_deadline = "2026-09-10T13:00:00+00:00"

    with mock.patch.object(
        workflow, "logger", logging.getLogger("test-workflow")
    ), mock.patch.object(
        workflow,
        "now",
        return_value=datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc),
    ):
        await wf.order_event(
            {"event_id": "routine-1", "type": "STATUS_UPDATE", "payload": {}}
        )

    assert wf.events == []
    assert wf.wake_seconds == 60 * 60
    assert wf.wake_deadline is not None
    assert wf.timeline[-1]["event_type"] == "STATUS_UPDATE"
    assert "stays asleep" in wf.timeline[-1]["reason"]


async def test_scheduled_wake_appends_wakeup_event():
    """Requirement 12E: timer wake creates a SCHEDULED_WAKEUP event."""
    import logging

    wf = _make_wf()
    wf.wake_seconds = 60

    async def fake_wait_condition(pred, **kwargs):
        raise asyncio.TimeoutError

    with mock.patch.object(
        workflow, "wait_condition", side_effect=fake_wait_condition
    ), mock.patch.object(
        workflow, "logger", logging.getLogger("test-workflow")
    ):
        await wf._wait_for_event_or_wake("ORD-SW")

    assert wf.wakeups == 1
    assert wf.events[0]["type"] == "SCHEDULED_WAKEUP"
    assert wf.events[0]["event_id"] == "wakeup-1"
    assert "wakeup-1" in wf.processed_event_ids


async def test_new_event_wakes_before_timer():
    """Requirement 12D: a signal arriving while sleeping wakes immediately.

    wait_condition is: events OR terminal OR timer done. The event arrives
    while the timer is still pending - the timer must be cancelled and NO
    synthetic wakeup appended.
    """
    import logging

    wf = _make_wf()
    wf.wake_seconds = 300

    async def fake_wait_condition(pred, **kwargs):
        with mock.patch.object(
            workflow, "logger", logging.getLogger("test-workflow")
        ), mock.patch.object(
            workflow,
            "now",
            return_value=datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc),
        ):
            # The event signal arrives while the timer is pending:
            await wf.order_event(
                {"event_id": "sig1", "type": "PAYMENT_DELAYED", "payload": {}}
            )
        assert pred() is True

    with mock.patch.object(workflow, "wait_condition", side_effect=fake_wait_condition):
        await wf._wait_for_event_or_wake("ORD-SW")

    assert wf.wakeups == 0
    assert len(wf.events) == 1
    assert wf.events[0]["event_id"] == "sig1"
