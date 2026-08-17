"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarDays, LayoutDashboard, AlertOctagon, BarChart3, Users, Settings, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useApp } from "@/lib/app-context";

const NAV = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/schedule", label: "Schedule", icon: CalendarDays },
  { href: "/exceptions", label: "Exceptions", icon: AlertOctagon },
  { href: "/insights", label: "Insights", icon: BarChart3 },
  { href: "/smes", label: "SMEs", icon: Users },
];

export function Sidebar() {
  const pathname = usePathname();
  const { opsName } = useApp();

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col justify-between bg-navy-900 text-slate-300">
      <div>
        <div className="px-5 pb-5 pt-6">
          <div className="flex items-center gap-2">
            <Sparkles size={18} className="text-brand-400" />
            <span className="text-[15px] font-semibold tracking-tight text-white">SessionOps AI</span>
          </div>
          <p className="mt-0.5 text-[11px] text-slate-400">AI Scheduling</p>
        </div>
        <nav className="flex flex-col gap-0.5 px-3">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "focus-ring flex items-center gap-2.5 rounded px-3 py-2 text-[13.5px] font-medium transition-colors",
                  active ? "bg-brand-600 text-white" : "text-slate-300 hover:bg-navy-800 hover:text-white"
                )}
              >
                <Icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="border-t border-navy-800 px-3 py-3">
        <Link
          href="/settings"
          className={cn(
            "focus-ring flex items-center gap-2.5 rounded px-3 py-2 text-[13.5px] font-medium transition-colors",
            pathname === "/settings" ? "bg-brand-600 text-white" : "text-slate-300 hover:bg-navy-800 hover:text-white"
          )}
        >
          <Settings size={16} />
          Settings
        </Link>
        <div className="mt-2 px-3 py-1.5">
          <p className="truncate text-[13px] font-medium text-slate-200">{opsName || "Ops Team"}</p>
          <p className="truncate text-[11px] text-slate-500">ops@sessionops-demo.com</p>
        </div>
      </div>
    </aside>
  );
}
