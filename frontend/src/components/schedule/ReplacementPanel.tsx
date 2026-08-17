"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { CandidateCard } from "./CandidateCard";
import type { CandidateOut } from "@/lib/types";

export function ReplacementPanel({
  candidates,
  onSend,
  loading,
}: {
  candidates: CandidateOut[];
  onSend: (smeId: string) => void;
  loading?: boolean;
}) {
  const eligible = candidates.filter((c) => c.eligible);
  const [selected, setSelected] = useState<string | null>(eligible[0]?.sme_id || null);
  const [showAll, setShowAll] = useState(false);

  if (eligible.length === 0) {
    return (
      <div className="rounded border border-red-200 bg-red-50 p-3.5 text-[13px] text-red-700">
        No replacement candidates are currently qualified and available for this session.
      </div>
    );
  }

  const shown = showAll ? eligible : eligible.slice(0, 1);

  return (
    <div className="space-y-3">
      <p className="text-[12.5px] font-semibold uppercase tracking-wide text-slate-500">Replacement Recommendation</p>
      <div className="space-y-2">
        {shown.map((c) => (
          <CandidateCard key={c.sme_id} candidate={c} selected={selected === c.sme_id} onSelect={() => setSelected(c.sme_id)} />
        ))}
      </div>
      {!showAll && eligible.length > 1 && (
        <button onClick={() => setShowAll(true)} className="focus-ring text-[12.5px] font-medium text-brand-600 hover:text-brand-700">
          Choose another candidate
        </button>
      )}
      <Button className="w-full" onClick={() => selected && onSend(selected)} disabled={!selected} loading={loading}>
        Send Replacement Invite
      </Button>
    </div>
  );
}
