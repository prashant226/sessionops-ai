import { cn, formatTime } from "@/lib/utils";
import type { AssignmentOut } from "@/lib/types";

const STATUS_DOT: Record<string, string> = {
  PENDING_REVIEW: "bg-brand-500",
  APPROVED: "bg-sky-500",
  CONFIRMED: "bg-emerald-500",
  EDITED: "bg-violet-500",
  OVERRIDDEN: "bg-amber-500",
  REASSIGNMENT_REQUIRED: "bg-red-500",
  REASSIGNED: "bg-amber-500",
  UNFILLED: "bg-red-500",
  FINALIZED: "bg-slate-700",
};

function dayLabel(iso: string, tz: string) {
  return new Date(`${iso}Z`.replace(/Z+$/, "Z")).toLocaleDateString("en-US", { weekday: "short", day: "numeric", timeZone: tz || "UTC" });
}

export function CalendarView({ rows, onOpen }: { rows: AssignmentOut[]; onOpen: (assignmentId: string) => void }) {
  const byDay = new Map<string, AssignmentOut[]>();
  for (const r of rows) {
    const key = dayLabel(r.session.start_datetime, r.session.timezone);
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key)!.push(r);
  }
  const days = Array.from(byDay.entries());

  if (days.length === 0) return null;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
      {days.map(([day, items]) => (
        <div key={day} className="rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 bg-slate-50 px-3 py-2 text-[12px] font-semibold text-slate-600">{day}</div>
          <div className="space-y-1.5 p-2">
            {items
              .sort((a, b) => a.session.start_datetime.localeCompare(b.session.start_datetime))
              .map((r) => (
                <button
                  key={r.assignment_id}
                  onClick={() => onOpen(r.assignment_id)}
                  className="focus-ring flex w-full flex-col items-start rounded border border-slate-200 px-2.5 py-2 text-left hover:border-slate-300 hover:bg-slate-50"
                >
                  <div className="flex w-full items-center gap-1.5">
                    <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", STATUS_DOT[r.status] || "bg-slate-300")} />
                    <span className="text-[11.5px] text-slate-500">{formatTime(r.session.start_datetime, r.session.timezone)}</span>
                  </div>
                  <p className="mt-0.5 truncate text-[12.5px] font-medium text-slate-800">{r.session.topic}</p>
                  <p className="truncate text-[11.5px] text-slate-500">{r.sme_name || "Unassigned"}</p>
                </button>
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}
