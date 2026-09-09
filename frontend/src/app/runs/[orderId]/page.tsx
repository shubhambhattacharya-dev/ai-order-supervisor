"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Activity, addInstruction, apiErrorMessage, controlRun, getActivities, getStatus, injectEvent, RunStatus, TimelineEntry } from "@/lib/api";
import StatusChip from "@/components/StatusChip";
import { Bell, CheckCircle2, CirclePlay, Clock3, Database, FileText, Layers3, Pause, Plus, RefreshCw, Send, Sparkles, Square, TriangleAlert, Zap } from "lucide-react";

const EVENT_TYPES = ["STATUS_UPDATE", "PAYMENT_DELAYED", "SHIPMENT_DELAYED", "FULFILLMENT_DELAYED", "CUSTOMER_MESSAGE_RECEIVED", "REFUND_REQUESTED", "COMPLETED", "CANCELLED"];
const DEMO_STATUS: RunStatus = {
  order_id: "ORD-1042",
  status: {
    events_processed: 12, events_queued: 0, actions_taken: 3, wakeups: 2, instructions: 1, paused: false, terminal: false,
    memory: [
      { event_type: "ORDER_CREATED", reason: "Order is created and payment confirmed." },
      { action: "message_logistics_team", reason: "Logistics team notified for preparation." },
      { event_type: "SHIPMENT_DELAYED", reason: "Shipment is delayed due to weather." },
      { action: "sleep_until", reason: "Monitoring until 14:30 to recheck status." },
    ],
    timeline: [
      { type: "event", event_type: "ORDER_CREATED", reason: "Order created in the system" },
      { type: "event", event_type: "PAYMENT_CONFIRMED", reason: "Payment confirmed successfully" },
      { type: "decision", action: "message_logistics_team", reason: "Payment confirmed, notify logistics for preparation" },
      { type: "action", action: "message_logistics_team", reason: "Message sent to logistics team" },
      { type: "event", event_type: "SHIPMENT_DELAYED", reason: "Shipment delayed due to weather" },
      { type: "action", action: "sleep_until", reason: "Woke up to check order status", wake_after_minutes: 60 },
      { type: "event", event_type: "INTERNAL_NOTE", reason: "Monitoring for shipment updates" },
    ],
  },
};
const labels: Record<string, string> = { event: "EVENT", decision: "DECISION", action: "ACTION" };
const timeFor = (index: number) => ["12:04", "11:58", "11:58", "11:59", "10:23", "09:00", "08:45"][index] ?? "Now";

export default function RunDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const [data, setData] = useState<RunStatus | null>(null);
  const [missing, setMissing] = useState(false);
  const [demoMode, setDemoMode] = useState(false);
  const [eventType, setEventType] = useState("SHIPMENT_DELAYED");
  const [payload, setPayload] = useState('{\n  "reason": "Weather delay at warehouse",\n  "location": "DEL",\n  "estimated_delay_hours": 6\n}');
  const [payloadError, setPayloadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [activities, setActivities] = useState<Activity[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [confirmKill, setConfirmKill] = useState(false);

  const refresh = useCallback(async () => {
    const status = await getStatus(orderId);
    if (status) {
      setData(status); setDemoMode(false); setMissing(false); setActivities(await getActivities(orderId));
    } else if (orderId.toUpperCase() === "ORD-1042") {
      setData(DEMO_STATUS); setDemoMode(true); setMissing(false); setActivities([]);
    } else setMissing(true);
  }, [orderId]);
  useEffect(() => { refresh(); const timer = setInterval(() => !document.hidden && refresh(), 5000); return () => clearInterval(timer); }, [refresh]);
  function flash(message: string) { setToast(message); window.setTimeout(() => setToast(null), 2600); }
  function appendDemo(entry: TimelineEntry, memoryReason?: string) {
    setData((current) => current ? { ...current, status: { ...current.status, events_processed: current.status.events_processed + (entry.type === "event" ? 1 : 0), actions_taken: current.status.actions_taken + (entry.type === "action" ? 1 : 0), timeline: [...current.status.timeline, entry], memory: memoryReason ? [...current.status.memory, { event_type: entry.event_type, action: entry.action, reason: memoryReason }] : current.status.memory } } : current);
  }
  async function sendEvent() {
    let parsed: Record<string, unknown> = {};
    try { parsed = payload.trim() ? JSON.parse(payload) : {}; } catch { setPayloadError("Use valid JSON before sending this event."); return; }
    setPayloadError(null); setBusy(true);
    if (demoMode) { appendDemo({ type: "event", event_type: eventType, reason: String(parsed.reason ?? "Event injected from the console") }, String(parsed.reason ?? "Event injected from the console")); setBusy(false); flash(`${eventType.replaceAll("_", " ")} received`); return; }
    try { const result = await injectEvent(orderId, `evt-${Date.now()}`, eventType, payload); flash(result.ok ? `Event ${eventType} sent` : await apiErrorMessage(result, `Inject failed (${result.status})`)); if (result.ok) refresh(); } catch { flash("Backend is not reachable."); }
    setBusy(false);
  }
  async function sendInstruction() {
    if (!instruction.trim() || busy) return; setBusy(true);
    if (demoMode) { appendDemo({ type: "event", event_type: "INSTRUCTION", reason: instruction.trim() }, instruction.trim()); setData((current) => current ? { ...current, status: { ...current.status, instructions: current.status.instructions + 1 } } : current); setInstruction(""); setBusy(false); flash("Instruction added to this run"); return; }
    try { const result = await addInstruction(orderId, instruction.trim()); flash(result.ok ? "Instruction added to this run" : await apiErrorMessage(result, `Instruction failed (${result.status})`)); if (result.ok) { setInstruction(""); refresh(); } } catch { flash("Backend is not reachable."); }
    setBusy(false);
  }
  async function control(action: "pause" | "resume" | "terminate") {
    setConfirmKill(false);
    if (demoMode) { setData((current) => current ? { ...current, status: { ...current.status, paused: action === "pause", terminal: action === "terminate" } } : current); flash(`Run ${action === "terminate" ? "terminated" : `${action}d`}`); return; }
    try { const result = await controlRun(orderId, action); flash(result.ok ? `Run ${action}d` : await apiErrorMessage(result, `${action} failed (${result.status})`)); if (result.ok) refresh(); } catch { flash("Backend is not reachable."); }
  }
  if (missing) return <div className="rounded-2xl border border-line bg-panel p-10 text-center text-sm text-sub">Run <span className="font-mono text-txt">{orderId}</span> was not found. Start a run first, or open <span className="font-mono text-txt">ORD-1042</span> to view the interactive demo.</div>;
  const status = data?.status; const timeline = [...(status?.timeline ?? [])].reverse();
  const chip = !status ? "LOADING" : status.terminal ? "TERMINATED" : status.paused ? "PAUSED" : "SLEEPING";
  const metrics = [[FileText, "Events processed", status?.events_processed ?? "—", "Total events handled", "blue"], [Zap, "Actions taken", status?.actions_taken ?? "—", "Automated actions executed", "green"], [Clock3, "Wake-ups", status?.wakeups ?? "—", "Scheduled wake-ups fired", "teal"], [Layers3, "Tokens", demoMode ? "4.1k" : "—", "Total tokens used (LLM)", "blue"]] as const;
  return <div className="space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="mb-3 text-sm text-sub">Runs <span className="mx-2 text-line">›</span> <span className="font-mono">{orderId}</span></p><div className="flex items-center gap-3"><h1 className="text-3xl font-semibold tracking-tight">Order {orderId}</h1><StatusChip label={chip} /></div><p className="mt-1 text-base text-sub">AI supervisor is monitoring this order <span className="mx-2">•</span> next wake-up 14:30</p></div><div className="flex flex-wrap items-center gap-2 pt-1"><button onClick={() => control("pause")} disabled={!status || status.paused || status.terminal} className="control-button"><Pause size={16}/> Pause</button><button onClick={() => control("resume")} disabled={!status || !status.paused || status.terminal} className="control-button control-primary"><CirclePlay size={17}/> Resume</button><button onClick={() => setConfirmKill(true)} disabled={!status || status.terminal} className="control-button control-danger"><Square size={14} fill="currentColor"/> Terminate</button></div></div>
    {demoMode && <div className="flex items-center gap-2 rounded-lg border border-brand/30 bg-brandsoft/50 px-3 py-2 text-xs text-brand"><CheckCircle2 size={14}/> Interactive demo data is active because no live {orderId} run is available.</div>}
    {toast && <div role="status" className="rounded-lg border border-brand/30 bg-brandsoft px-4 py-2 text-sm text-brand">{toast}</div>}
    {confirmKill && <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger bg-dangersoft px-4 py-3 text-sm"><span className="flex items-center gap-2 text-danger"><TriangleAlert size={16}/> Terminate this run? This cannot be undone.</span><span className="flex gap-2"><button onClick={() => control("terminate")} className="rounded-lg bg-danger px-3 py-1.5 text-white">Terminate run</button><button onClick={() => setConfirmKill(false)} className="rounded-lg border border-line px-3 py-1.5">Cancel</button></span></div>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{metrics.map(([Icon, label, value, caption, tone]) => <section key={label} className="metric-card"><span className={`metric-icon ${tone}`}><Icon size={24}/></span><div><p className="text-sm text-sub">{label}</p><p className="mt-1 text-3xl font-semibold tracking-tight">{value}</p><p className="mt-1 text-xs text-sub">{caption}</p></div></section>)}</div>
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(340px,0.95fr)]">
      <section className="panel overflow-hidden"><div className="flex items-center justify-between border-b border-line px-6 py-4"><h2 className="text-lg font-semibold">Timeline &amp; Activity</h2><button className="control-button py-1.5 text-xs">All events <Bell size={14}/></button></div><ol className="px-6 py-3">{timeline.map((entry, index) => { const kind = entry.type === "decision" ? "decision" : entry.type === "action" ? "action" : "event"; const Icon = kind === "decision" ? Sparkles : kind === "action" ? Send : entry.event_type?.includes("DELAY") ? TriangleAlert : entry.event_type?.includes("PAYMENT") ? CheckCircle2 : FileText; return <li key={`${entry.type}-${index}-${entry.event_type ?? entry.action}`} className="timeline-item"><time>{timeFor(index)}</time><div className={`timeline-dot ${kind}`}><Icon size={18}/></div><div className="min-w-0 flex-1 pb-5"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium">{kind === "event" ? `Event received: ${entry.event_type?.toLowerCase()}` : kind === "decision" ? `Agent decision: ${entry.action}` : `Action executed: ${entry.action}`}</p><span className={`event-tag ${kind}`}>{labels[kind]}</span></div><p className="mt-1 text-sm text-sub">{entry.reason ?? "No additional detail recorded."}</p>{entry.wake_after_minutes != null && <p className="mt-1 text-xs text-sub">Wake-up scheduled in {entry.wake_after_minutes} minutes</p>}</div></li>; })}</ol>{activities.length > 0 && <details className="mx-6 mb-5 border-t border-line pt-3"><summary className="cursor-pointer text-xs text-sub">Persisted activity log ({activities.length})</summary></details>}</section>
      <aside className="space-y-4"><section className="panel p-5"><div className="mb-4 flex items-start gap-3"><span className="text-brand"><Send size={24}/></span><div><h2 className="text-lg font-semibold">Inject Event</h2><p className="text-sm text-sub">Send a new event to this running supervisor</p></div></div><label className="field-label">Event type</label><select value={eventType} onChange={(event) => setEventType(event.target.value)} className="field-control">{EVENT_TYPES.map((type) => <option key={type} value={type}>{type.toLowerCase()}</option>)}</select><label className="field-label mt-3">Event payload (JSON)</label><textarea value={payload} onChange={(event) => setPayload(event.target.value)} rows={5} spellCheck={false} className="field-control font-mono text-xs leading-6"/>{payloadError && <p className="mt-1 text-xs text-danger">{payloadError}</p>}<button onClick={sendEvent} disabled={busy} className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 text-sm font-medium text-white hover:bg-brandhover disabled:opacity-50"><Send size={16}/> {busy ? "Sending…" : "Send signal"}</button></section>
      <section className="panel p-5"><div className="mb-3 flex items-start gap-3"><FileText className="text-sub" size={22}/><div><h2 className="text-lg font-semibold">Add Instruction</h2><p className="text-sm text-sub">Give the supervisor an additional instruction</p></div></div><div className="flex gap-2"><input value={instruction} onChange={(event) => setInstruction(event.target.value)} onKeyDown={(event) => event.key === "Enter" && sendInstruction()} placeholder="e.g. if delayed again, escalate immediately" className="field-control min-w-0 flex-1"/><button onClick={sendInstruction} disabled={!instruction.trim() || busy} className="control-button shrink-0"><Plus size={16}/> Add</button></div></section>
      <section className="panel p-5"><div className="mb-3 flex items-center justify-between"><div className="flex items-center gap-3"><Database size={22} className="text-sub"/><h2 className="text-lg font-semibold">Memory Summary</h2></div><button onClick={refresh} className="text-sub hover:text-brand" aria-label="Refresh memory"><RefreshCw size={16}/></button></div><p className="text-sm leading-6 text-sub">{(status?.memory ?? []).slice(-4).map((memory) => memory.reason).filter(Boolean).join(" ") || "The compact memory builds as events arrive."}</p></section></aside>
    </div>
  </div>;
}
