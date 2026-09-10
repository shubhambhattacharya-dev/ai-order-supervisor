import asyncio

import pytest

from activities.decide import DEFAULT_DECISION, DECISIONS, _validate_decision, decide


class TestDecisionTable:
    def test_every_table_decision_is_an_allowed_action(self):
        for event_type, (action, _) in DECISIONS.items():
            assert action in {
                "message_fulfillment_team",
                "message_payments_team",
                "message_logistics_team",
                "message_customer",
                "create_internal_note",
                "sleep_until",
                "no_action",
            }, f"{event_type} maps to non-allowed action {action}"

    def test_unknown_event_is_noted_not_slept(self):
        assert DEFAULT_DECISION == ("create_internal_note", 60)

    @pytest.mark.parametrize(
        "event_type,expected_action",
        [
            ("PAYMENT_DELAYED", "message_payments_team"),
            ("SHIPMENT_DELAYED", "message_logistics_team"),
            ("CUSTOMER_MESSAGE_RECEIVED", "message_customer"),
            ("REFUND_REQUESTED", "create_internal_note"),
            ("COMPLETED", "no_action"),
            ("DELIVERED", "no_action"),
            # No-update is a recheck, not customer contact: sleep and look again.
            ("NO_UPDATE_FOR_N_HOURS", "sleep_until"),
        ],
    )
    def test_decide_maps_event_types(self, event_type, expected_action):
        decision = asyncio.run(decide("ORD-1", {"event_id": "e1", "type": event_type}))
        assert decision["action"] == expected_action

    def test_sleep_decisions_carry_wake_after_minutes(self):
        decision = asyncio.run(decide("ORD-1", {"event_id": "e1", "type": "SCHEDULED_WAKEUP"}))
        assert decision["action"] == "sleep_until"
        assert decision["wake_after_minutes"] > 0

    def test_log_only_events_never_reach_decide(self):
        # STATUS_UPDATE is filtered by the wake policy before this activity.
        assert "STATUS_UPDATE" not in DECISIONS
        from policies.wake_policy import should_wake
        wake, _ = should_wake({"type": "STATUS_UPDATE"})
        assert wake is False

    def test_terminal_decision_has_no_wake_time(self):
        decision = asyncio.run(decide("ORD-1", {"event_id": "e1", "type": "COMPLETED"}))
        assert "wake_after_minutes" not in decision


class TestValidation:
    def test_rejects_unknown_action(self):
        with pytest.raises(ValueError):
            _validate_decision({"action": "delete_database"})

    def test_accepts_brief_actions(self):
        _validate_decision({"action": "message_customer"})
        _validate_decision({"action": "create_internal_note"})
