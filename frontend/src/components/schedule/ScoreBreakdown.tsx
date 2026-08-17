import type { ScoreBreakdown as ScoreBreakdownType } from "@/lib/types";

const ROWS: { key: keyof ScoreBreakdownType; maxKey: keyof ScoreBreakdownType; label: string }[] = [
  { key: "expertise", maxKey: "expertise_max", label: "Expertise" },
  { key: "performance", maxKey: "performance_max", label: "Performance" },
  { key: "fairness", maxKey: "fairness_max", label: "Fairness" },
  { key: "preference", maxKey: "preference_max", label: "Preference" },
];

export function ScoreBreakdown({ breakdown }: { breakdown: ScoreBreakdownType }) {
  return (
    <div className="space-y-2">
      {ROWS.map((r) => {
        const value = breakdown[r.key];
        const max = breakdown[r.maxKey];
        return (
          <div key={r.key}>
            <div className="mb-0.5 flex justify-between text-[12.5px]">
              <span className="text-slate-600">{r.label}</span>
              <span className="tabular-nums font-medium text-slate-700">
                {value}/{max}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-500" style={{ width: `${(value / max) * 100}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
