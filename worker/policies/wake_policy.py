"""Lightweight wake-up policy (the brief's event-importance classifier).

Pure function, zero tokens, unit-testable: decides whether an incoming event
is important enough to wake the main agent, or should just be logged while
the workflow keeps sleeping. Unknown event types wake the agent to be safe.
"""

IMPORTANT = {
    "PAYMENT_DELAYED",
    "PAYMENT_FAILED",
    "SHIPMENT_DELAYED",
    "SHIPMENT_CREATED",
    "FULFILLMENT_DELAYED",
    "CUSTOMER_MESSAGE_RECEIVED",
    "REFUND_REQUESTED",
    "DELIVERED",
    "COMPLETED",
    "CANCELLED",
    "SCHEDULED_WAKEUP",
    "NO_UPDATE_FOR_N_HOURS",
}

LOG_ONLY = {
    "STATUS_UPDATE",
    "PAYMENT_CONFIRMED",
    "SHIPMENT_CREATED",
}


def should_wake(event: dict) -> tuple[bool, str]:
    """Return (wake_now, reason) for one incoming event."""
    event_type = (event.get("type") or "").upper()

    if event_type in IMPORTANT:
        return True, "important event"

    if event_type in LOG_ONLY:
        return False, "routine update - logged, agent stays asleep"

    return True, "unknown event type - wake to be safe"
