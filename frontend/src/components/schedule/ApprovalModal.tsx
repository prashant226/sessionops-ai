import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { formatDate, formatTime } from "@/lib/utils";
import type { SessionOut } from "@/lib/types";

export function ApprovalModal({
  open,
  onClose,
  onConfirm,
  smeName,
  session,
  recipientEmail,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  smeName: string;
  session: SessionOut;
  recipientEmail: string | null;
  loading?: boolean;
}) {
  return (
    <Modal open={open} onClose={onClose} title="Approve Assignment">
      <div className="space-y-4">
        <dl className="space-y-2 text-[13.5px]">
          <div className="flex justify-between">
            <dt className="text-slate-500">SME</dt>
            <dd className="font-medium text-slate-800">{smeName}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Session</dt>
            <dd className="text-right font-medium text-slate-800">
              {session.topic} {session.class_type}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">When</dt>
            <dd className="text-right font-medium text-slate-800">
              {formatDate(session.start_datetime, session.timezone)}, {formatTime(session.start_datetime, session.timezone)} ({session.timezone})
            </dd>
          </div>
        </dl>

        <div className="rounded border border-brand-200 bg-brand-50 px-3.5 py-3 text-[13px] text-brand-900">
          <p className="font-medium">Calendar invitation will be sent to:</p>
          <p className="mt-0.5 font-mono text-[12.5px]">{recipientEmail || "no email on file"}</p>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={onConfirm} loading={loading} disabled={!recipientEmail}>
            Approve &amp; Send Invite
          </Button>
        </div>
      </div>
    </Modal>
  );
}
