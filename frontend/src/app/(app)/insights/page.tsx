"use client";

import { useCallback, useEffect, useState } from "react";
import { Topbar } from "@/components/shell/Topbar";
import { Tooltip } from "@/components/ui/Tooltip";
import { SchedulePeriodBar } from "@/components/schedule/SchedulePeriodBar";
import { api, ApiError } from "@/lib/api";
import { useApp } from "@/lib/app-context";
import { useToast } from "@/lib/toast-context";
import type { InsightsOut, Metric } from "@/lib/types";

function formatValue(m: Metric): string {
  if (m.value === null) return "—";
  if (m.unit === "percent") return `${m.value}%`;
  if (m.unit === "minutes") return `${m.value} min`;
  return `${m.value}`;
}

function MetricCard({ metric }: { metric: Metric }) {
  return (
    <div className="rounded border border-slate-200 bg-white p-4 shadow-subtle">
      <div className="mb-1 flex items-center gap-1.5">
        <p className="text-[12.5px] font-medium text-slate-500">{metric.label}</p>
        <Tooltip
          content={
            <div className="space-y-1.5">
              <p>
                <span className="font-semibold text-slate-700">Definition: </span>
                {metric.definition}
              </p>
              <p>
                <span className="font-semibold text-slate-700">Calculation: </span>
                {metric.calculation}
              </p>
              <p>
                <span className="font-semibold text-slate-700">Why it matters: </span>
                {metric.why_it_matters}
              </p>
            </div>
          }
        />
      </div>
      <p className="text-2xl font-semibold tabular-nums text-slate-900">{formatValue(metric)}</p>
    </div>
  );
}

function Section({ title, metrics }: { title: string; metrics: Metric[] }) {
  return (
    <div className="mb-8">
      <h2 className="mb-3 text-[14px] font-semibold text-slate-900">{title}</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {metrics.map((m) => (
          <MetricCard key={m.key} metric={m} />
        ))}
      </div>
    </div>
  );
}

export default function InsightsPage() {
  const { periodStart, periodEnd } = useApp();
  const { push } = useToast();
  const [data, setData] = useState<InsightsOut | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await api.insights(periodStart, periodEnd));
    } catch (err) {
      push("error", "Could not load insights", err instanceof ApiError ? err.message : undefined);
    } finally {
      setLoading(false);
    }
  }, [periodStart, periodEnd, push]);

  useEffect(() => {
    load();
  }, [load]);

  const maxWorkload = data ? Math.max(1, ...data.workload.map((w) => w.rolling_workload)) : 1;

  return (
    <>
      <Topbar title="Insights" subtitle="Is the system improving scheduling operations?" />
      <div className="p-6">
        <SchedulePeriodBar onPeriodChanged={load} />
        {loading || !data ? (
          <div className="h-64 animate-pulse rounded border border-slate-200 bg-white" />
        ) : (
          <>
            <Section title="Efficiency" metrics={data.efficiency} />
            <Section title="AI Quality" metrics={data.ai_quality} />
            <Section title="Scheduling Quality" metrics={data.scheduling_quality} />

            <div>
              <div className="mb-3 flex items-center gap-1.5">
                <h2 className="text-[14px] font-semibold text-slate-900">Workload Balance</h2>
                <Tooltip content="Rolling 4-week session count per active SME, including this week's assignments so far. The dashed line marks the team average." />
              </div>
              <div className="rounded border border-slate-200 bg-white p-4 shadow-subtle">
                <p className="mb-3 text-[12.5px] text-slate-500">
                  Team average: <span className="font-semibold text-slate-700">{data.team_average_workload}</span> sessions
                </p>
                <div className="space-y-2">
                  {data.workload.slice(0, 15).map((w) => (
                    <div key={w.sme_id} className="flex items-center gap-3">
                      <span className="w-32 shrink-0 truncate text-[12.5px] text-slate-600">{w.name}</span>
                      <div className="relative h-2 flex-1 rounded-full bg-slate-100">
                        <div
                          className={`h-full rounded-full ${w.rolling_workload > data.team_average_workload * 1.4 ? "bg-amber-500" : "bg-brand-500"}`}
                          style={{ width: `${(w.rolling_workload / maxWorkload) * 100}%` }}
                        />
                        <div
                          className="absolute top-0 h-2 w-px bg-slate-400"
                          style={{ left: `${(data.team_average_workload / maxWorkload) * 100}%` }}
                        />
                      </div>
                      <span className="w-6 shrink-0 text-right text-[12.5px] tabular-nums text-slate-600">{w.rolling_workload}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
