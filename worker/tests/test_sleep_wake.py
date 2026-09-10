"""Sleep/wake behavior tests (Scene 5): act-now, sleep-later, validation, dedup, wakes.

Run: uv run pytest tests/test_sleep_wake.py -v
"""

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


async def test_scheduled_wake_appends_wakeup_event():
    """Requirement 12E: timer wake creates a SCHEDULED_WAKEUP event."""
    import asyncio
    import logging

    wf = _make_wf()
    wf.wake_seconds = 60

    async def fake_sleep(seconds):
        return None  # "timer fires" immediately

    async def fake_wait_condition(pred):
        import asyncio

        # Let the created timer task finish so .done() becomes True.
        for _ in range(5):
            await asyncio.sleep(0)
        return None

    real_create_task = asyncio.create_task

    def fake_create_task(coro, **kw):
        return real_create_task(coro, **kw)

    with mock.patch.object(workflow, "sleep", side_effect=fake_sleep), mock.patch.object(
        workflow, "wait_condition", side_effect=fake_wait_condition
    ), mock.patch.object(
        workflow, "logger", logging.getLogger("test-workflow")
    ), mock.patch(
        "asyncio.create_task", side_effect=fake_create_task
    ):
        await wf._wait_for_event_or_wake("ORD-SW")

    assert wf.wakeups == 1
    assert wf.events[0]["type"] == "SCHEDULED_WAKEUP"
    assert wf.events[0]["event_id"] == "wakeup-1"


async def test_new_event_wakes_before_timer():
    """Requirement 12D: a signal arriving while sleeping wakes immediately.

    wait_condition is: events OR terminal OR timer done. The event arrives
    while the timer is still pending - the timer must be cancelled and NO
    synthetic wakeup appended.
    """
    import asyncio
    import logging

    wf = _make_wf()
    wf.wake_seconds = 300

    sleep_started = asyncio.Event()

    async def fake_sleep(seconds):
        sleep_started.set()
        await asyncio.Event().wait()  # never completes - timer still pending

    async def fake_wait_condition(pred):
        await sleep_started.wait()
        with mock.patch.object(
            workflow, "logger", logging.getLogger("test-workflow")
        ):
            # The event signal arrives while the timer is pending:
            await wf.order_event(
                {"event_id": "sig1", "type": "PAYMENT_DELAYED", "payload": {}}
            )
        assert pred() is True

    with mock.patch.object(workflow, "sleep", side_effect=fake_sleep), mock.patch.object(
        workflow, "wait_condition", side_effect=fake_wait_condition
    ):
        await wf._wait_for_event_or_wake("ORD-SW")

    assert wf.wakeups == 0
    assert len(wf.events) == 1
    assert wf.events[0]["event_id"] == "sig1"
