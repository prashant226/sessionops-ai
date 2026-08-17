import { StatusPill } from "@/components/ui/StatusPill";
import { RsvpBadge } from "@/components/ui/RsvpBadge";
import { formatDateTime } from "@/lib/utils";
import type { AssignmentOut } from "@/lib/types";

const ACTION_LABEL: Record<string, string> = {
  UNFILLED: "Assign",
  REASSIGNMENT_REQUIRED: "Resolve",
};

export function SessionTable({ rows, onOpen }: { rows: AssignmentOut[]; onOpen: (assignmentId: string) => void }) {
  return (
    <div className="overflow-x-auto rounded border border-slate-200 bg-white">
      <table className="w-full min-w-[880px] border-collapse text-left">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-[11.5px] font-semibold uppercase tracking-wide text-slate-500">
            <th className="px-4 py-2.5">Session</th>
            <th className="px-4 py-2.5">Date &amp; Time</th>
            <th className="px-4 py-2.5">Topic</th>
            <th className="px-4 py-2.5">Class Type</th>
            <th className="px-4 py-2.5">Suggested SME</th>
            <th className="px-4 py-2.5">Match</th>
            <th className="px-4 py-2.5">RSVP</th>
            <th className="px-4 py-2.5">Status</th>
            <th className="px-4 py-2.5">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-[13px] text-slate-700">
          {rows.map((r) => (
            <tr key={r.assignment_id} className="hover:bg-slate-50">
              <td className="whitespace-nowrap px-4 py-2.5 font-medium text-slate-800">{r.session.session_id}</td>
              <td className="whitespace-nowrap px-4 py-2.5 text-slate-500">{formatDateTime(r.session.start_datetime, r.session.timezone)}</td>
              <td className="px-4 py-2.5">{r.session.topic}</td>
              <td className="px-4 py-2.5">{r.session.class_type}</td>
              <td className="px-4 py-2.5">{r.sme_name || "—"}</td>
              <td className="px-4 py-2.5 tabular-nums">{r.match_score !== null ? <span className="font-semibold text-slate-800">{r.match_score}</span> : "—"}</td>
              <td className="px-4 py-2.5">
                <RsvpBadge status={r.rsvp_status} />
              </td>
              <td className="px-4 py-2.5">
                <StatusPill status={r.status} />
              </td>
              <td className="px-4 py-2.5">
                <button
                  onClick={() => onOpen(r.assignment_id)}
                  className="focus-ring rounded border border-slate-300 bg-white px-2.5 py-1 text-[12.5px] font-medium text-slate-600 hover:bg-slate-50"
                >
                  {ACTION_LABEL[r.status] || "Review"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
