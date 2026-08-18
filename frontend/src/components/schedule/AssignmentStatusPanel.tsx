"use client";

import { useState } from "react";
import { Mail, ExternalLink, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/StatusPill";
import { RsvpBadge } from "@/components/ui/RsvpBadge";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/lib/toast-context";
import type { AssignmentOut } from "@/lib/types";

// Only these are truly final decisions with a real (or once-real) Calendar
// invite. EDITED_PENDING_APPROVAL / EXCEPTION_PENDING_APPROVAL are
// deliberately excluded -- they are not approved yet, so this panel (and
// its Calendar/RSVP claims) must not show for them.
const DECIDED_STATUSES = new Set(["APPROVED", "CONFIRMED", "REASSIGNED", "FINALIZED"]);

/** The prominent "what's the current state" block shown once an assignment
 * has moved past a bare AI recommendation -- deliberately louder than the
 * AI score section below it once a decision exists (product spec section
 * 24: RSVP/Calendar state should outrank the original scoring once it's no
 * longer the live decision point). */
export function AssignmentStatusPanel({ assignment, onChanged }: { assignment: AssignmentOut; onChanged: () => void }) {
  const { push } = useToast();
  const [busy, setBusy] = useState(false);

  if (!DECIDED_STATUSES.has(assignment.status) || !assignment.sme_id) return null;

  async function resend() {
    setBusy(true);
    try {
      await api.resendInvite(assignment.assignment_id);
      push("success", "Invitation resent");
      onChanged();
    } catch (err) {
      push("error", "Could not resend the invitation", err instanceof ApiError ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  }

  async function openEvent() {
    try {
      const { url } = await api.eventLink(assignment.assignment_id);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      push("error", "Could not open the calendar event", err instanceof ApiError ? err.message : undefined);
    }
  }

  return (
    <div className="mt-3 rounded border border-slate-300 bg-slate-50 p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Assignment</p>
          <p className="text-[16px] font-semibold text-slate-900">{assignment.sme_name}</p>
        </div>
        <StatusPill status={assignment.status} />
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-slate-200 pt-3">
        <div className="flex items-center gap-1.5 text-[13px] text-slate-600">
          <Mail size={14} className="text-slate-400" />
          {assignment.calendar_event_id ? (
            <span>
              Invite sent{assignment.calendar_recipient_email ? ` to ${assignment.calendar_recipient_email}` : ""}
            </span>
          ) : (
            <span>No invitation sent</span>
          )}
        </div>
        {assignment.calendar_event_id && (
          <div className="flex gap-1.5">
            <button onClick={openEvent} className="focus-ring flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-1 text-[12px] font-medium text-slate-600 hover:bg-slate-50">
              <ExternalLink size={12} /> Open Event
            </button>
            <button onClick={resend} disabled={busy} className="focus-ring flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-1 text-[12px] font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50">
              <RefreshCw size={12} /> Resend Invite
            </button>
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-slate-200 pt-3">
        <span className="text-[13px] text-slate-600">RSVP</span>
        <RsvpBadge status={assignment.rsvp_status} />
      </div>
    </div>
  );
}
