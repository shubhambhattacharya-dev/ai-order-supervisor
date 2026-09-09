"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  addInstruction, apiErrorMessage, controlRun, getDecisions,
  getFinal, getStatus, injectEvent, subscribeRun,
  type Decision, type FinalOutput, type RunStatus, type TimelineEntry,
} from "@/lib/api";
import StatusChip from "@/components/StatusChip";
import {
  Braces, CheckCircle2, ChevronRight, CirclePlay, Clock3, Cpu, FileText,
  Layers3, Leaf, Pause, Plus, RefreshCw, Send, Sparkles, Square,
  TriangleAlert, Zap,
} from "lucide-react";

const EVENT_TYPES = [
  "ORDER_CREATED", "PAYMENT_CONFIRMED", "PAYMENT_FAILED", "PAYMENT_DELAYED",
  "SHIPMENT_CREATED", "SHIPMENT_DELAYED", "DELIVERED", "REFUND_REQUESTED",
  "CUSTOMER_MESSAGE_RECEIVED", "NO_UPDATE_FOR_N_HOURS", "STATUS_UPDATE",
  "COMPLETED", "CANCELLED",
];

type Tab = "timeline" | "details" | "memory" | "final";
const TABS: { id: Tab; label: string }[] = [
  { id: "timeline", label: "Timeline & Activity" },
  { id: "details", label: "Order Details" },
  { id: "memory", label: "Memory" },
  { id: "final", label: "Final Output" },
];

export default function RunDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const [data, setData] = useState<RunStatus | null>(null);
  const [missing, setMissing] = useState(false);
  const [tab, setTab] = useState<Tab>("timeline");
  const [kindFilter, setKindFilter] = useState("all");
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [finalOut, setFinalOut] = useState<FinalOutput | null>(null);
  const [eventType, setEventType] = useState("SHIPMENT_DELAYED");
  const [payload, setPayload] = useState('{\n  "reason": "Weather delay at warehouse"\n}');
  const [payloadError, setPayloadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [toast, setToast] = useState<string | null>(null);
    const [confirmKill, setConfirmKill] = useState(false);
  const [nowMs, setNowMs] = useState<number | null>(null);
  const status = data?.status;

  const refresh = useCallback(async () => {
    const status = await getStatus(orderId);
    if (!status) { setMissing(true); return; }
    setMissing(false);
    setNowMs(Date.now());
    setData(status);
    setDecisions(await getDecisions(orderId));
  }, [orderId]);

  // Real-time: SSE pushes status the moment it changes; activities refetch on each push.
  /* eslint-disable react-hooks/set-state-in-effect -- syncing with the backend API is this effect's whole job */
  useEffect(() => {
    refresh();
    const close = subscribeRun(orderId, () => { setMissing(false); refresh(); });
    return close;
  }, [orderId, refresh]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Fallback poll in case the SSE connection drops.
  useEffect(() => {
    const timer = setInterval(() => { if (!document.hidden) refresh(); }, 10000);
    return () => clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (tab === "final" && !finalOut && status?.terminal) {
      getFinal(orderId).then((f) => setFinalOut(f));
    }
  }, [tab, status?.terminal, finalOut, orderId]);

  function flash(msg: string) {
    setToast(msg);
    window.setTimeout(() => setToast(null), 2600);
  }

  async function sendEvent() {
    let parsed: Record<string, unknown> = {};
    try { parsed = payload.trim() ? JSON.parse(payload) : {}; }
    catch { setPayloadError("Use valid JSON before sending this event."); return; }
    setPayloadError(null); setBusy(true);
    try {
      const result = await injectEvent(orderId, `evt-${Date.now()}`, eventType, JSON.stringify(parsed));
      flash(result.ok ? `${eventType.replace(/_/g, " ")} sent` : await apiErrorMessage(result, `Inject failed (${result.status})`));
      if (result.ok) refresh();
    } catch { flash("Backend is not reachable."); }
    setBusy(false);
  }

  async function sendInstruction() {
    if (!instruction.trim() || busy) return;
    setBusy(true);
    try {
      const result = await addInstruction(orderId, instruction.trim());
      flash(result.ok ? "Instruction added — honored by the next decision" : await apiErrorMessage(result, `Instruction failed (${result.status})`));
      if (result.ok) { setInstruction(""); refresh(); }
    } catch { flash("Backend is not reachable."); }
    setBusy(false);
  }

  async function control(action: "pause" | "resume" | "terminate") {
    setConfirmKill(false);
    try {
      const result = await controlRun(orderId, action);
      flash(result.ok ? `Run ${action}d` : await apiErrorMessage(result, `${action} failed (${result.status})`));
      if (result.ok && action === "terminate") setTab("final");
      refresh();
    } catch { flash("Backend is not reachable."); }
  }

  if (missing) {
    return (
      <div className="rounded-2xl border border-line bg-panel p-10 text-center text-sm text-sub">
        Run <span className="font-mono text-txt">{orderId}</span> was not found. Start
        a run first, or open a run from the list.
      </div>
    );
  }

  const entries: TimelineEntry[] = [...(status?.timeline ?? [])].reverse();
  const shown = kindFilter === "all" ? entries : entries.filter((e) => e.type === kindFilter);
  const totalTokens = decisions.reduce((sum, d) => sum + d.prompt_tokens + d.completion_tokens, 0);
  const runningFor = (() => {
    if (!nowMs || !status?.started_at) return "—";
    const mins = Math.max(0, Math.round((nowMs - new Date(status.started_at).getTime()) / 60000));
    return mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}m` : `${mins} min`;
  })();

  const chip = !status ? "LOADING"
    : status.terminal
      ? ([...status.timeline].reverse().find((e) => e.type === "event")?.event_type === "COMPLETED" ? "COMPLETED" : "TERMINATED")
      : status.paused ? "PAUSED"
      : status.sleeping ? "SLEEPING"
      : "RUNNING";

  return (
    <div className="space-y-5">
      {/* Breadcrumb */}
      <p className="text-sm text-sub">
        Runs <span className="mx-2 text-line">›</span>
        <span className="font-mono">{orderId}</span>
      </p>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand/15 text-brand">
            <Leaf size={24} fill="currentColor" />
          </span>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">Order {orderId}</h1>
              <StatusChip label={chip} />
            </div>
            <p className="mt-0.5 text-sm text-sub">AI supervisor is monitoring this order</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {status?.sleeping && status.next_wake_at && (
            <div className="rounded-xl border border-line bg-panel px-4 py-2">
              <p className="text-xs text-sub">Next wake-up</p>
              <p className="text-sm font-medium">
                {new Date(status.next_wake_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </p>
            </div>
          )}
          <button onClick={() => control("pause")} disabled={!status || status.paused || status.terminal}
            className="control-button"><Pause size={15} /> Pause</button>
          <button onClick={() => control("resume")} disabled={!status || !status.paused || status.terminal}
            className="control-button control-primary"><CirclePlay size={16} /> Resume</button>
          <button onClick={() => setConfirmKill(true)} disabled={!status || status.terminal}
            className="control-button control-danger"><Square size={14} fill="currentColor" /> Terminate</button>
        </div>
      </div>

      {status?.sleeping && status.next_wake_at && (
        <p className="text-sm text-sub">
          Waiting for new events or scheduled wake-up — the durable timer fires on its
          own, even if this server restarts.
        </p>
      )}

      {toast && (
        <div className="rounded-lg border border-brand/30 bg-brandsoft px-4 py-2 text-sm text-brand">{toast}</div>
      )}

      {confirmKill && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger bg-dangersoft px-4 py-3 text-sm">
          <span className="flex items-center gap-2 text-danger">
            <TriangleAlert size={16} /> Terminate this run? A final summary is still produced.
          </span>
          <span className="flex gap-2">
            <button onClick={() => control("terminate")} className="rounded-lg bg-danger px-3 py-1.5 text-white">Terminate run</button>
            <button onClick={() => setConfirmKill(false)} className="rounded-lg border border-line px-3 py-1.5">Cancel</button>
          </span>
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
        {([
          ["Events processed", status?.events_processed ?? "—", "Total events handled", Cpu],
          ["Actions taken", status?.actions_taken ?? "—", "Automated actions executed", Zap],
          ["Wake-ups", status?.wakeups ?? "—", "Scheduled wake-ups fired", Clock3],
          ["Tokens used", totalTokens ? `${(totalTokens / 1000).toFixed(1)}k` : "0", "Total tokens (LLM)", Layers3],
          ["Running for", runningFor, status?.started_at ? `since ${new Date(status.started_at).toLocaleString()}` : "—", Leaf],
        ] as const).map(([label, value, capText, Icon]) => (
          <section key={label} className="metric-card">
            <span className="metric-icon blue"><Icon size={22} /></span>
            <div className="min-w-0">
              <p className="text-sm text-sub">{label}</p>
              <p className="text-2xl font-semibold tracking-tight">{String(value)}</p>
              <p className="mt-0.5 truncate text-xs text-sub">{capText}</p>
            </div>
          </section>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1 rounded-xl border border-line bg-panel p-1">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`rounded-lg px-4 py-1.5 text-sm transition-colors ${
                tab === t.id ? "bg-brandsoft font-medium text-brand" : "text-sub hover:text-txt"
              }`}>
              {t.label}
            </button>
          ))}
        </div>
        {tab === "timeline" && (
          <select value={kindFilter} onChange={(e) => setKindFilter(e.target.value)}
            className="rounded-lg border border-line bg-panel px-3 py-1.5 text-xs text-sub outline-none">
            <option value="all">All events</option>
            <option value="event">Events</option>
            <option value="decision">Decisions</option>
            <option value="action">Actions</option>
          </select>
        )}
      </div>

      {tab === "timeline" && (
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.95fr)]">
          <section className="panel overflow-hidden">
            {shown.length === 0 ? (
              <p className="p-8 text-center text-sm text-sub">
                Nothing here yet — inject an event to wake the agent.
              </p>
            ) : (
              <ol className="px-6 py-4">
                {shown.map((entry, i) => {
                  const kind = entry.type === "decision" ? "decision" : entry.type === "action" ? "action" : "event";
                  const decisionInfo = kind === "decision"
                    ? decisions.filter((d) => d.action === entry.action).reverse()[
                        entries.filter((e) => e.type === "decision" && e.action === entry.action).length - 1 -
                        [...entries].slice(0, i).filter((e) => e.type === "decision" && e.action === entry.action).length
                      ]
                    : undefined;
                  const isSleep = entry.action === "sleep_until";
                  const Icon = kind === "decision"
                    ? (isSleep ? Clock3 : Sparkles)
                    : kind === "action" ? Send
                    : entry.event_type?.includes("DELAY") ? TriangleAlert
                    : entry.event_type?.includes("PAYMENT") ? CheckCircle2
                    : FileText;
                  return (
                    <li key={`${entry.type}-${i}-${entry.event_id ?? entry.action}`} className="timeline-item">
                      <time>{status?.started_at ? new Date(new Date(status.started_at).getTime() + i * 60000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Now"}</time>
                      <div className={`timeline-dot ${kind}`}><Icon size={17} /></div>
                      <div className="min-w-0 flex-1 pb-6">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="font-medium">
                            {kind === "event"
                              ? `Event received: ${entry.event_type?.toLowerCase()}`
                              : isSleep ? "Supervisor sleeping"
                              : kind === "decision" ? `Agent decision: ${entry.action}`
                              : `Action executed: ${entry.action}`}
                          </p>
                          <span className={`event-tag ${kind}`}>
                            {isSleep ? "STATE" : kind.toUpperCase()}
                          </span>
                        </div>
                        <p className="mt-1 text-sm text-sub">{entry.reason ?? "No additional detail recorded."}</p>
                        {isSleep && status?.next_wake_at && (
                          <div className="mt-2 rounded-lg border border-line bg-panelsoft px-3 py-2 text-xs">
                            <p><span className="text-sub">Reason:</span> {entry.reason ?? "waiting"}</p>
                            <p><span className="text-sub">Wake-up at:</span>{" "}
                              {new Date(status.next_wake_at).toLocaleString()}</p>
                          </div>
                        )}
                        {kind === "decision" && decisionInfo && !isSleep && (
                          <div className="mt-2 rounded-lg border border-line bg-panelsoft px-3 py-2 text-xs">
                            <p><span className="text-sub">Provider:</span> {decisionInfo.provider ?? "—"}</p>
                            <p><span className="text-sub">Tokens:</span> {decisionInfo.prompt_tokens} in / {decisionInfo.completion_tokens} out</p>
                            <p><span className="text-sub">Triggered by:</span> {decisionInfo.event_id ?? "—"}</p>
                            {decisionInfo.trace_url && (
                              <p><span className="text-sub">Trace:</span>{" "}
                                <a href={decisionInfo.trace_url} target="_blank" rel="noreferrer" className="text-brand hover:underline">open in Langfuse</a></p>
                            )}
                          </div>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>

          <aside className="space-y-4">
            <section className="panel p-5">
              <div className="mb-3 flex items-start gap-3">
                <span className="text-brand"><Send size={22} /></span>
                <div>
                  <h2 className="text-base font-semibold">Inject Event</h2>
                  <p className="text-xs text-sub">Send a new event to this running supervisor</p>
                </div>
              </div>
              <label className="field-label">Event type</label>
              <select value={eventType} onChange={(e) => setEventType(e.target.value)} className="field-control">
                {EVENT_TYPES.map((t) => <option key={t} value={t}>{t.toLowerCase()}</option>)}
              </select>
              <label className="field-label mt-3">Event payload (JSON)</label>
              <textarea value={payload} onChange={(e) => setPayload(e.target.value)} rows={4} spellCheck={false}
                className="field-control font-mono text-xs" />
              {payloadError && <p className="mt-1 text-xs text-danger">{payloadError}</p>}
              <button onClick={sendEvent} disabled={busy}
                className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 text-sm font-medium text-white hover:bg-brandhover disabled:opacity-50">
                <Send size={15} /> {busy ? "Sending…" : "Send signal"}
              </button>
            </section>

            <section className="panel p-5">
              <div className="mb-3 flex items-start gap-3">
                <span className="text-sub"><Braces size={22} /></span>
                <div>
                  <h2 className="text-base font-semibold">Add Instruction</h2>
                  <p className="text-xs text-sub">Give the supervisor an additional instruction</p>
                </div>
              </div>
              <input value={instruction} onChange={(e) => setInstruction(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendInstruction()}
                placeholder="e.g. Prioritize customer communication…"
                className="field-control" />
              <button onClick={sendInstruction} disabled={busy || !instruction.trim()}
                className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brandhover disabled:opacity-50">
                <Plus size={15} /> Add instruction
              </button>
            </section>

            <section className="panel p-5">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-sub"><Layers3 size={22} /></span>
                  <h2 className="text-base font-semibold">Memory Summary</h2>
                </div>
                <button onClick={refresh} className="text-sub hover:text-brand" aria-label="Refresh memory">
                  <RefreshCw size={15} />
                </button>
              </div>
              <p className="text-sm leading-6 text-sub">
                {(status?.memory ?? []).slice(-4).map((m) => m.reason).filter(Boolean).join(" ")
                  || "The compact memory builds as events arrive."}
              </p>
              <button onClick={() => setTab("memory")}
                className="mt-3 flex items-center gap-1 text-xs text-brand hover:underline">
                View full memory <ChevronRight size={13} />
              </button>
            </section>
          </aside>
        </div>
      )}

      {tab === "details" && status && (
        <section className="panel overflow-hidden">
          <table className="w-full text-sm">
            <tbody>
              {[
                ["Order ID", orderId],
                ["Workflow ID", `order-supervisor-${orderId}`],
                ["State", chip],
                ["Started", status.started_at ? new Date(status.started_at).toLocaleString() : "—"],
                ["Events processed", String(status.events_processed)],
                ["Actions taken", String(status.actions_taken)],
                ["Scheduled wake-ups", String(status.wakeups)],
                ["Instructions", String(status.instructions)],
                ["Currently", status.sleeping && status.next_wake_at ? `sleeping until ${new Date(status.next_wake_at).toLocaleString()}` : status.paused ? "paused" : status.terminal ? "completed" : "running"],
              ].map(([k, v]) => (
                <tr key={k} className="border-b border-line last:border-0">
                  <td className="w-56 px-5 py-3 text-sub">{k}</td>
                  <td className="px-5 py-3 font-medium">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {tab === "memory" && status && (
        <section className="panel p-5">
          <h2 className="mb-3 text-sm font-medium">
            Compact memory ({status.memory.length} entries)
          </h2>
          {status.memory.length === 0 ? (
            <p className="text-sm text-sub">Memory builds as events arrive.</p>
          ) : (
            <ul className="space-y-2">
              {[...status.memory].reverse().map((m, i) => (
                <li key={i} className="rounded-lg border border-line bg-panelsoft px-3 py-2 text-sm">
                  <span className="font-mono text-xs text-brand">
                    {m.event_type ?? m.action}
                  </span>
                  {m.reason && <span className="text-sub"> — {m.reason}</span>}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "final" && (
        <section className="panel p-6">
          {finalOut ? (
            <div className="space-y-5">
              <div>
                <h2 className="mb-1 text-sm font-medium text-sub">Summary</h2>
                <p className="leading-6">{finalOut.summary}</p>
              </div>
              <div>
                <h2 className="mb-1 text-sm font-medium text-sub">Actions taken</h2>
                <ul className="list-disc space-y-1 pl-5 text-sm">
                  {(finalOut.actions_taken ?? []).map((a, i) => <li key={i}>{a}</li>)}
                </ul>
              </div>
              <div>
                <h2 className="mb-1 text-sm font-medium text-sub">Key learnings</h2>
                <ul className="list-disc space-y-1 pl-5 text-sm">
                  {(finalOut.learnings ?? []).map((l, i) => <li key={i}>{l}</li>)}
                </ul>
              </div>
              <div>
                <h2 className="mb-1 text-sm font-medium text-sub">Feedback</h2>
                <ul className="list-disc space-y-1 pl-5 text-sm">
                  {(finalOut.feedback ?? []).map((f, i) => <li key={i}>{f}</li>)}
                </ul>
              </div>
            </div>
          ) : status?.terminal ? (
            <p className="text-sm text-sub">
              Final output not persisted for this run — it was completed before the
              persistence layer existed. New runs store it automatically.
            </p>
          ) : (
            <p className="text-sm text-sub">
              The final output appears here once the run completes.
            </p>
          )}
        </section>
      )}
    </div>
  );
}

