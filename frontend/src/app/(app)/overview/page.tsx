"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw, ArrowRight, RotateCcw, CalendarCheck } from "lucide-react";
import { Topbar } from "@/components/shell/Topbar";
import { Button } from "@/components/ui/Button";
import { KpiCard } from "@/components/ui/KpiCard";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { EmptyState } from "@/components/ui/EmptyState";
import { SeverityBadge } from "@/components/ui/SeverityBadge";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { SchedulePeriodBar } from "@/components/schedule/SchedulePeriodBar";
import { api, ApiError } from "@/lib/api";
import { useApp } from "@/lib/app-context";
import { useToast } from "@/lib/toast-context";
import type { KpiOut, NeedsAttentionItem } from "@/lib/types";

export default function OverviewPage() {
  const { periodStart, periodEnd, opsName } = useApp();
  const { push } = useToast();
  const router = useRouter();
  const [kpis, setKpis] = useState<KpiOut | null>(null);
  const [attention, setAttention] = useState<NeedsAttentionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetting, setResetting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [k, a] = await Promise.all([api.kpis(periodStart, periodEnd), api.needsAttention(periodStart, periodEnd)]);
      setKpis(k);
      setAttention(a);
    } catch (err) {
      push("error", "Could not load overview", err instanceof ApiError ? err.message : undefined);
    } finally {
      setLoading(false);
    }
  }, [periodStart, periodEnd, push]);

  useEffect(() => {
    load();
  }, [load]);

  // Quietly re-pull every 30s so RSVP changes picked up by the backend's
  // background poller (live mode) show up without a manual refresh.
  useEffect(() => {
    const interval = setInterval(() => {
      Promise.all([api.kpis(periodStart, periodEnd), api.needsAttention(periodStart, periodEnd)])
        .then(([k, a]) => {
          setKpis(k);
          setAttention(a);
        })
        .catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, [periodStart, periodEnd]);

  async function onReset() {
    setResetting(true);
    try {
      const res = await api.resetPeriod(periodStart, periodEnd);
      push("success", "Period reset", `Cleared ${res.cleared} assignment(s). Everything is back to 0 -- run Generate Draft on the Schedule page to repopulate.`);
      setResetOpen(false);
      await load();
    } catch (err) {
      push("error", "Could not reset this period", err instanceof ApiError ? err.message : undefined);
    } finally {
      setResetting(false);
    }
  }

  async function onSync() {
    setSyncing(true);
    try {
      const res = await api.sync();
      push("success", "Data synced", `${res.sessions} sessions and ${res.smes} SMEs loaded from source data.`);
      await load();
    } catch (err) {
      push("error", "We could not sync your data", err instanceof ApiError ? err.message : "Your existing schedule has not been changed.");
    } finally {
      setSyncing(false);
    }
  }

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const reviewed = kpis ? kpis.confirmed : 0;
  const total = kpis?.total_sessions || 0;
  const progressPct = total ? (reviewed / total) * 100 : 0;

  return (
    <>
      <Topbar
        title={`${greeting}, ${opsName || "Ops Team"}`}
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={onSync} loading={syncing}>
              <RefreshCw size={14} /> Sync Data
            </Button>
            {kpis && kpis.total_sessions > 0 && (
              <Button variant="outline-danger" size="sm" onClick={() => setResetOpen(true)}>
                <RotateCcw size={14} /> Reset
              </Button>
            )}
          </>
        }
      />
      <div className="p-6">
        <SchedulePeriodBar onPeriodChanged={load} />

        {loading ? (
          <div className="grid grid-cols-5 gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded border border-slate-200 bg-white" />
            ))}
          </div>
        ) : !kpis || kpis.total_sessions === 0 ? (
          <EmptyState
            icon={CalendarCheck}
            title="No sessions found for this period"
            description="Sync your session data, then go to Schedule to generate a draft for this date range."
            action={
              <div className="flex gap-2">
                <Button variant="secondary" onClick={onSync} loading={syncing}>
                  <RefreshCw size={14} /> Sync Data
                </Button>
                <Button onClick={() => router.push("/schedule")}>Go to Schedule</Button>
              </div>
            }
          />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              <KpiCard label="Total Sessions" value={kpis.total_sessions} />
              <KpiCard label="Confirmed" value={kpis.confirmed} tone="success" />
              <KpiCard label="Pending Review" value={kpis.pending_review} tone="brand" />
              <KpiCard label="Need Attention" value={kpis.need_attention} tone="danger" />
              <KpiCard label="Unfilled" value={kpis.unfilled} tone="warning" />
            </div>

            <div className="mt-6 rounded border border-slate-200 bg-white p-5 shadow-subtle">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-[14px] font-semibold text-slate-900">Needs Attention</h2>
                <button onClick={() => router.push("/exceptions")} className="focus-ring flex items-center gap-1 text-[13px] font-medium text-brand-600 hover:text-brand-700">
                  View all <ArrowRight size={13} />
                </button>
              </div>
              {attention.length === 0 ? (
                <EmptyState title="No unresolved exceptions" description="This schedule is ready for review." className="py-8" />
              ) : (
                <ul className="divide-y divide-slate-100">
                  {attention.slice(0, 5).map((item) => (
                    <li key={item.session_id} className="flex items-center justify-between gap-3 py-2.5">
                      <div className="flex min-w-0 items-center gap-3">
                        <SeverityBadge severity={item.severity} />
                        <div className="min-w-0">
                          <p className="truncate text-[13.5px] font-medium text-slate-800">
                            <span className="text-slate-400">{item.session_id}</span> · {item.headline}
                          </p>
                          <p className="truncate text-[12px] text-slate-500">{item.detail}</p>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-3">
                        {item.starts_in && <span className="text-[12px] text-slate-400">Starts in {item.starts_in}</span>}
                        <button
                          onClick={() => router.push(`/schedule?session=${item.session_id}`)}
                          className="focus-ring rounded border border-slate-300 px-2.5 py-1 text-[12.5px] font-medium text-slate-600 hover:bg-slate-50"
                        >
                          Review
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="mt-6 rounded border border-slate-200 bg-white p-5 shadow-subtle">
              <h2 className="mb-3 text-[14px] font-semibold text-slate-900">Review Progress</h2>
              <ProgressBar value={progressPct} />
              <p className="mt-2 text-[12.5px] text-slate-500">
                {kpis.confirmed} Confirmed · {kpis.pending_review} Pending · {kpis.need_attention} Exceptions
              </p>
              <div className="mt-4 flex gap-2">
                <Button onClick={() => router.push("/schedule")}>Go to Schedule</Button>
                <Button variant="secondary" onClick={() => router.push("/exceptions")}>
                  Review Exceptions
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
      <ConfirmModal
        open={resetOpen}
        onClose={() => setResetOpen(false)}
        onConfirm={onReset}
        loading={resetting}
        danger
        title="Reset This Period"
        confirmLabel="Reset to 0"
        description={
          <>
            This clears every assignment for this period back to a blank slate -- all counts go to 0, and
            you&apos;ll need to run Generate Draft on the Schedule page again to repopulate it.
            <br />
            <br />
            Session, SME, and performance data is not affected. If any invites were already sent to a real
            Google Calendar, those events are not deleted -- only the app&apos;s own record of them is cleared.
          </>
        }
      />
    </>
  );
}
