"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, BarChart3, Bot, Leaf, Moon, Sun } from "lucide-react";
import { apiHealthy } from "@/lib/api";

const nav = [
  { href: "/", label: "Runs", icon: Activity },
  { href: "/supervisors", label: "Supervisors", icon: Bot },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [online, setOnline] = useState(false);
  const [dark, setDark] = useState(true);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
    const check = () => apiHealthy().then(setOnline);
    check();
    const id = setInterval(check, 5000);
    return () => clearInterval(id);
  }, []);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  return (
    <div className="flex min-h-screen">
      <aside className="sidebar">
        <Link href="/" className="flex items-center gap-3 border-b border-line px-6 py-5">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand/15 text-brand">
            <Leaf size={22} fill="currentColor" />
          </span>
          <div>
            <p className="text-base font-semibold leading-tight">Order Supervisor</p>
            <p className="mt-0.5 text-xs text-sub">AI that keeps orders moving</p>
          </div>
        </Link>

        <nav className="flex-1 px-3 py-4">
          {nav.map(({ href, label, icon: Icon }) => {
            const active =
              href === "/"
                ? path === "/" || path.startsWith("/runs")
                : path.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`nav-item ${active ? "active" : ""}`}
              >
                <Icon size={20} />
                <span className="flex-1">{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-line px-5 py-4">
          <p className="flex items-center gap-2 text-xs text-brand">
            <Leaf size={16} fill="currentColor" /> Build a greener tomorrow.
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-end gap-4 border-b border-line bg-panel px-6">
          <span className={`flex items-center gap-2 text-xs ${online ? "text-brand" : "text-warn"}`}>
            <span className={`h-2.5 w-2.5 rounded-full ${online ? "bg-brand" : "bg-warn animate-pulse"}`} />
            {online ? "API Connected" : "API Offline"}
          </span>

          <button
            onClick={toggleTheme}
            aria-label="Toggle dark mode"
            className="flex items-center gap-2 rounded-full border border-line bg-panelsoft px-1.5 py-1"
          >
            <Moon size={14} className="text-sub" />
            <span
              className={`flex h-5 w-5 items-center justify-center rounded-full ${
                dark ? "bg-brand text-white translate-x-3" : "bg-sub text-white -translate-x-3"
              } transition-transform`}
            >
              {dark ? "" : ""}
            </span>
            <Sun size={14} className="text-sub" />
          </button>

          <span className="flex items-center gap-1.5 text-sm font-medium">
            <Leaf size={18} className="text-brand" fill="currentColor" /> Sagepilot.ai
          </span>

          <span className="flex items-center gap-2 rounded-full border border-line py-1 pl-1 pr-3">
            <span className="grid h-6 w-6 place-items-center rounded-full bg-brand text-[10px] font-bold text-white">
              SB
            </span>
            <span className="text-xs">Shubham</span>
          </span>
        </header>

        {!online && (
          <div className="bg-dangersoft px-4 py-2 text-center text-sm text-danger">
            Backend not reachable at localhost:8000 — start it with{" "}
            <code className="font-mono">uv run uvicorn main:app --port 8000</code>
          </div>
        )}

        <main className="mx-auto w-full max-w-[1420px] flex-1 p-5 sm:p-8">{children}</main>
      </div>
    </div>
  );
}
