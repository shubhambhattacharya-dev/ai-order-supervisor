"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Leaf } from "lucide-react";
import { getAnalytics, getObservability, subscribeDecisions, type AnalyticsData, type Observability } from "@/lib/api";

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [obs, setObs] = useState<Observability | null>(null);

  useEffect(() => {
    getAnalytics().then(setData);
    getObservability().then(setObs);
    // Real-time: the decisions feed pushes the moment a new decision lands.
    const close = subscribeDecisions(setData);
    return close;
  }, []);

  const decisions = data?.decisions ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Analytics</h1>
        <p className="text-sm text-sub">
          Observability for every LLM decision the supervisors have made.
        </p>
      </div>

      {/* Langfuse card */}
      <section className="rounded-xl border border-line bg-panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand/15 text-brand">
              <Leaf size={22} />
            </span>
            <div>
              <h2 className="font-medium">Langfuse tracing</h2>
              <p className="text-xs text-sub">
                {obs?.enabled
                  ? "Every agent decision is traced with prompt, provider, tokens and latency."
                  : "Tracing is disabled — add LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY to .env and restart the worker."}
              </p>
            </div>
          </div>
          {obs?.enabled && obs.traces_url && (
            <a
              href={obs.traces_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 rounded-lg border border-brand px-3 py-1.5 text-sm text-brand hover:bg-brandsoft"
            >
              Open traces <ExternalLink size={14} />
            </a>
          )}
        </div>
      </section>

      {/* Totals */}
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {[
          ["Decisions", decisions.length, "LLM calls recorded"],
          ["Tokens used", data ? data.total_tokens.toLocaleString() : "—", "prompt + completion"],
          ["Avg latency", data ? `${data.avg_latency_ms} ms` : "—", "per decision"],
          ["Provider fallbacks", data ? data.fallback_count : "—", "gateway failovers"],
        ].map(([label, value, cap]) => (
          <section key={String(label)} className="metric-card">
            <div className="min-w-0">
              <p className="text-sm text-sub">{label}</p>
              <p className="mt-1 text-2xl font-semibold tracking-tight">{String(value)}</p>
              <p className="mt-0.5 text-xs text-sub">{cap}</p>
            </div>
          </section>
        ))}
      </div>

      {/* Decisions table */}
      <section className="panel overflow-hidden">
        <div className="border-b border-line px-5 py-4">
          <h2 className="font-medium">Decision log</h2>
        </div>
        {decisions.length === 0 ? (
          <p className="p-8 text-center text-sm text-sub">
            No decisions recorded yet — run an order and they appear here.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-sub">
                  <th className="px-4 py-3 font-medium">Time</th>
                  <th className="px-4 py-3 font-medium">Order</th>
                  <th className="px-4 py-3 font-medium">Action</th>
                  <th className="px-4 py-3 font-medium">Provider</th>
                  <th className="px-4 py-3 font-medium">Model</th>
                  <th className="px-4 py-3 font-medium">Tokens</th>
                  <th className="px-4 py-3 font-medium">Latency</th>
                  <th className="px-4 py-3 font-medium">Langfuse</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((d) => (
                  <tr key={d.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-2.5 text-xs text-sub">
                      {new Date(d.created_at).toLocaleTimeString()}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs">{d.order_id}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{d.action ?? "—"}</td>
                    <td className="px-4 py-2.5 text-xs">
                      {d.provider}
                      {d.fallback_used && (
                        <span className="ml-1 rounded bg-warnsoft px-1.5 py-0.5 text-[10px] text-warn">
                          fallback
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-sub">{d.model ?? "—"}</td>
                    <td className="px-4 py-2.5 text-xs">
                      {d.prompt_tokens + d.completion_tokens}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-sub">{d.latency_ms} ms</td>
                    <td className="px-4 py-2.5">
                      {d.trace_url ? (
                        <a href={d.trace_url} target="_blank" rel="noreferrer" className="text-brand hover:underline text-xs">trace</a>
                      ) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
