import { cn } from "@/lib/utils";
import type { AssignmentStatus } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = {
  DRAFT: "Draft",
  PENDING_REVIEW: "Pending Review",
  APPROVED: "Approved",
  CONFIRMED: "Confirmed",
  EDITED: "Edited",
  OVERRIDDEN: "Overridden",
  REASSIGNMENT_REQUIRED: "Reassignment Required",
  REASSIGNED: "Replacement Invited",
  UNFILLED: "Unfilled",
  FINALIZED: "Finalized",
};

const STATUS_STYLE: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600 border-slate-200",
  PENDING_REVIEW: "bg-brand-50 text-brand-700 border-brand-200",
  APPROVED: "bg-sky-50 text-sky-700 border-sky-200",
  CONFIRMED: "bg-emerald-50 text-emerald-700 border-emerald-200",
  EDITED: "bg-violet-50 text-violet-700 border-violet-200",
  OVERRIDDEN: "bg-amber-50 text-amber-800 border-amber-200",
  REASSIGNMENT_REQUIRED: "bg-red-50 text-red-700 border-red-200",
  REASSIGNED: "bg-amber-50 text-amber-800 border-amber-200",
  UNFILLED: "bg-red-50 text-red-700 border-red-200",
  FINALIZED: "bg-slate-800 text-white border-slate-800",
};

export function StatusPill({ status, className }: { status: AssignmentStatus | string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm border px-2 py-0.5 text-[12px] font-medium leading-5",
        STATUS_STYLE[status] || "bg-slate-100 text-slate-600 border-slate-200",
        className
      )}
    >
      {STATUS_LABEL[status] || status}
    </span>
  );
}
