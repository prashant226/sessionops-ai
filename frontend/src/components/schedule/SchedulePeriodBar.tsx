"use client";

import { useEffect, useState } from "react";
import { CalendarRange, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { cn, formatDate } from "@/lib/utils";
import { api, ApiError } from "@/lib/api";
import { useApp } from "@/lib/app-context";
import type { PeriodConflictOut } from "@/lib/types";

function fmt(dateStr: string): string {
  return formatDate(`${dateStr}T00:00:00`);
}

export function SchedulePeriodBar({ onPeriodChanged }: { onPeriodChanged?: () => void }) {
  const { periodStart, periodEnd, setPeriod } = useApp();
  const [status, setStatus] = useState<"NONE" | "DRAFT" | "FINALIZED">("NONE");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [draftStart, setDraftStart] = useState(periodStart);
  const [draftEnd, setDraftEnd] = useState(periodEnd);
  const [conflict, setConflict] = useState<PeriodConflictOut | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.periodStatus(periodStart, periodEnd).then((s) => setStatus(s.status)).catch(() => setStatus("NONE"));
  }, [periodStart, periodEnd]);

  function openPicker() {
    setDraftStart(periodStart);
    setDraftEnd(periodEnd);
    setConflict(null);
    setError(null);
    setPickerOpen(true);
  }

  async function onSubmitDraftRange() {
    setError(null);
    if (draftEnd < draftStart) {
      setError("End date must be on or after the start date.");
      return;
    }
    setChecking(true);
    try {
      const res = await api.checkOverlap(draftStart, draftEnd);
      if (res.overlap) {
        setConflict(res.overlap);
      } else {
        applyPeriod();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not check this period.");
    } finally {
      setChecking(false);
    }
  }

  function applyPeriod() {
    setPeriod(draftStart, draftEnd);
    setPickerOpen(false);
    setConflict(null);
    onPeriodChanged?.();
  }

  function viewExisting() {
    if (!conflict) return;
    setPeriod(conflict.start_date, conflict.end_date);
    setPickerOpen(false);
    setConflict(null);
    onPeriodChanged?.();
  }

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded border border-slate-200 bg-white px-4 py-2.5">
        <div className="flex items-center gap-2.5">
          <CalendarRange size={16} className="text-slate-400" />
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Schedule Period</p>
            <p className="text-[13.5px] font-medium text-slate-800">
              {fmt(periodStart)} <span className="text-slate-400">&rarr;</span> {fmt(periodEnd)}
            </p>
          </div>
          <span
            className={cn(
              "ml-1 rounded-sm border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
              status === "FINALIZED"
                ? "border-slate-800 bg-slate-800 text-white"
                : status === "DRAFT"
                ? "border-brand-200 bg-brand-50 text-brand-700"
                : "border-slate-200 bg-slate-50 text-slate-400"
            )}
          >
            {status === "NONE" ? "No draft yet" : status === "DRAFT" ? "Draft" : "Finalized"}
          </span>
        </div>
        <Button variant="secondary" size="sm" onClick={openPicker}>
          Change Period
        </Button>
      </div>

      <Modal open={pickerOpen} onClose={() => setPickerOpen(false)} title={conflict ? "Schedule Overlap" : "Change Schedule Period"}>
        {!conflict ? (
          <div className="space-y-4">
            <p className="text-[13px] text-slate-600">
              {status !== "NONE"
                ? "Changing the scheduling period will create a new draft for the selected dates. Your current draft is not discarded -- you can switch back to it any time."
                : "Choose any date range to schedule."}
            </p>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <label className="mb-1 block text-[12px] font-medium text-slate-600" htmlFor="period-start">
                  Start Date
                </label>
                <input
                  id="period-start"
                  type="date"
                  value={draftStart}
                  onChange={(e) => setDraftStart(e.target.value)}
                  className="focus-ring h-9 w-full rounded border border-slate-300 px-2.5 text-[13px] focus:border-brand-500"
                />
              </div>
              <span className="mt-5 text-slate-400">&rarr;</span>
              <div className="flex-1">
                <label className="mb-1 block text-[12px] font-medium text-slate-600" htmlFor="period-end">
                  End Date
                </label>
                <input
                  id="period-end"
                  type="date"
                  value={draftEnd}
                  onChange={(e) => setDraftEnd(e.target.value)}
                  className="focus-ring h-9 w-full rounded border border-slate-300 px-2.5 text-[13px] focus:border-brand-500"
                />
              </div>
            </div>
            {error && <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">{error}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setPickerOpen(false)} disabled={checking}>
                Cancel
              </Button>
              <Button onClick={onSubmitDraftRange} loading={checking}>
                Change Period
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-start gap-2 rounded border border-red-200 bg-red-50 px-3.5 py-3 text-[13px] text-red-800">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-semibold">
                  {conflict.status === "FINALIZED" ? "A finalized schedule already exists for part of this date range." : "An existing schedule overlaps this period."}
                </p>
                <p className="mt-1">
                  Existing schedule: {fmt(conflict.start_date)} &rarr; {fmt(conflict.end_date)} ({conflict.assignment_count} sessions,{" "}
                  {conflict.status === "FINALIZED" ? "finalized" : "draft"})
                </p>
                <p className="mt-1">
                  {conflict.status === "FINALIZED"
                    ? "Review the existing schedule before generating another overlapping schedule."
                    : "Choose another period or open the existing schedule."}
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setConflict(null)}>
                Choose Different Dates
              </Button>
              <Button onClick={viewExisting}>View Existing</Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
