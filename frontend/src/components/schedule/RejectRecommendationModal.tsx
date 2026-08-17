"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

const REASONS = ["Wrong expertise", "Availability concern", "SME preference", "Better candidate", "Other"];

export function RejectRecommendationModal({
  open,
  onClose,
  onSubmit,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (reason: string) => void;
  loading?: boolean;
}) {
  const [reason, setReason] = useState<string | null>(null);

  return (
    <Modal open={open} onClose={onClose} title="Reject Recommendation">
      <div className="space-y-4">
        <p className="text-[13px] text-slate-600">Why doesn&apos;t this recommendation work? This helps the agent find a better alternative.</p>
        <div className="space-y-1.5">
          {REASONS.map((r) => (
            <button
              key={r}
              onClick={() => setReason(r)}
              className={cn(
                "focus-ring w-full rounded border px-3 py-2 text-left text-[13.5px] transition-colors",
                reason === r ? "border-brand-400 bg-brand-50 text-brand-800" : "border-slate-200 text-slate-700 hover:bg-slate-50"
              )}
            >
              {r}
            </button>
          ))}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={() => reason && onSubmit(reason)} disabled={!reason} loading={loading}>
            Find Alternatives
          </Button>
        </div>
      </div>
    </Modal>
  );
}
