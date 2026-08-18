"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Search, Ban } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { CandidateCard } from "./CandidateCard";
import { api } from "@/lib/api";
import type { CandidateOut, SmeListItem } from "@/lib/types";

export interface EditConflict {
  kind: "blocked" | "exception_required";
  reason: string;
}

export function EditAssignmentModal({
  open,
  onClose,
  onConfirm,
  candidates,
  title = "Edit Assignment",
  loading,
  conflict,
  onDismissConflict,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (smeId: string, exceptionReason?: string) => void;
  candidates: CandidateOut[];
  title?: string;
  loading?: boolean;
  conflict: EditConflict | null;
  onDismissConflict: () => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [allSmes, setAllSmes] = useState<SmeListItem[]>([]);
  const [exceptionReason, setExceptionReason] = useState("");

  useEffect(() => {
    if (open) api.smes().then(setAllSmes).catch(() => {});
  }, [open]);

  useEffect(() => {
    if (!open) {
      setSelected(null);
      setQuery("");
      setExceptionReason("");
    }
  }, [open]);

  const knownIds = useMemo(() => new Set(candidates.map((c) => c.sme_id)), [candidates]);
  const extraMatches = useMemo(() => {
    if (query.trim().length < 2) return [];
    const q = query.toLowerCase();
    return allSmes.filter((s) => !knownIds.has(s.sme_id) && s.name.toLowerCase().includes(q)).slice(0, 6);
  }, [query, allSmes, knownIds]);

  function selectCandidate(id: string) {
    setSelected(id);
    onDismissConflict();
    setExceptionReason("");
  }

  return (
    <Modal open={open} onClose={onClose} title={title} width="max-w-lg">
      <div className="space-y-3">
        <div className="flex h-9 items-center gap-2 rounded border border-slate-300 px-3 text-slate-400 focus-within:border-brand-500">
          <Search size={14} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search any SME by name"
            className="h-full w-full bg-transparent text-[13px] text-slate-800 placeholder:text-slate-400 focus:outline-none"
          />
        </div>

        <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
          {candidates.length === 0 && extraMatches.length === 0 && (
            <p className="py-4 text-center text-[13px] text-slate-400">No candidates to show. Try searching by name.</p>
          )}
          {candidates.map((c) => (
            <CandidateCard key={c.sme_id} candidate={c} selected={selected === c.sme_id} onSelect={() => selectCandidate(c.sme_id)} />
          ))}
          {extraMatches.map((s) => (
            <button
              key={s.sme_id}
              onClick={() => selectCandidate(s.sme_id)}
              className={`focus-ring flex w-full items-center justify-between rounded border px-3.5 py-3 text-left transition-colors ${
                selected === s.sme_id ? "border-brand-400 bg-brand-50" : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              <div>
                <p className="text-[13.5px] font-medium text-slate-800">{s.name}</p>
                <p className="mt-0.5 text-[12px] text-slate-500">
                  {s.status} · {s.expertise_level} · {s.primary_skills.join(", ")}
                </p>
              </div>
            </button>
          ))}
        </div>

        {conflict?.kind === "blocked" && (
          <div className="flex items-start gap-2 rounded border border-red-200 bg-red-50 px-3 py-2.5 text-[13px] text-red-700">
            <Ban size={15} className="mt-0.5 shrink-0" />
            <div>
              <p className="font-medium">This candidate cannot be assigned.</p>
              <p className="mt-0.5">{conflict.reason}</p>
              <p className="mt-1 text-[12px] text-red-600">This is a hard constraint and cannot be overridden. Choose another SME.</p>
            </div>
          </div>
        )}

        {conflict?.kind === "exception_required" && (
          <div className="space-y-2 rounded border border-amber-200 bg-amber-50 px-3 py-2.5 text-[13px] text-amber-900">
            <div className="flex items-start gap-2">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-medium">This candidate exceeds a policy limit.</p>
                <p className="mt-0.5">{conflict.reason}</p>
              </div>
            </div>
            <label className="block text-[12px] font-medium text-amber-900" htmlFor="exception-reason">
              Reason for exception (required)
            </label>
            <textarea
              id="exception-reason"
              value={exceptionReason}
              onChange={(e) => setExceptionReason(e.target.value)}
              rows={2}
              placeholder="e.g. Only qualified SME available this week"
              className="focus-ring w-full rounded border border-amber-300 bg-white px-2.5 py-1.5 text-[13px] text-slate-800 placeholder:text-slate-400"
            />
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          {conflict?.kind === "exception_required" ? (
            <Button variant="danger" onClick={() => selected && onConfirm(selected, exceptionReason)} disabled={!exceptionReason.trim()} loading={loading}>
              Request Exception
            </Button>
          ) : (
            <Button onClick={() => selected && onConfirm(selected)} disabled={!selected || conflict?.kind === "blocked"} loading={loading}>
              Confirm Change
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}
