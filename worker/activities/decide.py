from temporalio import activity


# The five business actions required by the brief, plus the runtime
# capabilities the agent needs to sleep and to do nothing.
ALLOWED_ACTIONS = {
    "message_fulfillment_team",
    "message_payments_team",
    "message_logistics_team",
    "message_customer",
    "create_internal_note",
    "sleep_until",
    "no_action",
}

# Fake decision table: event type -> (action, wake_after_minutes or None).
# Replaced by a real LLM call in Day 2.
DECISIONS = {
    "PAYMENT_DELAYED": ("message_payments_team", 120),
    "SHIPMENT_DELAYED": ("message_logistics_team", 120),
    "FULFILLMENT_DELAYED": ("message_fulfillment_team", 60),
    "CUSTOMER_MESSAGE_RECEIVED": ("message_customer", None),
    "REFUND_REQUESTED": ("create_internal_note", 240),
    "COMPLETED": ("no_action", None),
    "CANCELLED": ("no_action", None),
    "SCHEDULED_WAKEUP": ("sleep_until", 60),
}

DEFAULT_DECISION = ("sleep_until", 60)


def _validate_decision(decision: dict) -> dict:
    action = decision.get("action")

    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported decision action: {action}")

    return decision


@activity.defn
async def decide(order_id: str, event: dict) -> dict:
    """
    Decide what the order supervisor should do next.

    This is a fake decision-maker for now.
    A real LLM will replace this logic later.
    """

    event_type = event.get("type")
    action, wake_after_minutes = DECISIONS.get(event_type, DEFAULT_DECISION)

    decision = {
        "action": action,
        "reason": f"Event {event_type} mapped to {action} by the decision table.",
    }

    if wake_after_minutes is not None:
        decision["wake_after_minutes"] = wake_after_minutes

    decision = _validate_decision(decision)

    if activity.in_activity():
        activity.logger.info(
            "Order decision made",
            extra={
                "order_id": order_id,
                "event_type": event_type,
                "action": decision["action"],
                "reason": decision["reason"],
            },
        )

    return decision
