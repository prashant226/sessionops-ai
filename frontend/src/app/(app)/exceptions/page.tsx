"use client";

import { useCallback, useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { Topbar } from "@/components/shell/Topbar";
import { EmptyState } from "@/components/ui/EmptyState";
import { SeverityBadge } from "@/components/ui/SeverityBadge";
import { StatusPill } from "@/components/ui/StatusPill";
import { SessionDrawer } from "@/components/schedule/SessionDrawer";
import { SchedulePeriodBar } from "@/components/schedule/SchedulePeriodBar";
import { api, ApiError } from "@/lib/api";
import { useApp } from "@/lib/app-context";
import { useToast } from "@/lib/toast-context";
import { cn, formatDateTime } from "@/lib/utils";
import type { AssignmentOut } from "@/lib/types";

const FILTERS = ["All", "Critical", "Availability", "Expertise", "Fairness", "RSVP", "Unfilled"];

export default function ExceptionsPage() {
  const { periodStart, periodEnd } = useApp();
  const { push } = useToast();
  const [filter, setFilter] = useState("All");
  const [rows, setRows] = useState<AssignmentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.exceptions(periodStart, periodEnd, filter);
      setRows(data);
    } catch (err) {
      push("error", "Could not load exceptions", err instanceof ApiError ? err.message : undefined);
    } finally {
      setLoading(false);
    }
  }, [periodStart, periodEnd, filter, push]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <Topbar title="Exceptions" subtitle="Sessions that need Ops attention, sorted by urgency" />
      <div className="p-6">
        <SchedulePeriodBar onPeriodChanged={load} />
        <div className="mb-4 flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "focus-ring rounded-full border px-3 py-1.5 text-[12.5px] font-medium transition-colors",
                filter === f ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
              )}
            >
              {f}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="h-64 animate-pulse rounded border border-slate-200 bg-white" />
        ) : rows.length === 0 ? (
          <EmptyState icon={ShieldCheck} title="No unresolved exceptions" description="This schedule is ready for review." />
        ) : (
          <ul className="space-y-2">
            {rows.map((r) => (
              <li key={r.assignment_id}>
                <button
                  onClick={() => setOpenId(r.assignment_id)}
                  className="focus-ring flex w-full items-center justify-between gap-4 rounded border border-slate-200 bg-white px-4 py-3.5 text-left hover:border-slate-300 hover:shadow-subtle"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    {r.exception_severity && <SeverityBadge severity={r.exception_severity} />}
                    <div className="min-w-0">
                      <p className="truncate text-[13.5px] font-medium text-slate-800">
                        <span className="text-slate-400">{r.session.session_id}</span> · {r.session.topic} — {r.session.class_type}
                      </p>
                      <p className="truncate text-[12px] text-slate-500">
                        {formatDateTime(r.session.start_datetime, r.session.timezone)} · {r.reason || "No details available."}
                      </p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <StatusPill status={r.status} />
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {openId && <SessionDrawer assignmentId={openId} onClose={() => setOpenId(null)} onChanged={load} />}
    </>
  );
}
