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
    sleeping?: boolean;
    next_wake_at?: string | null;
    started_at?: string | null;
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
    fetch(`${API}/runs`, { cache: "no-store" }),
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
  }).catch(() => new Response(null, { status: 503 }));
}

export async function getStatus(orderId: string): Promise<RunStatus | null> {
  return json<RunStatus>(
    fetch(`${API}/runs/${orderId}`, { cache: "no-store" }),
  );
}

export async function getActivities(
  orderId: string,
): Promise<Activity[]> {
  const data = await json<{ activities: Activity[] }>(
    fetch(`${API}/runs/${orderId}/activities`, { cache: "no-store" }),
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
  }).catch(() => new Response(null, { status: 503 }));
}

export async function addInstruction(
  orderId: string,
  text: string,
): Promise<Response> {
  return fetch(`${API}/runs/${orderId}/instruction`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  }).catch(() => new Response(null, { status: 503 }));
}

export async function controlRun(
  orderId: string,
  action: "pause" | "resume" | "terminate",
): Promise<Response> {
  return fetch(`${API}/runs/${orderId}/${action}`, { method: "POST" })
    .catch(() => new Response(null, { status: 503 }));
}

export async function listSupervisors(): Promise<Supervisor[]> {
  return (await json<Supervisor[]>(
    fetch(`${API}/supervisors`, { cache: "no-store" }),
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
  }).catch(() => new Response(null, { status: 503 }));
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

export type Decision = {
  id: number;
  order_id: string;
  event_id: string | null;
  provider: string | null;
  model: string | null;
  action: string | null;
  reason: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  fallback_used: boolean;
  trace_url?: string | null;
  created_at: string;
};

export async function getDecisions(orderId: string): Promise<Decision[]> {
  const data = await json<{ decisions: Decision[] }>(
    fetch(`${API}/runs/${orderId}/decisions`, { cache: "no-store" }),
  );
  return data?.decisions ?? [];
}

export type FinalOutput = {
  order_id: string;
  summary: string;
  actions_taken: string[];
  learnings: string[];
  feedback: string[];
  created_at: string;
};

export async function getFinal(orderId: string): Promise<FinalOutput | null> {
  return json<FinalOutput>(
    fetch(`${API}/runs/${orderId}/final`, { cache: "no-store" }),
  );
}

export type AnalyticsData = {
  decisions: (Decision & { order_id: string })[];
  total_tokens: number;
  avg_latency_ms: number;
  fallback_count: number;
};

export async function getAnalytics(): Promise<AnalyticsData | null> {
  return json<AnalyticsData>(
    fetch(`${API}/analytics/decisions`, { cache: "no-store" }),
  );
}

export type Observability = {
  enabled: boolean;
  host: string | null;
  traces_url: string | null;
};

export async function getObservability(): Promise<Observability | null> {
  return json<Observability>(
    fetch(`${API}/observability`, { cache: "no-store" }),
  );
}

/** Live push for one run's status (Server-Sent Events). Returns a closer. */
export function subscribeRun(
  orderId: string,
  onStatus: (status: RunStatus["status"]) => void,
): () => void {
  const es = new EventSource(`${API}/runs/${orderId}/stream`);
  es.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as {
        order_id: string;
        status: RunStatus["status"] | null;
      };
      if (payload.status && Object.keys(payload.status).length > 0) {
        onStatus(payload.status);
      }
    } catch {
      // malformed frame — the next one will be good
    }
  };
  return () => es.close();
}

/** Live push of the cross-run decisions feed for the Analytics page. */
export function subscribeDecisions(
  onData: (data: AnalyticsData) => void,
): () => void {
  const es = new EventSource(`${API}/analytics/stream`);
  es.onmessage = (event) => {
    try {
      onData(JSON.parse(event.data) as AnalyticsData);
    } catch {
      // malformed frame — skip
    }
  };
  return () => es.close();
}
