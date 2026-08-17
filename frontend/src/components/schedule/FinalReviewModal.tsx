"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/lib/toast-context";
import type { FinalReviewOut } from "@/lib/types";

export function FinalReviewModal({
  open,
  onClose,
  weekStart,
  onFinalized,
}: {
  open: boolean;
  onClose: () => void;
  weekStart: string;
  onFinalized: () => void;
}) {
  const { push } = useToast();
  const [data, setData] = useState<FinalReviewOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirmException, setConfirmException] = useState(false);

  useEffect(() => {
    if (!open) {
      setConfirmException(false);
      return;
    }
    api.finalReview(weekStart).then(setData).catch(() => push("error", "Could not load final review"));
  }, [open, weekStart, push]);

  const unresolved = data ? data.pending + data.unfilled : 0;

  async function finalize(force: boolean) {
    setLoading(true);
    try {
      await api.finalize(weekStart, force);
      push("success", "Schedule finalized", `Week of ${weekStart} has been finalized.`);
      onFinalized();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setConfirmException(true);
      } else {
        push("error", "Could not finalize the schedule", err instanceof ApiError ? err.message : undefined);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Final Review">
      {!data ? (
        <div className="h-32 animate-pulse rounded bg-slate-100" />
      ) : (
        <div className="space-y-4">
          <p className="text-[13.5px] text-slate-600">{data.total_sessions} Sessions</p>
          <div className="grid grid-cols-2 gap-3 text-[13px]">
            <Stat label="Confirmed" value={data.confirmed} />
            <Stat label="Edited" value={data.edited} />
            <Stat label="Pending" value={data.pending} />
            <Stat label="Unfilled" value={data.unfilled} tone="danger" />
            <Stat label="Critical Conflicts" value={data.critical} tone="danger" />
            <Stat label="Warnings" value={data.warnings} tone="warning" />
          </div>

          {confirmException && (
            <div className="flex items-start gap-2 rounded border border-amber-200 bg-amber-50 px-3 py-2.5 text-[13px] text-amber-800">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              <p>This schedule contains unresolved exceptions. You can finalize with an exception.</p>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose} disabled={loading}>
              Back to Schedule
            </Button>
            {confirmException ? (
              <Button variant="danger" onClick={() => finalize(true)} loading={loading}>
                Finalize with Exception
              </Button>
            ) : (
              <Button onClick={() => finalize(false)} loading={loading} disabled={data.finalized}>
                {data.finalized ? "Already Finalized" : "Finalize Schedule"}
              </Button>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "danger" | "warning" }) {
  return (
    <div className="rounded border border-slate-200 px-3 py-2">
      <p className={`text-lg font-semibold tabular-nums ${tone === "danger" ? "text-red-600" : tone === "warning" ? "text-amber-600" : "text-slate-800"}`}>{value}</p>
      <p className="text-[12px] text-slate-500">{label}</p>
    </div>
  );
}
