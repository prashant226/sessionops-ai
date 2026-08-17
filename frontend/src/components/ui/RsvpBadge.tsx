import { cn } from "@/lib/utils";
import { Clock, CircleDot } from "lucide-react";
import type { RsvpStatus } from "@/lib/types";

const LABEL: Record<string, string> = {
  NONE: "—",
  PENDING: "Pending",
  ACCEPTED: "Accepted",
  TENTATIVE: "Tentative",
  DECLINED: "Declined",
};

const STYLE: Record<string, string> = {
  NONE: "text-slate-400",
  PENDING: "text-amber-600",
  ACCEPTED: "text-emerald-700",
  TENTATIVE: "text-amber-600",
  DECLINED: "text-red-600",
};

export function RsvpBadge({ status, className }: { status: RsvpStatus | string; className?: string }) {
  if (status === "NONE" || !status) {
    return <span className={cn("text-[13px] text-slate-400", className)}>—</span>;
  }
  const Icon = status === "PENDING" || status === "TENTATIVE" ? Clock : CircleDot;
  return (
    <span className={cn("inline-flex items-center gap-1 text-[13px] font-medium", STYLE[status], className)}>
      <Icon size={13} />
      {LABEL[status] || status}
    </span>
  );
}
