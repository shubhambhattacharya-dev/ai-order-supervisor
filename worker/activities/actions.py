
from __future__ import annotations

import os
from typing import Any

import psycopg
from temporalio import activity


def _conn() -> psycopg.Connection[Any]:
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DB", "order_supervisor"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
    )


def _insert(record: dict) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO activity_records
                    (order_id, event_id, activity_type, action, reason)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    record["order_id"],
                    record.get("event_id"),
                    "agent_action",
                    record["action"],
                    record.get("reason"),
                ),
            )
            conn.commit()


@activity.defn
async def record_action(
    order_id: str,
    action: str,
    reason: str,
    event_id: str,
) -> dict:
    """Persist one agent action to the run activity log (Postgres)."""

    record: dict[str, Any] = {
        "order_id": order_id,
        "action": action,
        "reason": reason,
        "event_id": event_id,
    }

    if activity.in_activity():
        activity.logger.info("Agent action recorded", extra=record)

    try:
        _insert(record)
    except Exception as exc:  # noqa: S110
        activity.logger.warning(
            "activity log write failed — run continues without it",
            extra={"error": str(exc), "record": record},
        )

    return record