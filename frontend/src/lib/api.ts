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
    memory: { event_type?: string; action?: string; reason?: string }[];
    timeline: TimelineEntry[];
  };
};

export type TimelineEntry = {
  type: "event" | "decision" | "action";
  event_id?: string;
  event_type?: string;
  action?: string;
  reason?: string;
  wake_after_minutes?: number;
};

export type RunSummary = {
  order_id: string;
  workflow_id: string;
  run_id: string;
  status: string;
  start_time: string | null;
};

export type Activity = {
  id: number;
  order_id: string;
  event_id: string | null;
  activity_type: string;
  action: string | null;
  reason: string | null;
  created_at: string;
};

export type Supervisor = {
  id: number;
  name: string;
  base_instruction: string;
  allowed_actions: string[];
  default_wake_minutes: number;
};

async function json<T>(request: Response | Promise<Response>): Promise<T | null> {
  try {
    const res = await request;
    return res.ok ? ((await res.json()) as T) : null;
  } catch {
    return null;
  }
}

export async function listRuns(): Promise<RunSummary[]> {
  const data = await json<{ runs: RunSummary[] }>(
    await fetch(`${API}/runs`, { cache: "no-store" }),
  );
  return data?.runs ?? [];
}

export async function createRun(
  orderId: string,
  supervisorId?: number,
): Promise<Response> {
  return fetch(`${API}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order_id: orderId, supervisor_id: supervisorId }),
  });
}

export async function getStatus(orderId: string): Promise<RunStatus | null> {
  return json<RunStatus>(
    await fetch(`${API}/runs/${orderId}`, { cache: "no-store" }),
  );
}

export async function getActivities(
  orderId: string,
): Promise<Activity[]> {
  const data = await json<{ activities: Activity[] }>(
    await fetch(`${API}/runs/${orderId}/activities`, { cache: "no-store" }),
  );
  return data?.activities ?? [];
}

export async function injectEvent(
  orderId: string,
  eventId: string,
  type: string,
  payload: string,
): Promise<Response> {
  return fetch(`${API}/runs/${orderId}/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_id: eventId,
      type,
      payload: payload ? JSON.parse(payload) : {},
    }),
  });
}

export async function addInstruction(
  orderId: string,
  text: string,
): Promise<Response> {
  return fetch(`${API}/runs/${orderId}/instruction`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export async function controlRun(
  orderId: string,
  action: "pause" | "resume" | "terminate",
): Promise<Response> {
  return fetch(`${API}/runs/${orderId}/${action}`, { method: "POST" });
}

export async function listSupervisors(): Promise<Supervisor[]> {
  return (await json<Supervisor[]>(
    await fetch(`${API}/supervisors`, { cache: "no-store" }),
  )) ?? [];
}

export async function createSupervisor(cfg: {
  name: string;
  base_instruction: string;
  allowed_actions: string[];
  default_wake_minutes: number;
}): Promise<Response> {
  return fetch(`${API}/supervisors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  });
}

export async function apiHealthy(): Promise<boolean> {
  try {
    const res = await fetch(`${API}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function apiErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const body = (await response.clone().json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : fallback;
  } catch {
    return fallback;
  }
}
