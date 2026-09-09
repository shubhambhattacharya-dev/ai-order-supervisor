"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, Bot, Leaf, Moon, Sun } from "lucide-react";
import { apiHealthy } from "@/lib/api";

const nav = [{ href: "/", label: "Runs", icon: Activity }, { href: "/supervisors", label: "Supervisors", icon: Bot }];

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
  return <div className="flex min-h-screen">
    <aside className="sidebar">
      <Link href="/" className="flex items-center gap-3 border-b border-line px-6 py-5">
        <span className="grid h-8 w-8 place-items-center rounded-xl bg-brand/15 text-brand"><Leaf size={22} fill="currentColor"/></span>
        <div><p className="text-lg font-semibold leading-tight">Order Supervisor</p><p className="mt-1 text-xs text-sub">AI that keeps orders moving</p></div>
      </Link>
      <nav className="flex-1 px-3 py-4">{nav.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? path === "/" || path.startsWith("/runs") : path.startsWith(href);
        return <Link key={label} href={href} className={`nav-item ${active ? "active" : ""}`}><Icon size={20}/>{label}</Link>;
      })}</nav>
      <div className="border-t border-line px-5 py-4">
        <button onClick={toggleTheme} className="mb-4 flex w-full items-center justify-between rounded-lg border border-line px-3 py-2 text-xs text-sub hover:text-txt hover:bg-panel-soft" aria-label="Toggle dark mode">
          <span>{dark ? "Light mode" : "Dark mode"}</span>
          {dark ? <Sun size={15}/> : <Moon size={15}/>}
        </button>
        <p className="mt-2 flex items-center gap-2 text-xs text-brand"><Leaf size={17} fill="currentColor"/> Build a greener tomorrow.</p>
      </div>
    </aside>
    <div className="min-w-0 flex-1">
      <header className="flex h-16 items-center justify-end border-b border-line px-6"><button onClick={toggleTheme} aria-label="Toggle dark mode" className="mr-4 grid h-8 w-8 place-items-center rounded-lg border border-line text-sub hover:text-txt"><Moon size={15}/></button><span className={`mr-2 h-2.5 w-2.5 rounded-full ${online ? "bg-brand" : "bg-warn"}`}/><span className="mr-8 text-xs text-brand">{online ? "API Connected" : "Demo mode"}</span><span className="flex items-center gap-2 text-sm font-medium"><Leaf size={22} className="text-brand" fill="currentColor"/> Sagepilot.ai</span></header>
      <main className="mx-auto max-w-[1420px] p-5 sm:p-8">{children}</main>
    </div>
  </div>;
}
