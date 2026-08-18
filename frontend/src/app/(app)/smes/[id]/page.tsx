"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Topbar } from "@/components/shell/Topbar";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/lib/toast-context";
import type { SmeDetailOut } from "@/lib/types";

export default function SmeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { push } = useToast();
  const [sme, setSme] = useState<SmeDetailOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .sme(id)
      .then(setSme)
      .catch((err) => push("error", "Could not load this SME", err instanceof ApiError ? err.message : undefined))
      .finally(() => setLoading(false));
  }, [id, push]);

  return (
    <>
      <Topbar title={sme?.name || "SME"} subtitle={sme ? `${sme.status} · ${sme.expertise_level}` : undefined} />
      <div className="p-6">
        <button onClick={() => router.push("/smes")} className="focus-ring mb-4 flex items-center gap-1.5 text-[13px] font-medium text-slate-500 hover:text-slate-700">
          <ArrowLeft size={14} /> Back to SMEs
        </button>

        {loading || !sme ? (
          <div className="h-64 animate-pulse rounded border border-slate-200 bg-white" />
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="rounded border border-slate-200 bg-white p-5 shadow-subtle lg:col-span-1">
              <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-slate-500">Profile</h2>
              <dl className="space-y-2.5 text-[13px]">
                <Row label="Email" value={sme.email || "—"} />
                <Row label="Status" value={sme.status} />
                <Row label="Timezone" value={sme.timezone} />
                <Row label="Base Location" value={sme.base_location} />
                <Row label="Expertise Level" value={sme.expertise_level} />
                <Row label="Daily Capacity" value={`${sme.max_sessions_per_day} sessions/day`} />
                <Row label="Rolling 4-week Workload" value={String(sme.rolling_workload)} />
                <Row label="Primary Skills" value={sme.primary_skills.join(", ") || "—"} />
                <Row label="Secondary Skills" value={sme.secondary_skills.join(", ") || "—"} />
              </dl>

              {sme.calendar_recipient_email && sme.calendar_recipient_email !== sme.email && (
                <div className="mt-3 rounded border border-dashed border-slate-300 bg-slate-50 px-3 py-2.5">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Demo invite recipient</p>
                  <p className="mt-0.5 font-mono text-[12.5px] text-slate-700">{sme.calendar_recipient_email}</p>
                  <p className="mt-1 text-[11.5px] text-slate-500">
                    Demo mode is on -- real Calendar invites for this SME are redirected here instead of their listed email.
                  </p>
                </div>
              )}

              {sme.preferences && (
                <>
                  <h2 className="mb-3 mt-5 text-[13px] font-semibold uppercase tracking-wide text-slate-500">Preferences</h2>
                  <dl className="space-y-2.5 text-[13px]">
                    <Row label="Preferred Topics" value={sme.preferences.preferred_topics.join(", ") || "—"} />
                    <Row label="Preferred Class Types" value={sme.preferences.preferred_class_types.join(", ") || "—"} />
                    <Row
                      label="Preferred Hours"
                      value={sme.preferences.preferred_start_time && sme.preferences.preferred_end_time ? `${sme.preferences.preferred_start_time}–${sme.preferences.preferred_end_time}` : "—"}
                    />
                  </dl>
                </>
              )}
            </div>

            <div className="rounded border border-slate-200 bg-white p-5 shadow-subtle lg:col-span-2">
              <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-slate-500">Topic &amp; Class Type Performance</h2>
              {sme.performance.length === 0 ? (
                <p className="text-[13px] text-slate-400">No performance history recorded yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] border-collapse text-left">
                    <thead>
                      <tr className="border-b border-slate-200 text-[11.5px] font-semibold uppercase tracking-wide text-slate-500">
                        <th className="py-2 pr-4">Topic</th>
                        <th className="py-2 pr-4">Class Type</th>
                        <th className="py-2 pr-4">Sessions</th>
                        <th className="py-2 pr-4">Rating</th>
                        <th className="py-2 pr-4">Quality</th>
                        <th className="py-2 pr-4">Reliability</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-[13px] text-slate-700">
                      {sme.performance.map((p, i) => (
                        <tr key={i}>
                          <td className="py-2 pr-4">{p.topic}</td>
                          <td className="py-2 pr-4">{p.class_type}</td>
                          <td className="py-2 pr-4 tabular-nums">{p.sessions_delivered}</td>
                          <td className="py-2 pr-4 tabular-nums">{p.avg_learner_rating.toFixed(1)}/5</td>
                          <td className="py-2 pr-4 tabular-nums">{p.avg_quality_score}</td>
                          <td className="py-2 pr-4 tabular-nums">{p.reliability_score}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value}</dd>
    </div>
  );
}
