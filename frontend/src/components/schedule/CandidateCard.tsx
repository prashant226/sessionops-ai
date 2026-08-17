import { cn } from "@/lib/utils";
import { AlertTriangle } from "lucide-react";
import type { CandidateOut } from "@/lib/types";

export function CandidateCard({
  candidate,
  selected,
  onSelect,
}: {
  candidate: CandidateOut;
  selected?: boolean;
  onSelect?: () => void;
}) {
  const Tag = onSelect ? "button" : "div";
  return (
    <Tag
      onClick={onSelect}
      className={cn(
        "focus-ring flex w-full items-start justify-between gap-3 rounded border px-3.5 py-3 text-left transition-colors",
        selected ? "border-brand-400 bg-brand-50" : "border-slate-200 bg-white hover:border-slate-300"
      )}
    >
      <div className="min-w-0">
        <p className="text-[13.5px] font-medium text-slate-800">{candidate.name}</p>
        <p className="mt-0.5 text-[12px] text-slate-500">
          Expertise {candidate.breakdown.expertise}/{candidate.breakdown.expertise_max} · Performance{" "}
          {candidate.breakdown.performance}/{candidate.breakdown.performance_max} · Workload {candidate.rolling_workload}
        </p>
        {candidate.warnings.length > 0 && (
          <p className="mt-1 flex items-start gap-1 text-[11.5px] text-amber-700">
            <AlertTriangle size={12} className="mt-0.5 shrink-0" />
            {candidate.warnings[0]}
          </p>
        )}
      </div>
      <span className="shrink-0 text-lg font-semibold tabular-nums text-slate-800">{candidate.total_score}</span>
    </Tag>
  );
}
