/** A submission keeps its identity until the backend acknowledges the original result. */
import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
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
import type { CreateJobFileRequest } from '../../shared/api/generated/create-job-file-request';
import { ApiError } from '../../shared/api/http';
import { isCreateJobFileRequest } from '../../shared/api/validation';
import { focusDialogInput } from '../../shared/ui/dialog-focus';
import {
  clearPendingCreation,
  readPendingCreation,
  retainPendingCreation,
} from './creation-command';
import { createJobFile } from './job-file-api';

interface Props {
  onClose: () => void;
  onCreated: (jobFileId: string) => void;
}

function restoreCreation(): { command: CreateJobFileRequest | null; error: string | null } {
  try {
    return { command: readPendingCreation(), error: null };
  } catch {
    return {
      command: null,
      error: '無法讀取本分頁的待確認建立紀錄。請先確認瀏覽器儲存權限，勿重複建立。',
    };
  }
}

export function CreateJobFileDialog({ onClose, onCreated }: Props) {
  const [restored] = useState(restoreCreation);
  const nameInput = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState(restored.command);
  const inFlight = useRef(false);
  const hasPending = pending !== null;
  const [displayName, setDisplayName] = useState(restored.command?.display_name ?? '');
  const [employeeName, setEmployeeName] = useState(restored.command?.employee_name ?? '');
  const [message, setMessage] = useState(restored.error);
  const mutation = useMutation({ mutationFn: createJobFile, retry: false });

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (inFlight.current || restored.error) return;
    const command = pending ?? {
      command_id: crypto.randomUUID(),
      display_name: displayName,
      employee_name: employeeName,
    };
    if (!isCreateJobFileRequest(command)) {
      setMessage('請填寫職務檔案名稱與受訪員工姓名，各 1–200 字，不能只有空白。');
      return;
    }
    try {
      retainPendingCreation(command);
    } catch {
      setMessage('瀏覽器無法保留本次建立識別，尚未送出。請確認儲存權限後重試。');
      return;
    }
    setPending(command);
    inFlight.current = true;
    setMessage(null);
    try {
      const file = await mutation.mutateAsync(command);
      // An acknowledged result stays successful even if local cleanup is unavailable.
      // A leftover command can only retrieve the same original result on the next visit.
      try {
        clearPendingCreation();
      } catch {
        /* Server remains authoritative. */
      }
      onCreated(file.job_file_id);
    } catch (error) {
      if (error instanceof ApiError && [400, 409, 422].includes(error.status ?? 0)) {
        try {
          clearPendingCreation();
          setPending(null);
          setMessage('這次建立未被接受，請檢查名稱與姓名後重新送出。');
        } catch {
          setMessage('建立未被接受，且瀏覽器待確認紀錄未能清除。請確認儲存權限後重試。');
        }
      } else {
        setMessage('建立結果尚未確認。請重新確認原請求，不會另外建立一份檔案。');
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
      aria-labelledby="create-file-title"
      slotProps={{
        transition: {
          onEntered: () => {
            focusDialogInput(nameInput.current);
          },
        },
      }}
    >
      <form
        onSubmit={(event) => {
          void submit(event);
        }}
      >
        <DialogTitle id="create-file-title">建立職務檔案</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <p>一位受訪員工、一份獨立工作記錄。名稱與姓名不會自動填入 JD。</p>
            {message && <Alert severity="warning">{message}</Alert>}
            {hasPending && !message && !mutation.isPending && (
              <Alert severity="info">有尚未確認的建立請求，請先取得原結果。</Alert>
            )}
            <TextField
              inputRef={nameInput}
              label="職務檔案名稱"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              disabled={hasPending || !!restored.error}
              slotProps={{ htmlInput: { maxLength: 200 } }}
            />
            <TextField
              label="受訪員工姓名"
              value={employeeName}
              onChange={(e) => setEmployeeName(e.target.value)}
              required
              disabled={hasPending || !!restored.error}
              slotProps={{ htmlInput: { maxLength: 200 } }}
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={onClose} disabled={mutation.isPending}>
            返回清單
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={mutation.isPending || !!restored.error}
          >
            {mutation.isPending ? '確認中…' : hasPending ? '重新確認建立結果' : '建立'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
