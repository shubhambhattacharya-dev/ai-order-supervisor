from temporalio import workflow
from logging_setup import setup_logging


@workflow.defn
class OrderSupervisorWorkflow:
    def __init__(self):
        self.events: list[dict] = []
        self.processed_event_ids: set[str] = set()
        self.terminal = False

    @workflow.run
    async def run(self, order_id: str) -> str:
        workflow.logger.info(
            "Order supervisor started",
            extra={"order_id": order_id},
        )

        try:
            while not self.terminal:
               
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

                    workflow.logger.info(
                        "Processing order event",
                        extra={
                            "order_id": order_id,
                            "event_id": event_id,
                            "event_type": event_type,
                        },
                    )

                  
                    workflow.logger.info(
                        "Agent would decide here",
                        extra={
                            "order_id": order_id,
                            "event_type": event_type,
                        },
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

                if self.terminal:
                    break

              
                await workflow.wait_condition(
                    lambda: len(self.events) > 0 or self.terminal
                )

            workflow.logger.info(
                "Order supervisor completed",
                extra={"order_id": order_id},
            )

            return f"Order {order_id} supervisor completed"

        except Exception:
            workflow.logger.exception(
                "Order supervisor failed",
                extra={"order_id": order_id},
            )
            raise

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