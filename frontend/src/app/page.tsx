"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  createRun,
  listRuns,
  listSupervisors,
  type RunSummary,
  type Supervisor,
} from "@/lib/api";
import StatusChip from "@/components/StatusChip";

export default function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
  const [orderId, setOrderId] = useState("");
  const [supervisorId, setSupervisorId] = useState<number | undefined>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setRuns(await listRuns());
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    listSupervisors().then((s) => {
      setSupervisors(s);
      if (s.length > 0) setSupervisorId(s[0].id);
    });
    return () => clearInterval(t);
  }, [refresh]);

  async function start() {
    setError(null);
    const id = orderId.trim();
    if (!id || busy) return;

    setBusy(true);
    const res = await createRun(id, supervisorId);
    setBusy(false);

    if (res.ok || res.status === 409) {
      setOrderId("");
      refresh();
    } else {
      setError(`Could not start run (${res.status}). Is the worker running?`);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Runs</h1>
          <p className="text-sm text-sub">
            One Temporal workflow per order — active and completed.
          </p>
        </div>
      </div>

      <section className="rounded-xl border border-line bg-panel p-4">
        <h2 className="text-sm font-medium mb-3">Start a new run</h2>
        <div className="flex flex-wrap gap-2">
          <input
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && start()}
            placeholder="ORD-1042"
            className="flex-1 min-w-48 rounded-lg border border-line bg-panelsoft px-3 py-2 text-sm outline-none focus:border-brand"
          />
          <select
            value={supervisorId ?? ""}
            onChange={(e) =>
              setSupervisorId(e.target.value ? Number(e.target.value) : undefined)
            }
            className="rounded-lg border border-line bg-panelsoft px-3 py-2 text-sm outline-none focus:border-brand"
          >
            {supervisors.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <button
            onClick={start}
            disabled={busy || !orderId.trim()}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brandhover disabled:opacity-40"
          >
            {busy ? "Starting…" : "Start run"}
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-danger">{error}</p>}
      </section>

      <section className="rounded-xl border border-line bg-panel overflow-hidden">
        {runs === null ? (
          <p className="p-6 text-sm text-sub">Loading runs…</p>
        ) : runs.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-sm text-sub">No runs yet.</p>
            <p className="text-xs text-sub mt-1">
              Start your first run above — make sure the worker is running.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-sub uppercase tracking-wide">
                <th className="px-4 py-3 font-medium">Order</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Started</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr
                  key={r.workflow_id + r.run_id}
                  className="border-b border-line last:border-0 hover:bg-panelsoft"
                >
                  <td className="px-4 py-3 font-mono text-xs">{r.order_id}</td>
                  <td className="px-4 py-3">
                    <StatusChip
                      label={r.status.replace("WorkflowExecutionStatus.", "")}
                    />
                  </td>
                  <td className="px-4 py-3 text-sub text-xs">
                    {r.start_time
                      ? new Date(r.start_time).toLocaleString()
                      : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/runs/${r.order_id}`}
                      className="text-brand hover:underline text-xs font-medium"
                    >
                      Open →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
