import { ConfirmModal } from "@/components/ui/ConfirmModal";

export function ApprovalModal({
  open,
  onClose,
  onConfirm,
  smeName,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  smeName: string;
  loading?: boolean;
}) {
  return (
    <ConfirmModal
      open={open}
      onClose={onClose}
      onConfirm={onConfirm}
      loading={loading}
      title="Approve Recommendation"
      confirmLabel="Approve & Send Invite"
      description={
        <>
          Approve {smeName} for this session?
          <br />
          This will create a Google Calendar invitation.
        </>
      }
    />
  );
}
