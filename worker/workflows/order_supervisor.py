import asyncio
import contextlib
import json
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class OrderSupervisorWorkflow:
    def __init__(self):
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

    @workflow.run
    async def run(self, order_id: str) -> str:
        workflow.logger.info(
            "Order supervisor started",
            extra={"order_id": order_id},
        )

        try:
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
                "Final output generated",
                extra={
                    "order_id": order_id,
                    "summary": report["summary"],
                },
            )

            return json.dumps(report)

        except asyncio.CancelledError:
            workflow.logger.info(
                "Order supervisor terminated by operator",
                extra={
                    "order_id": order_id,
                    "events_processed": len(self.processed_event_ids),
                    "actions_taken": len(self.actions_taken),
                },
            )
            raise

        except Exception:
            workflow.logger.exception(
                "Order supervisor failed",
                extra={"order_id": order_id},
            )
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
                    "Order reached terminal state",
                    extra={
                        "order_id": order_id,
                        "event_type": event_type,
                    },
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

        # Add the event to the timeline.
        self.timeline.append(
            {
                "type": "event",
                "event_id": event["event_id"],
                "event_type": event_type,
            }
        )

        # Add important event information to memory.
        self.memory.append(
            {
                "event_type": event_type,
                "reason": reason,
            }
        )

        if action == "no_action":
            self.timeline.append(
                {
                    "type": "decision",
                    "action": "no_action",
                    "reason": reason,
                }
            )
            return

        if action == "sleep_until":
            wake_minutes = int(
                decision.get("wake_after_minutes", 30)
            )

            self.wake_seconds = wake_minutes * 60

            self.timeline.append(
                {
                    "type": "decision",
                    "action": "sleep_until",
                    "wake_after_minutes": wake_minutes,
                    "reason": reason,
                }
            )
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
                "action": action,
                "reason": reason,
            }
        )

        self.memory.append(
            {
                "action": action,
                "reason": reason,
            }
        )

    async def _wait_for_event_or_wake(
        self,
        order_id: str,
    ) -> None:
        timer = None

        if self.wake_seconds is not None:
            timer = asyncio.create_task(
                workflow.sleep(self.wake_seconds)
            )
            self.wake_seconds = None

        await workflow.wait_condition(
            lambda: bool(self.events)
            or self.terminal
            or (timer is not None and timer.done())
        )

        if timer is None:
            return

        if timer.done():
            self.wakeups += 1

            self.events.append(
                {
                    "event_id": f"wakeup-{self.wakeups}",
                    "type": "SCHEDULED_WAKEUP",
                    "payload": {
                        "wakeup_number": self.wakeups,
                    },
                }
            )

            workflow.logger.info(
                "Scheduled wake-up fired",
                extra={
                    "order_id": order_id,
                    "wakeup_number": self.wakeups,
                },
            )

        else:
            timer.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await timer

    @workflow.query
    def status(self) -> dict:
        return {
            "events_queued": len(self.events),
            "events_processed": len(self.processed_event_ids),
            "actions_taken": len(self.actions_taken),
            "wakeups": self.wakeups,
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
                "Ignoring event without event_id",
                extra={"event": event},
            )
            return

        if event_id in self.processed_event_ids:
            workflow.logger.info(
                "Ignoring duplicate event",
                extra={"event_id": event_id},
            )
            return

        self.processed_event_ids.add(event_id)
        self.events.append(event)

        workflow.logger.info(
            "Order event received",
            extra={
                "event_id": event_id,
                "event_type": event.get("type"),
            },
        )

    @workflow.signal
    async def instruction(self, text: str) -> None:
        """Operator guidance: honored by the next decision."""
        self.instructions.append(text)

        workflow.logger.info(
            "Operator instruction received",
            extra={
                "instruction_count": len(self.instructions),
            },
        )

    @workflow.signal
    async def pause(self) -> None:
        if self.terminal:
            return

        self.paused = True

        workflow.logger.info(
            "Supervisor paused by operator"
        )

    @workflow.signal
    async def resume(self) -> None:
        self.paused = False

        workflow.logger.info(
            "Supervisor resumed by operator"
        )