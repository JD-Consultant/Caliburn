/** Rename a label from an observed base; never silently upgrade a rejected command. */
import { useRef, useState } from 'react';
import type { SubmitEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
} from '@mui/material';
import type { JobFile } from '../../shared/api/generated/job-file-list';
import type { RenameJobFileRequest } from '../../shared/api/generated/rename-job-file-request';
import { ApiError } from '../../shared/api/http';
import { isRenameJobFileRequest } from '../../shared/api/validation';
import { focusDialogInput } from '../../shared/ui/dialog-focus';
import { renameJobFile } from './job-file-api';
import { clearPendingRename, readPendingRename, retainPendingRename } from './rename-command';

interface Props {
  file: JobFile;
  onClose: () => void;
  onRefresh: () => void;
}

function restoreRename(jobFileId: string): {
  command: RenameJobFileRequest | null;
  error: string | null;
} {
  try {
    return { command: readPendingRename(jobFileId), error: null };
  } catch {
    return {
      command: null,
      error: '無法讀取本分頁的待確認改名紀錄。請確認瀏覽器儲存權限，勿重複改名。',
    };
  }
}

export function RenameJobFileDialog({ file, onClose, onRefresh }: Props) {
  const [restored] = useState(() => restoreRename(file.job_file_id));
  const [pending, setPending] = useState(restored.command);
  const [displayName, setDisplayName] = useState(
    restored.command?.display_name ?? file.display_name,
  );
  const [message, setMessage] = useState(restored.error);
  const [isRejected, setIsRejected] = useState(false);
  const nameInput = useRef<HTMLInputElement>(null);
  const inFlight = useRef(false);
  const mutation = useMutation({
    mutationFn: (command: RenameJobFileRequest) => renameJobFile(file.job_file_id, command),
    retry: false,
  });

  async function submit(event: SubmitEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (inFlight.current || restored.error || isRejected) return;
    const command = pending ?? {
      command_id: crypto.randomUUID(),
      expected_name_revision: file.name_revision,
      display_name: displayName,
    };
    if (!isRenameJobFileRequest(command)) {
      setMessage('名稱須為 1–200 字，不能只有空白。');
      return;
    }
    try {
      retainPendingRename(file.job_file_id, command);
    } catch {
      setMessage('瀏覽器無法保留本次改名識別，尚未送出。請確認儲存權限後重試。');
      return;
    }
    inFlight.current = true;
    setPending(command);
    setMessage(null);
    try {
      await mutation.mutateAsync(command);
      try {
        clearPendingRename(file.job_file_id);
      } catch {
        // A residual original command only recovers its result, never overwrites a newer name.
      }
      onRefresh();
    } catch (error) {
      if (error instanceof ApiError && [400, 404, 409, 422].includes(error.status ?? 0)) {
        try {
          clearPendingRename(file.job_file_id);
          setPending(null);
          setIsRejected(true);
          setMessage('改名未被接受。請讀取目前名稱後再決定，不會自動覆蓋其他修改。');
        } catch {
          setMessage('改名未被接受，且待確認紀錄無法清除。請確認瀏覽器儲存權限。');
        }
      } else {
        setMessage('改名結果尚未確認。請重新確認原請求，不會再次覆蓋後來的名稱。');
      }
    } finally {
      inFlight.current = false;
    }
  }

  return (
    <Dialog
      open
      onClose={mutation.isPending ? undefined : onClose}
      fullWidth
      maxWidth="sm"
      aria-labelledby="rename-file-title"
      slotProps={{ transition: { onEntered: () => focusDialogInput(nameInput.current) } }}
    >
      <form
        onSubmit={(event) => {
          void submit(event);
        }}
      >
        <DialogTitle id="rename-file-title">重新命名職務檔案</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <p>只修改檔案名稱，不影響受訪員工姓名、JD 或訪談內容。</p>
            {message && <Alert severity="warning">{message}</Alert>}
            {pending && !message && !mutation.isPending && (
              <Alert severity="info">有尚未確認的改名請求，請先取得原結果。</Alert>
            )}
            <TextField
              inputRef={nameInput}
              label="職務檔案名稱"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              required
              disabled={pending !== null || !!restored.error || isRejected}
              slotProps={{ htmlInput: { maxLength: 200 } }}
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button variant="outlined" onClick={onClose} disabled={mutation.isPending}>
            返回清單
          </Button>
          {isRejected ? (
            <Button variant="contained" onClick={onRefresh}>
              讀取目前名稱
            </Button>
          ) : (
            <Button
              type="submit"
              variant="contained"
              disabled={mutation.isPending || !!restored.error}
            >
              {mutation.isPending ? '確認中…' : pending ? '重新確認改名結果' : '儲存名稱'}
            </Button>
          )}
        </DialogActions>
      </form>
    </Dialog>
  );
}
