import { cn } from "@/lib/utils";

const TONE: Record<string, string> = {
  default: "text-slate-900",
  brand: "text-brand-600",
  success: "text-emerald-600",
  warning: "text-amber-600",
  danger: "text-red-600",
};

export function KpiCard({
  label,
  value,
  tone = "default",
  className,
}: {
  label: string;
  value: string | number;
  tone?: "default" | "brand" | "success" | "warning" | "danger";
  className?: string;
}) {
  return (
    <div className={cn("rounded border border-slate-200 bg-white px-5 py-4 shadow-subtle", className)}>
      <p className={cn("text-3xl font-semibold tabular-nums", TONE[tone])}>{value}</p>
      <p className="mt-1 text-[13px] text-slate-500">{label}</p>
    </div>
  );
}
