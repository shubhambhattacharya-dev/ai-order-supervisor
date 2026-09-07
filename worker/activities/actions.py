from temporalio import activity


@activity.defn
async def record_action(
    order_id: str,
    action: str,
    reason: str,
    event_id: str,
) -> dict:
    """
    Execute a business action for the order supervisor.

    For the POC every action is a recorded activity: it is logged here and
    later persisted to the activity log table. No external system is called.
    """

    record = {
        "order_id": order_id,
        "action": action,
        "reason": reason,
        "event_id": event_id,
    }

    if activity.in_activity():
        activity.logger.info(
            "Agent action recorded",
            extra=record,
        )

    return record
