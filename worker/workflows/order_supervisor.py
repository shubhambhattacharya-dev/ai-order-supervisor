import asyncio
import json
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from policies.wake_policy import should_wake

DEFAULT_WAKE_MINUTES = 2


def _event_detail(event: dict) -> str:
    """Create a compact, safe timeline summary from an event payload."""
    payload = event.get("payload")
    if not isinstance(payload, dict) or not payload:
        return "No payload provided."

    reason = payload.get("reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()[:240]

    summary = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"Payload received: {summary[:240]}"


@workflow.defn
class OrderSupervisorWorkflow:
    def __init__(self):
        self.order_id = ""
        self.events: list[dict] = []
        self.processed_event_ids: set[str] = set()
        self.actions_taken: list[dict] = []
        self.terminal = False
        self.wake_seconds: int | None = None
        self.wakeups = 0
        self.instructions: list[str] = []
        self.memory: list[dict] = []
        self.timeline: list[dict] = []
        self.paused = False
        self.wake_deadline: str | None = None
        self.started_at: str | None = None

    @workflow.run
    async def run(self, order_id: str) -> str:
        self.order_id = order_id
        workflow.logger.info("[RUN] started for %s", order_id)

        try:
            self.started_at = workflow.now().isoformat()
            while not self.terminal:
                if self.paused:
                    await workflow.wait_condition(
                        lambda: not self.paused or self.terminal
                    )

                    if self.terminal:
                        break

                await self._process_events(order_id)

                if self.terminal:
                    break

                await self._wait_for_event_or_wake(order_id)

            report = await workflow.execute_activity(
                "final_output",
                args=[
                    order_id,
                    self.memory,
                    self.actions_taken,
                ],
                start_to_close_timeout=timedelta(seconds=45),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            workflow.logger.info(
                "[DONE] %s | summary: %s", order_id, report["summary"]
            )

            return json.dumps(report)

        except asyncio.CancelledError:
            workflow.logger.info(
                "[CONTROL] terminated by operator (events=%d, actions=%d)",
                len(self.processed_event_ids),
                len(self.actions_taken),
            )
            try:
                await asyncio.shield(
                    workflow.execute_activity(
                        "final_output",
                        args=[
                            order_id,
                            self.memory,
                            self.actions_taken,
                        ],
                        start_to_close_timeout=timedelta(seconds=45),
                        retry_policy=RetryPolicy(maximum_attempts=2),
                    )
                )
            except Exception:
                workflow.logger.exception(
                    "[CONTROL] final_output failed during termination"
                )
            raise

        except Exception:
            workflow.logger.exception("[RUN] failed for %s", order_id)
            raise

    async def _process_events(self, order_id: str) -> None:
        while self.events:
            event = self.events.pop(0)

            event_id = event.get("event_id")
            event_type = event.get("type")

            if not event_id or not event_type:
                workflow.logger.warning(
                    "Ignoring malformed event",
                    extra={
                        "order_id": order_id,
                        "event": event,
                    },
                )
                continue

            decision = await workflow.execute_activity(
                "decide",
                args=[
                    order_id,
                    {
                        **event,
                        "operator_instructions": self.instructions,
                    },
                    self.memory[-8:],
                ],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            await self._apply_decision(
                order_id,
                event,
                event_type,
                decision,
            )

            if event_type in {"COMPLETED", "CANCELLED"}:
                self.terminal = True

                workflow.logger.info(
                    "[RULE] terminal event %s -> completing run",
                    event_type,
                )
                break

    async def _apply_decision(
        self,
        order_id: str,
        event: dict,
        event_type: str,
        decision: dict,
    ) -> None:
        action = decision.get("action")
        reason = decision.get("reason", "")

        wake_at = None
        if action == "sleep_until":
            wake_at = self._schedule_wake(
                int(decision.get("wake_after_minutes", DEFAULT_WAKE_MINUTES))
            )

        # Add the event to the timeline.
        self.timeline.append(
            {
                "type": "event",
                "event_id": event["event_id"],
                "event_type": event_type,
                "reason": _event_detail(event),
                "at": workflow.now().isoformat(),
            }
        )

        # Every decision is recorded: EVENT -> DECISION -> ACTION.
        decision_entry = {
            "type": "decision",
            "event_id": event["event_id"],
            "event_type": event_type,
            "action": action,
            "reason": reason,
            "at": workflow.now().isoformat(),
        }

        if decision.get("wake_after_minutes") is not None:
            decision_entry["wake_after_minutes"] = decision["wake_after_minutes"]
        if wake_at is not None:
            decision_entry["wake_at"] = wake_at

        self.timeline.append(decision_entry)

        # Add important event information to memory.
        self.memory.append(
            {
                "event_type": event_type,
                "reason": reason,
            }
        )

        if action == "no_action":
            if event_type not in {"COMPLETED", "CANCELLED"}:
                self._schedule_wake(DEFAULT_WAKE_MINUTES)
            return

        if action == "sleep_until":
            return

        record = await workflow.execute_activity(
            "record_action",
            args=[
                order_id,
                action,
                reason,
                event["event_id"],
            ],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        self.actions_taken.append(record)

        self.timeline.append(
            {
                "type": "action",
                "event_id": event["event_id"],
                "event_type": event_type,
                "action": action,
                "reason": reason,
                "at": workflow.now().isoformat(),
            }
        )

        self.memory.append(
            {
                "action": action,
                "reason": reason,
            }
        )
        # A business action is followed by a durable recheck. The old code
        # discarded the follow-up interval and left the workflow waiting for a
        # signal forever.
        self._schedule_wake(DEFAULT_WAKE_MINUTES)

    def _schedule_wake(self, minutes: int) -> str:
        self.wake_seconds = max(1, minutes) * 60
        self.wake_deadline = (
            workflow.now() + timedelta(seconds=self.wake_seconds)
        ).isoformat()
        return self.wake_deadline

    async def _wait_for_event_or_wake(
        self,
        order_id: str,
    ) -> None:
        if self.wake_seconds is None:
            await workflow.wait_condition(
                lambda: bool(self.events) or self.terminal
            )
            return

        wait_seconds = self.wake_seconds
        self.wake_seconds = None
        timer_fired = False

        try:
            # Temporal creates and owns this timer. It survives worker/server
            # restarts and wakes this workflow either when a signal arrives or
            # exactly when the timeout expires.
            await workflow.wait_condition(
                lambda: bool(self.events) or self.terminal,
                timeout=timedelta(seconds=wait_seconds),
                timeout_summary="order-supervisor-scheduled-wake",
            )
        except asyncio.TimeoutError:
            timer_fired = True
        finally:
            self.wake_deadline = None

        if timer_fired:
            self.wakeups += 1

            wake_event = {
                "event_id": f"wakeup-{self.wakeups}",
                "type": "SCHEDULED_WAKEUP",
                "payload": {"wakeup_number": self.wakeups},
            }
            self.processed_event_ids.add(wake_event["event_id"])
            self.events.append(wake_event)

            workflow.logger.info(
                "[WAKEUP] scheduled wake-up #%d fired", self.wakeups
            )

    @workflow.query
    def status(self) -> dict:
        return {
            "events_queued": len(self.events),
            "events_processed": len(self.processed_event_ids),
            "actions_taken": len(self.actions_taken),
            "wakeups": self.wakeups,
            "sleeping": self.wake_deadline is not None,
            "next_wake_at": self.wake_deadline,
            "started_at": self.started_at,
            "terminal": self.terminal,
            "paused": self.paused,
            "instructions": len(self.instructions),
            "memory": self.memory,
            "timeline": self.timeline,
        }

    @workflow.signal
    async def order_event(self, event: dict) -> None:
        event_id = event.get("event_id")

        if not event_id:
            workflow.logger.warning(
                "[EVENT] rejected: missing event_id (%s)", event
            )
            return

        if event_id in self.processed_event_ids:
            workflow.logger.info(
                "[DEDUP] %s duplicate ignored", event_id
            )
            self.timeline.append(
                {
                    "type": "event",
                    "event_id": event_id,
                    "event_type": event.get("type"),
                    "reason": f"[DEDUP] Duplicate {event_id} ignored; workflow continues sleeping.",
                    "at": workflow.now().isoformat(),
                }
            )
            return

        self.processed_event_ids.add(event_id)
        wake_now, why = should_wake(event)
        if not wake_now:
            # Routine updates are retained in the audit trail but must not
            # interrupt the currently scheduled durable timer.
            self.timeline.append(
                {
                    "type": "event",
                    "event_id": event_id,
                    "event_type": event.get("type"),
                    "reason": why,
                    "at": workflow.now().isoformat(),
                }
            )
            self.memory.append(
                {"event_type": event.get("type"), "reason": why}
            )
            workflow.logger.info("[POLICY] %s logged-only: %s", event_id, why)
            return

        self.events.append(event)

        workflow.logger.info(
            "[EVENT] %s received %s (%s)",
            self.order_id,
            event.get("type"),
            event_id,
        )

    @workflow.signal
    async def instruction(self, text: str) -> None:
        """Operator guidance: honored by the next decision."""
        self.instructions.append(text)

        workflow.logger.info(
            "[INSTRUCTION] added (total %d)", len(self.instructions)
        )

    @workflow.signal
    async def pause(self) -> None:
        if self.terminal:
            return

        self.paused = True

        workflow.logger.info("[CONTROL] paused by operator")

    @workflow.signal
    async def resume(self) -> None:
        self.paused = False

        workflow.logger.info("[CONTROL] resumed by operator")
