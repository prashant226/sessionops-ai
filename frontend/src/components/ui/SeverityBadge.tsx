import { cn } from "@/lib/utils";
import { AlertTriangle, AlertCircle, Info } from "lucide-react";

const CONFIG: Record<string, { icon: React.ElementType; style: string; label: string }> = {
  Critical: { icon: AlertCircle, style: "bg-red-50 text-red-700 border-red-200", label: "Critical" },
  Warning: { icon: AlertTriangle, style: "bg-amber-50 text-amber-800 border-amber-200", label: "Warning" },
  Info: { icon: Info, style: "bg-slate-100 text-slate-600 border-slate-200", label: "Info" },
};

export function SeverityBadge({ severity, className }: { severity: string; className?: string }) {
  const cfg = CONFIG[severity] || CONFIG.Info;
  const Icon = cfg.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        cfg.style,
        className
      )}
    >
      <Icon size={11} />
      {cfg.label}
    </span>
  );
}
