"use client";

import { useState, useEffect, useCallback } from "react";
import {
  createRun,
  injectEvent,
  getStatus,
  type RunStatus,
} from "@/lib/api";

const EVENT_TYPES = [
  "STATUS_UPDATE",
  "PAYMENT_DELAYED",
  "SHIPMENT_DELAYED",
  "FULFILLMENT_DELAYED",
  "CUSTOMER_MESSAGE_RECEIVED",
  "REFUND_REQUESTED",
  "COMPLETED",
  "CANCELLED",
];

export default function Home() {
  const [orderId, setOrderId] = useState("");
  const [activeRun, setActiveRun] = useState<string | null>(null);
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [eventType, setEventType] = useState(EVENT_TYPES[0]);
  const [error, setError] = useState<string | null>(null);

  // Step 4: Start or attach to a workflow run
  async function startRun() {
    setError(null);

    if (!orderId.trim()) return;

    const res = await createRun(orderId.trim());

    if (res.ok || res.status === 409) {
      setActiveRun(orderId.trim());
    } else {
      setError(`failed to start run (${res.status})`);
    }
  }

  // Step 5: Inject an event into the workflow
  async function send() {
    setError(null);

    if (!activeRun) return;

    const res = await injectEvent(
      activeRun,
      `evt-${Date.now()}`,
      eventType,
    );

    if (!res.ok) {
      setError(`inject failed (${res.status})`);
    }
  }

  // Step 6: Get the latest workflow status
  const refresh = useCallback(async () => {
    if (activeRun) {
      setStatus(await getStatus(activeRun));
    }
  }, [activeRun]);

  // Step 6: Poll the backend every 3 seconds
  useEffect(() => {
    if (!activeRun) return;

    refresh();

    const t = setInterval(refresh, 3000);

    return () => clearInterval(t);
  }, [activeRun, refresh]);

  return (
    <main className="max-w-3xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-4">
        AI Order Supervisor
      </h1>

      {error && (
        <div className="bg-red-100 text-red-700 p-3 rounded mb-4">
          {error}
        </div>
      )}

      {/* Step 4: Start or attach */}
      <section className="border rounded p-4 mb-4 space-y-2">
        <h2 className="font-semibold">
          1 · Start or attach to a run
        </h2>

        <div className="flex gap-2">
          <input
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            placeholder="ORD-100"
            className="border p-2 rounded flex-1"
          />

          <button
            onClick={startRun}
            className="bg-black text-white px-4 py-2 rounded"
          >
            {activeRun === orderId.trim() ? "Attach" : "Start"}
          </button>
        </div>

        {activeRun && (
          <p className="text-sm text-green-600">
            Attached: {activeRun}
          </p>
        )}
      </section>

      {/* Step 5: Inject event */}
      <section className="border rounded p-4 mb-4 flex gap-2">
        <select
          value={eventType}
          onChange={(e) => setEventType(e.target.value)}
          className="border p-2 rounded"
        >
          {EVENT_TYPES.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>

        <button
          onClick={send}
          disabled={!activeRun}
          className="bg-black text-white px-4 py-2 rounded disabled:opacity-40"
        >
          Inject event
        </button>
      </section>

      {/* Step 6: Live status */}
      <section className="border rounded p-4 flex flex-wrap gap-2">
        {status ? (
          Object.entries(status.status).map(([k, v]) => (
            <span
              key={k}
              className="border rounded-full px-3 py-1 text-sm"
            >
              {k}: {String(v)}
            </span>
          ))
        ) : (
          <p className="text-gray-500">
            Start a run to see live status.
          </p>
        )}
      </section>
    </main>
  );
}