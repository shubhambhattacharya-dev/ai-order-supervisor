"use client";

export default function StatusChip({ label }: { label: string }) {
  const tone = (() => {
    const s = label.toUpperCase();
    if (s.includes("RUNNING")) return "bg-brandsoft text-brand";
    if (s.includes("SLEEPING") || s.includes("PAUSED"))
      return "bg-infosoft text-info";
    if (s.includes("ESCALAT") || s.includes("CANCELLED"))
      return "bg-warnsoft text-warn";
    if (s.includes("TERMINATED") || s.includes("FAILED"))
      return "bg-dangersoft text-danger";
    if (s.includes("COMPLETED")) return "bg-brandsoft text-brand";
    return "bg-panelsoft text-sub";
  })();

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${tone}`}
    >
      {label}
    </span>
  );
}
