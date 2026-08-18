"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, LogOut } from "lucide-react";
import { api } from "@/lib/api";
import type { SearchResult } from "@/lib/types";
import { useApp } from "@/lib/app-context";

export function Topbar({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { logout } = useApp();
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(() => {
      api
        .search(q)
        .then((r) => {
          setResults(r);
          setOpen(true);
        })
        .catch(() => setResults([]));
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function goTo(r: SearchResult) {
    setOpen(false);
    setQ("");
    if (r.type === "session") router.push(`/schedule?session=${r.id}`);
    else router.push(`/smes/${r.id}`);
  }

  return (
    <header className="flex min-h-16 shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-slate-200 bg-white px-6 py-3">
      <div className="shrink-0">
        <h1 className="whitespace-nowrap text-[17px] font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="whitespace-nowrap text-[12.5px] text-slate-500">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap items-center justify-end gap-3">
        <div ref={boxRef} className="relative">
          <div className="flex h-9 w-64 items-center gap-2 rounded border border-slate-300 bg-white px-3 text-slate-400 focus-within:border-brand-500">
            <Search size={15} />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onFocus={() => results.length > 0 && setOpen(true)}
              placeholder="Search session, topic, or SME"
              aria-label="Global search"
              className="h-full w-full bg-transparent text-[13px] text-slate-800 placeholder:text-slate-400 focus:outline-none"
            />
          </div>
          {open && results.length > 0 && (
            <div className="absolute right-0 top-10 z-40 max-h-80 w-80 overflow-y-auto rounded border border-slate-200 bg-white py-1 shadow-panel">
              {results.map((r) => (
                <button
                  key={`${r.type}-${r.id}`}
                  onClick={() => goTo(r)}
                  className="focus-ring flex w-full flex-col items-start px-3 py-2 text-left hover:bg-slate-50"
                >
                  <span className="text-[13px] font-medium text-slate-800">{r.label}</span>
                  <span className="text-[11.5px] text-slate-500">{r.sublabel}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        {actions}
        <button
          onClick={logout}
          aria-label="Sign out"
          className="focus-ring flex h-9 w-9 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <LogOut size={16} />
        </button>
      </div>
    </header>
  );
}
