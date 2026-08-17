"use client";

import { useState, useId } from "react";
import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

export function Tooltip({ content, className }: { content: React.ReactNode; className?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-describedby={id}
        aria-label="More information"
        className={cn("focus-ring inline-flex items-center rounded-full text-slate-400 hover:text-slate-600", className)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
      >
        <Info size={14} />
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="animate-fade-in absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 rounded border border-slate-200 bg-white p-3 text-left text-[12px] leading-relaxed text-slate-600 shadow-panel"
        >
          {content}
        </span>
      )}
    </span>
  );
}
