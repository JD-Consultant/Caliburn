/** The command in flight as the person editing sees it: why it is unconfirmed and what they can do next. */
import { Alert, Button } from '@mui/material';

export interface WorkStatusProps {
  message: string | null;
  isSending: boolean;
  /** A command's result is unknown: only that same command may be re-confirmed, never a new one. */
  canConfirm: boolean;
  confirmDisabled: boolean;
  onConfirm: () => void;
  canReload: boolean;
  onReload: () => void;
}

export function WorkStatus({
  message,
  isSending,
  canConfirm,
  confirmDisabled,
  onConfirm,
  canReload,
  onReload,
}: WorkStatusProps) {
  return (
    <>
      {message && <Alert severity="warning">{message}</Alert>}
      {canConfirm && (
        <Button disabled={confirmDisabled} onClick={onConfirm}>
          重新確認修改結果
        </Button>
      )}
      {canReload && <Button onClick={onReload}>讀取目前 JD</Button>}
      {isSending && <p role="status">正在確認修改…</p>}
    </>
  );
}
