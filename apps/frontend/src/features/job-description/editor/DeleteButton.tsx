import { useRef, useState } from 'react';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from '@mui/material';
import { IconAction } from '../../../shared/ui/IconAction';
import { CloseIcon } from '../../../shared/ui/icons';

export function DeleteButton({
  label,
  description,
  disabled,
  onDelete,
}: {
  label: string;
  description: string;
  disabled: boolean;
  onDelete: () => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);
  const [error, setError] = useState('');
  async function confirm() {
    if (pendingRef.current || disabled) return;
    pendingRef.current = true;
    setPending(true);
    try {
      if (await onDelete()) setOpen(false);
      else setError('尚未確認刪除完成。請關閉此視窗，依文件上方的說明核對。');
    } catch {
      setError('刪除未能完成，請檢查文件上方的說明。');
    } finally {
      pendingRef.current = false;
      setPending(false);
    }
  }
  return (
    <>
      <IconAction
        className="jd-delete-button"
        label={`刪除${label}`}
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        <CloseIcon />
      </IconAction>
      <Dialog
        open={open}
        aria-labelledby="jd-delete-title"
        onClose={() => {
          if (!pending) setOpen(false);
        }}
      >
        <DialogTitle id="jd-delete-title">刪除{label}</DialogTitle>
        <DialogContent>
          <DialogContentText>{description}</DialogContentText>
          {error && <Alert severity="error">{error}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button autoFocus disabled={pending} onClick={() => setOpen(false)}>
            取消
          </Button>
          <Button
            color="error"
            variant="contained"
            disabled={disabled || pending}
            onClick={() => {
              void confirm();
            }}
          >
            確認刪除
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
