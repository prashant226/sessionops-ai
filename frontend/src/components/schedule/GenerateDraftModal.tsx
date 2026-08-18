"use client";

import { useState } from "react";
import { Check, Loader2, Circle } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { GenerateEvent } from "@/lib/types";

const STAGES = [
  { key: "loading_sessions", label: "Loading sessions" },
  { key: "checking_availability", label: "Checking availability" },
  { key: "applying_hard_constraints", label: "Applying hard constraints" },
  { key: "evaluating_expertise", label: "Evaluating expertise" },
  { key: "optimizing_workload_fairness", label: "Optimizing workload fairness" },
  { key: "generating_recommendations", label: "Generating recommendations" },
  { key: "detecting_conflicts", label: "Detecting conflicts" },
  { key: "preparing_review_queue", label: "Preparing review queue" },
];

export function GenerateDraftModal({
  open,
  onClose,
  startDate,
  endDate,
  onComplete,
}: {
  open: boolean;
  onClose: () => void;
  startDate: string;
  endDate: string;
  onComplete: () => void;
}) {
  const [running, setRunning] = useState(false);
  const [stageIndex, setStageIndex] = useState(-1);
  const [total, setTotal] = useState(0);
  const [processed, setProcessed] = useState(0);
  const [summary, setSummary] = useState<{ pending_review: number; unfilled: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    setSummary(null);
    setStageIndex(0);
    setProcessed(0);
    setTotal(0);
    try {
      await api.generateDraft(startDate, endDate, (e: GenerateEvent) => {
        if (e.stage === "loading_sessions_done") {
          setTotal(e.count || 0);
          setStageIndex(1);
        } else if (e.stage === "session_processed") {
          setProcessed((p) => p + 1);
          setStageIndex(4);
        } else if (e.stage === "detecting_conflicts") {
          setStageIndex(6);
        } else if (e.stage === "preparing_review_queue") {
          setStageIndex(7);
        } else if (e.stage === "done") {
          setStageIndex(8);
          setSummary({ pending_review: e.pending_review || 0, unfilled: e.unfilled || 0 });
        }
      });
      onComplete();
    } catch {
      setError("We could not generate the draft schedule. Your existing schedule has not been changed.");
    } finally {
      setRunning(false);
    }
  }

  function handleClose() {
    if (running) return;
    setStageIndex(-1);
    onClose();
  }

  return (
    <Modal open={open} onClose={handleClose} title="Generating Schedule" width="max-w-lg">
      {stageIndex === -1 ? (
        <div className="space-y-4">
          <p className="text-[13px] text-slate-600">
            The engine will load sessions in this date range, apply hard constraints, score every eligible SME, and
            prepare a draft recommendation for each session that still needs review.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={run}>Generate Draft</Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {total > 0 && (
            <div>
              <div className="mb-1 flex justify-between text-[12px] text-slate-500">
                <span>Sessions processed</span>
                <span className="tabular-nums">
                  {processed} / {total}
                </span>
              </div>
              <ProgressBar value={total ? (processed / total) * 100 : 0} />
            </div>
          )}
          <ul className="space-y-1.5">
            {STAGES.map((s, i) => {
              const done = i < stageIndex || (i === stageIndex && s.key === "preparing_review_queue" && summary);
              const active = i === stageIndex && !done;
              return (
                <li key={s.key} className={cn("flex items-center gap-2 text-[13px]", done ? "text-slate-700" : active ? "text-brand-700" : "text-slate-400")}>
                  {done ? (
                    <Check size={15} className="text-emerald-600" />
                  ) : active ? (
                    <Loader2 size={15} className="animate-spin text-brand-600" />
                  ) : (
                    <Circle size={15} className="text-slate-300" />
                  )}
                  {s.label}
                </li>
              );
            })}
          </ul>
          {error && <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">{error}</p>}
          {summary && (
            <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2.5 text-[13px] text-slate-700">
              Draft ready: <span className="font-semibold text-brand-700">{summary.pending_review}</span> ready for review,{" "}
              <span className="font-semibold text-red-600">{summary.unfilled}</span> unfilled.
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={handleClose} disabled={running}>
              {summary ? "Close" : "Cancel"}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
