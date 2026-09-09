export const API = "http://localhost:8000";

export type RunStatus = {
  order_id: string;
  status: {
    events_processed: number;
    events_queued: number;
    actions_taken: number;
    wakeups: number;
    instructions: number;
    paused: boolean;
    terminal: boolean;
  };
};

export async function createRun(orderId: string): Promise<Response> {
  return fetch(`${API}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order_id: orderId }),
  });
}

export async function injectEvent(
  orderId: string,
  eventId: string,
  type: string,
): Promise<Response> {
  return fetch(`${API}/runs/${orderId}/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_id: eventId,
      type,
      payload: {},
    }),
  });
}

export async function getStatus(
  orderId: string,
): Promise<RunStatus | null> {
  const res = await fetch(`${API}/runs/${orderId}`);
  return res.ok ? res.json() : null;
}