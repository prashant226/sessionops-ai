import { formatTime, formatDate } from "@/lib/utils";
import type { ActivityOut } from "@/lib/types";

const ACTOR_STYLE: Record<string, string> = {
  AI: "bg-brand-100 text-brand-700",
  Ops: "bg-slate-200 text-slate-700",
  System: "bg-slate-100 text-slate-500",
};

export function ActivityTimeline({ items }: { items: ActivityOut[] }) {
  if (items.length === 0) {
    return <p className="text-[13px] text-slate-400">No activity recorded yet.</p>;
  }
  return (
    <ol className="space-y-3">
      {items.map((a, i) => (
        <li key={i} className="flex gap-3">
          <div className="flex flex-col items-center">
            <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold ${ACTOR_STYLE[a.actor] || "bg-slate-100 text-slate-500"}`}>
              {a.actor[0]}
            </span>
            {i < items.length - 1 && <span className="mt-0.5 w-px flex-1 bg-slate-200" />}
          </div>
          <div className="pb-3">
            <p className="text-[13px] text-slate-700">{a.message}</p>
            <p className="text-[11.5px] text-slate-400">
              {formatDate(a.timestamp)} · {formatTime(a.timestamp)}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
