import { cn } from "@/lib/utils";
import { Tooltip } from "@/components/ui/Tooltip";
import type { CandidateOut } from "@/lib/types";

function WorkloadChip({ candidate }: { candidate: CandidateOut }) {
  const workloadWarning = candidate.warnings.find((w) => w.toLowerCase().includes("workload"));
  const hoursWarning = candidate.warnings.find((w) => w.toLowerCase().includes("preferred"));
  if (!workloadWarning && !hoursWarning) return null;
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
      {workloadWarning && (
        <span className="inline-flex items-center gap-1 rounded-sm border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-800">
          Workload: Above average
          <Tooltip
            content={
              <>
                Rolling workload: {candidate.rolling_workload} sessions
                <br />
                Team average: {candidate.team_average_workload} sessions
              </>
            }
          />
        </span>
      )}
      {hoursWarning && (
        <span className="inline-flex items-center rounded-sm border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
          Outside preferred hours
        </span>
      )}
    </div>
  );
}

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
        <WorkloadChip candidate={candidate} />
      </div>
      <span className="shrink-0 text-lg font-semibold tabular-nums text-slate-800">{candidate.total_score}</span>
    </Tag>
  );
}
