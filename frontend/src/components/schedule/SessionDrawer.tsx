"use client";

import { useCallback, useEffect, useState } from "react";
import { X, AlertCircle, AlertTriangle, MapPin, Video } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/StatusPill";
import { RsvpBadge } from "@/components/ui/RsvpBadge";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { CandidateCard } from "./CandidateCard";
import { ActivityTimeline } from "./ActivityTimeline";
import { ApprovalModal } from "./ApprovalModal";
import { EditAssignmentModal } from "./EditAssignmentModal";
import { RejectRecommendationModal } from "./RejectRecommendationModal";
import { ReplacementPanel } from "./ReplacementPanel";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatTime } from "@/lib/utils";
import { useToast } from "@/lib/toast-context";
import type { AssignmentOut } from "@/lib/types";

export function SessionDrawer({
  assignmentId,
  onClose,
  onChanged,
}: {
  assignmentId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [assignment, setAssignment] = useState<AssignmentOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const { push } = useToast();

  const [approveOpen, setApproveOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [dropoutOpen, setDropoutOpen] = useState(false);
  const [conflictMessage, setConflictMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const a = await api.getAssignment(assignmentId);
      setAssignment(a);
    } catch (err) {
      push("error", "Could not load session details", err instanceof ApiError ? err.message : undefined);
    } finally {
      setLoading(false);
    }
  }, [assignmentId, push]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  function refreshAfterAction(a: AssignmentOut) {
    setAssignment(a);
    onChanged();
  }

  async function doApprove() {
    if (!assignment) return;
    setBusy(true);
    try {
      const a = await api.approve(assignment.assignment_id);
      refreshAfterAction(a);
      push("success", "Assignment approved", "Calendar invitation sent. RSVP: Pending.");
      setApproveOpen(false);
    } catch (err) {
      push("error", "Could not approve this assignment", err instanceof ApiError ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  }

  async function doEdit(smeId: string, override: boolean) {
    if (!assignment) return;
    setBusy(true);
    try {
      const a = await api.edit(assignment.assignment_id, smeId, override);
      refreshAfterAction(a);
      setEditOpen(false);
      setConflictMessage(null);
      push("success", override ? "Assignment overridden" : "Assignment updated");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setConflictMessage(err.message.replace("This assignment conflicts with a hard constraint.", "").trim());
      } else {
        push("error", "Could not update this assignment", err instanceof ApiError ? err.message : undefined);
      }
    } finally {
      setBusy(false);
    }
  }

  async function doReject(reason: string) {
    if (!assignment) return;
    setBusy(true);
    try {
      const a = await api.reject(assignment.assignment_id, reason);
      refreshAfterAction(a);
      setRejectOpen(false);
      push("info", "Recommendation rejected", "Looking for alternative candidates.");
    } catch (err) {
      push("error", "Could not reject this recommendation", err instanceof ApiError ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  }

  async function doSimulateRsvp(rsvp: "ACCEPTED" | "TENTATIVE" | "DECLINED") {
    if (!assignment) return;
    setBusy(true);
    try {
      const a = await api.simulateRsvp(assignment.assignment_id, rsvp);
      refreshAfterAction(a);
      if (rsvp === "ACCEPTED") push("success", "RSVP accepted", "Session confirmed.");
      else if (rsvp === "DECLINED") push("warning", "RSVP declined", "Reassignment required.");
      else push("info", "RSVP tentative", "SME has not fully committed to this session.");
    } catch (err) {
      push("error", "Could not update RSVP", err instanceof ApiError ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  }

  async function doDropout() {
    if (!assignment) return;
    setBusy(true);
    try {
      const a = await api.reportDropout(assignment.assignment_id);
      refreshAfterAction(a);
      setDropoutOpen(false);
      push("warning", "Dropout reported", "Reassignment required.");
    } catch (err) {
      push("error", "Could not report dropout", err instanceof ApiError ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  }

  async function doSendReplacement(smeId: string) {
    if (!assignment) return;
    setBusy(true);
    try {
      const a = await api.sendReplacement(assignment.assignment_id, smeId);
      refreshAfterAction(a);
      push("success", "Replacement invitation sent", "RSVP: Pending.");
    } catch (err) {
      push("error", "Could not send replacement invite", err instanceof ApiError ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/30" role="presentation" onClick={onClose}>
      <div
        className="animate-slide-in flex h-full w-full max-w-md flex-col bg-white shadow-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Session details"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-[15px] font-semibold text-slate-900">Session Details</h2>
          <button aria-label="Close" className="focus-ring rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {loading || !assignment ? (
          <div className="flex-1 space-y-3 p-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-6 animate-pulse rounded bg-slate-100" />
            ))}
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto px-5 py-4">
              <p className="text-[17px] font-semibold text-slate-900">
                {assignment.session.topic} — {assignment.session.class_type}
              </p>
              <p className="mt-1 text-[13px] text-slate-500">
                {formatDate(assignment.session.start_datetime, assignment.session.timezone)} ·{" "}
                {formatTime(assignment.session.start_datetime, assignment.session.timezone)} ({assignment.session.timezone}) ·{" "}
                {assignment.session.duration_mins} min · {assignment.session.required_level}
              </p>
              <p className="mt-1 flex items-center gap-1.5 text-[13px] text-slate-500">
                {assignment.session.mode === "Online" ? <Video size={13} /> : <MapPin size={13} />}
                {assignment.session.mode}
                {assignment.session.location ? ` · ${assignment.session.location}` : ""}
              </p>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <StatusPill status={assignment.status} />
                <RsvpBadge status={assignment.rsvp_status} />
              </div>

              {assignment.exception_severity && (
                <div
                  className={`mt-4 flex items-start gap-2 rounded border px-3.5 py-3 text-[13px] ${
                    assignment.exception_severity === "Critical" ? "border-red-200 bg-red-50 text-red-800" : "border-amber-200 bg-amber-50 text-amber-800"
                  }`}
                >
                  {assignment.exception_severity === "Critical" ? (
                    <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  ) : (
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                  )}
                  <div>
                    <p className="font-semibold">{assignment.exception_severity}</p>
                    <p className="mt-0.5">{assignment.reason}</p>
                    {assignment.exception_detail && "qualified_count" in assignment.exception_detail && (
                      <p className="mt-1.5 text-[12.5px]">
                        Qualified: {String(assignment.exception_detail.qualified_count)}
                        {"available_count" in assignment.exception_detail ? ` · Available: ${String(assignment.exception_detail.available_count)}` : ""}
                      </p>
                    )}
                    {assignment.status === "UNFILLED" && (
                      <div className="mt-2.5 flex flex-wrap gap-1.5">
                        <button
                          onClick={() =>
                            push(
                              "info",
                              "Related expertise",
                              "No SME in the current pool holds this expertise. Consider expanding the SME pool or adjusting the session requirement."
                            )
                          }
                          className="focus-ring rounded border border-red-300 bg-white px-2.5 py-1 text-[12px] font-medium text-red-700 hover:bg-red-50"
                        >
                          View Related Expertise
                        </button>
                        <button
                          onClick={() => setEditOpen(true)}
                          className="focus-ring rounded border border-red-300 bg-white px-2.5 py-1 text-[12px] font-medium text-red-700 hover:bg-red-50"
                        >
                          Manual Assign
                        </button>
                        <button
                          onClick={() => push("info", "Move Session", "Session rescheduling isn't available in this prototype. Reassign manually or escalate.")}
                          className="focus-ring rounded border border-red-300 bg-white px-2.5 py-1 text-[12px] font-medium text-red-700 hover:bg-red-50"
                        >
                          Move Session
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {assignment.sme_id && assignment.status !== "REASSIGNMENT_REQUIRED" && (
                <div className={`mt-4 rounded border p-4 ${assignment.status === "OVERRIDDEN" ? "border-amber-200 bg-amber-50" : "border-brand-200 bg-brand-50"}`}>
                  <p className={`mb-1 text-[11px] font-semibold uppercase tracking-wide ${assignment.status === "OVERRIDDEN" ? "text-amber-700" : "text-brand-700"}`}>
                    {assignment.status === "OVERRIDDEN" || assignment.status === "EDITED" ? "Current Assignment (Ops-selected)" : "AI Recommendation"}
                  </p>
                  <div className="flex items-baseline justify-between">
                    <p className="text-[17px] font-semibold text-slate-900">{assignment.sme_name}</p>
                    {assignment.match_score !== null && (
                      <p className={`text-[15px] font-semibold ${assignment.status === "OVERRIDDEN" ? "text-amber-700" : "text-brand-700"}`}>
                        {assignment.match_score}<span className="text-[12px] font-normal opacity-70">/100</span>
                      </p>
                    )}
                  </div>
                  {assignment.reason && <p className="mt-1.5 text-[13px] leading-relaxed text-slate-700">{assignment.reason}</p>}
                </div>
              )}

              {assignment.breakdown && (
                <div className="mt-4">
                  <p className="mb-2 text-[12.5px] font-semibold uppercase tracking-wide text-slate-500">Score Breakdown</p>
                  <ScoreBreakdown breakdown={assignment.breakdown} />
                </div>
              )}

              {assignment.status === "REASSIGNMENT_REQUIRED" && (
                <div className="mt-4">
                  <ReplacementPanel candidates={assignment.candidates} onSend={doSendReplacement} loading={busy} />
                </div>
              )}

              {assignment.candidates.filter((c) => c.sme_id !== assignment.sme_id && c.eligible).length > 0 && assignment.status !== "REASSIGNMENT_REQUIRED" && (
                <div className="mt-4">
                  <p className="mb-2 text-[12.5px] font-semibold uppercase tracking-wide text-slate-500">Other Candidates</p>
                  <div className="space-y-2">
                    {assignment.candidates
                      .filter((c) => c.sme_id !== assignment.sme_id && c.eligible)
                      .slice(0, 4)
                      .map((c) => (
                        <CandidateCard key={c.sme_id} candidate={c} />
                      ))}
                  </div>
                </div>
              )}

              {(assignment.status === "APPROVED" || assignment.status === "REASSIGNED") && (
                <div className="mt-4 rounded border border-dashed border-slate-300 bg-slate-50 p-3.5">
                  <p className="mb-2 text-[11.5px] font-semibold uppercase tracking-wide text-slate-500">Demo: Simulate SME Response</p>
                  <p className="mb-2 text-[12px] text-slate-500">
                    Standing in for a real Calendar RSVP webhook. In production this updates automatically when the SME responds.
                  </p>
                  <div className="flex gap-1.5">
                    <Button size="sm" variant="secondary" onClick={() => doSimulateRsvp("ACCEPTED")} disabled={busy}>
                      Accepted
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => doSimulateRsvp("TENTATIVE")} disabled={busy}>
                      Tentative
                    </Button>
                    <Button size="sm" variant="outline-danger" onClick={() => doSimulateRsvp("DECLINED")} disabled={busy}>
                      Declined
                    </Button>
                  </div>
                </div>
              )}

              {assignment.rsvp_status === "TENTATIVE" && (
                <div className="mt-4 rounded border border-amber-200 bg-amber-50 p-3.5 text-[13px] text-amber-800">
                  <p className="font-medium">Tentative RSVP</p>
                  <p className="mt-0.5">{assignment.sme_name} has not fully committed to this session.</p>
                </div>
              )}

              <div className="mt-5">
                <p className="mb-2 text-[12.5px] font-semibold uppercase tracking-wide text-slate-500">Activity History</p>
                <ActivityTimeline items={assignment.activity} />
              </div>
            </div>

            <div className="shrink-0 space-y-2 border-t border-slate-200 px-5 py-4">
              {assignment.status === "PENDING_REVIEW" && assignment.sme_id && (
                <>
                  <Button className="w-full" onClick={() => setApproveOpen(true)}>
                    Approve
                  </Button>
                  <Button variant="secondary" className="w-full" onClick={() => setEditOpen(true)}>
                    Edit Assignment
                  </Button>
                  <Button variant="outline-danger" className="w-full" onClick={() => setRejectOpen(true)}>
                    Reject Recommendation
                  </Button>
                </>
              )}
              {(assignment.status === "APPROVED" || assignment.status === "CONFIRMED" || assignment.status === "REASSIGNED") && assignment.sme_id && (
                <Button variant="outline-danger" className="w-full" onClick={() => setDropoutOpen(true)}>
                  Report SME Dropout
                </Button>
              )}
            </div>
          </>
        )}
      </div>

      {assignment && (
        <>
          <ApprovalModal open={approveOpen} onClose={() => setApproveOpen(false)} onConfirm={doApprove} smeName={assignment.sme_name || "this SME"} loading={busy} />
          <EditAssignmentModal
            open={editOpen}
            onClose={() => {
              setEditOpen(false);
              setConflictMessage(null);
            }}
            onConfirm={doEdit}
            candidates={assignment.candidates}
            loading={busy}
            conflictMessage={conflictMessage}
            onDismissConflict={() => setConflictMessage(null)}
          />
          <RejectRecommendationModal open={rejectOpen} onClose={() => setRejectOpen(false)} onSubmit={doReject} loading={busy} />
          <ConfirmModal
            open={dropoutOpen}
            onClose={() => setDropoutOpen(false)}
            onConfirm={doDropout}
            loading={busy}
            danger
            title="Report SME Dropout"
            confirmLabel="Report Dropout"
            description={`Report that ${assignment.sme_name} has dropped out of this session? This will start the replacement workflow, the same as an RSVP decline.`}
          />
        </>
      )}
    </div>
  );
}
