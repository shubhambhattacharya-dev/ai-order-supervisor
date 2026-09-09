"use client";

import { useEffect, useState } from "react";
import {
  createSupervisor,
  listSupervisors,
  type Supervisor,
} from "@/lib/api";

const ALL_ACTIONS = [
  "message_fulfillment_team",
  "message_payments_team",
  "message_logistics_team",
  "message_customer",
  "create_internal_note",
  "sleep_until",
  "no_action",
];

export default function SupervisorsPage() {
  const [configs, setConfigs] = useState<Supervisor[] | null>(null);
  const [name, setName] = useState("");
  const [instruction, setInstruction] = useState("");
  const [actions, setActions] = useState<string[]>(ALL_ACTIONS.slice(0, 5));
  const [wake, setWake] = useState(60);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setConfigs(await listSupervisors());
  }

  useEffect(() => {
    refresh();
  }, []);

  function toggle(action: string) {
    setActions((a) =>
      a.includes(action) ? a.filter((x) => x !== action) : [...a, action],
    );
  }

  async function save() {
    setError(null);
    if (!name.trim() || !instruction.trim() || busy) return;

    setBusy(true);
    const res = await createSupervisor({
      name: name.trim(),
      base_instruction: instruction.trim(),
      allowed_actions: actions,
      default_wake_minutes: wake,
    });
    setBusy(false);

    if (res.ok) {
      setName("");
      setInstruction("");
      refresh();
    } else {
      setError(`Save failed (${res.status}) — name may already exist.`);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Supervisors</h1>
        <p className="text-sm text-sub">
          Reusable templates: base instruction, allowed actions, wake behavior.
        </p>
      </div>

      <section className="rounded-xl border border-line bg-panel p-4">
        <h2 className="text-sm font-medium mb-3">Create configuration</h2>

        <div className="space-y-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name — e.g. Night-shift Ops"
            className="w-full rounded-lg border border-line bg-panelsoft px-3 py-2 text-sm outline-none focus:border-brand"
          />

          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            rows={3}
            placeholder="Base instruction — how this supervisor should behave"
            className="w-full rounded-lg border border-line bg-panelsoft px-3 py-2 text-sm outline-none focus:border-brand"
          />

          <div>
            <p className="text-xs text-sub mb-1.5">Allowed actions</p>
            <div className="flex flex-wrap gap-1.5">
              {ALL_ACTIONS.map((a) => (
                <button
                  key={a}
                  onClick={() => toggle(a)}
                  className={`rounded-full px-2.5 py-1 text-xs font-mono border transition-colors ${
                    actions.includes(a)
                      ? "bg-brandsoft text-brand border-brand"
                      : "text-sub border-line hover:text-txt"
                  }`}
                >
                  {a}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <label className="text-xs text-sub">
              Default wake-up (minutes)
            </label>
            <input
              type="number"
              min={1}
              max={240}
              value={wake}
              onChange={(e) => setWake(Number(e.target.value) || 60)}
              className="w-24 rounded-lg border border-line bg-panelsoft px-3 py-2 text-sm outline-none focus:border-brand"
            />
          </div>

          <button
            onClick={save}
            disabled={busy || !name.trim() || !instruction.trim()}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brandhover disabled:opacity-40"
          >
            {busy ? "Saving…" : "Save configuration"}
          </button>
          {error && <p className="text-sm text-danger">{error}</p>}
        </div>
      </section>

      <section className="rounded-xl border border-line bg-panel overflow-hidden">
        {configs === null ? (
          <p className="p-6 text-sm text-sub">Loading…</p>
        ) : (
          <ul className="divide-y divide-line">
            {configs.map((c) => (
              <li key={c.id} className="p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">{c.name}</span>
                  <span className="text-xs text-sub">
                    wake {c.default_wake_minutes}m
                  </span>
                </div>
                <p className="text-xs text-sub mt-1 line-clamp-2">
                  {c.base_instruction}
                </p>
                {c.allowed_actions.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {c.allowed_actions.map((a) => (
                      <span
                        key={a}
                        className="rounded bg-panelsoft px-1.5 py-0.5 text-[10px] font-mono text-sub"
                      >
                        {a}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
