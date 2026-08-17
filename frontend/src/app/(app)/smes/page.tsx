"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "@/components/shell/Topbar";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/lib/toast-context";
import { cn } from "@/lib/utils";
import type { SmeListItem } from "@/lib/types";

const STATUS_STYLE: Record<string, string> = {
  Active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  "On Leave": "bg-amber-50 text-amber-800 border-amber-200",
  Inactive: "bg-slate-100 text-slate-500 border-slate-200",
};

export default function SmesPage() {
  const { push } = useToast();
  const router = useRouter();
  const [smes, setSmes] = useState<SmeListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  useEffect(() => {
    api
      .smes()
      .then(setSmes)
      .catch((err) => push("error", "Could not load SMEs", err instanceof ApiError ? err.message : undefined))
      .finally(() => setLoading(false));
  }, [push]);

  const filtered = smes.filter((s) => s.name.toLowerCase().includes(q.toLowerCase()) || s.primary_skills.some((sk) => sk.toLowerCase().includes(q.toLowerCase())));

  return (
    <>
      <Topbar title="SMEs" subtitle={`${smes.length} subject matter experts in the pool`} />
      <div className="p-6">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter by name or skill"
          className="focus-ring mb-4 h-9 w-72 rounded border border-slate-300 px-3 text-[13px] focus:border-brand-500"
        />
        {loading ? (
          <div className="h-64 animate-pulse rounded border border-slate-200 bg-white" />
        ) : (
          <div className="overflow-x-auto rounded border border-slate-200 bg-white">
            <table className="w-full min-w-[880px] border-collapse text-left">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-[11.5px] font-semibold uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-2.5">Name</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Level</th>
                  <th className="px-4 py-2.5">Primary Skills</th>
                  <th className="px-4 py-2.5">Timezone</th>
                  <th className="px-4 py-2.5">Location</th>
                  <th className="px-4 py-2.5">Rolling Workload</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-[13px] text-slate-700">
                {filtered.map((s) => (
                  <tr key={s.sme_id} className="cursor-pointer hover:bg-slate-50" onClick={() => router.push(`/smes/${s.sme_id}`)}>
                    <td className="whitespace-nowrap px-4 py-2.5 font-medium text-slate-800">{s.name}</td>
                    <td className="px-4 py-2.5">
                      <span className={cn("inline-flex rounded-sm border px-2 py-0.5 text-[12px] font-medium", STATUS_STYLE[s.status])}>{s.status}</span>
                    </td>
                    <td className="px-4 py-2.5">{s.expertise_level}</td>
                    <td className="px-4 py-2.5 text-slate-500">{s.primary_skills.join(", ")}</td>
                    <td className="px-4 py-2.5 text-slate-500">{s.timezone}</td>
                    <td className="px-4 py-2.5 text-slate-500">{s.base_location}</td>
                    <td className="px-4 py-2.5 tabular-nums">{s.rolling_workload}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
