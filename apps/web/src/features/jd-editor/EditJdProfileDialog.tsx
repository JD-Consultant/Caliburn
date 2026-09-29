/** Edit a captured formal base; unclear results keep the original intent across remounts. */
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
import type { JdProfileView } from '../../shared/api/generated/jd-profile-view';
import type { ReviseJdProfileRequest } from '../../shared/api/generated/revise-jd-profile-request';
import { ApiError } from '../../shared/api/http';
import { isReviseJdProfileRequest } from '../../shared/api/validation';
import { reviseJdProfile } from './jd-profile-api';
import {
  clearPendingProfile,
  makeProfileDraft,
  profileFields,
  profileLabels,
  readPendingProfile,
  retainPendingProfile,
} from './profile-command';

interface Props {
  jobFileId: string;
  baseline: JdProfileView;
  onClose: () => void;
  onRefresh: () => void;
}

function restoreProfile(jobFileId: string): {
  command: ReviseJdProfileRequest | null;
  error: string | null;
} {
  try {
    return { command: readPendingProfile(jobFileId), error: null };
  } catch {
    return {
      command: null,
      error: '無法讀取本分頁的待確認 JD 修改。請確認瀏覽器儲存權限，勿重複送出。',
    };
  }
}

export function EditJdProfileDialog({ jobFileId, baseline, onClose, onRefresh }: Props) {
  const [restored] = useState(() => restoreProfile(jobFileId));
  const [pending, setPending] = useState(restored.command);
  const [draft, setDraft] = useState(() => makeProfileDraft(baseline.profile, restored.command));
  const [message, setMessage] = useState(restored.error);
  const [isRejected, setIsRejected] = useState(false);
  const titleInput = useRef<HTMLInputElement>(null);
  const inFlight = useRef(false);
  const mutation = useMutation({
    mutationFn: (command: ReviseJdProfileRequest) => reviseJdProfile(jobFileId, command),
    retry: false,
  });

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (inFlight.current || restored.error || isRejected) return;
    const changes = profileFields
      .filter((field) => draft[field] !== (baseline.profile[field] ?? ''))
      .map((field) =>
        draft[field] === ''
          ? { action: 'clear_field', field }
          : { action: 'set_field', field, value: draft[field] },
      );
    if (!pending && changes.length === 0) {
      setMessage('沒有修改任何欄位，尚未送出。');
      return;
    }
    const command = pending ?? {
      command_id: crypto.randomUUID(),
      expected_revision_id: baseline.revision_id,
      changes,
    };
    if (!isReviseJdProfileRequest(command)) {
      setMessage('欄位不能只有空白或包含無法儲存的字元；若要清空，請刪除全部文字。');
      return;
    }
    try {
      retainPendingProfile(jobFileId, command);
    } catch {
      setMessage('瀏覽器無法保留本次修改識別，尚未送出。請確認儲存權限後重試。');
      return;
    }
    inFlight.current = true;
    setPending(command);
    setMessage(null);
    try {
      await mutation.mutateAsync(command);
      try {
        clearPendingProfile(jobFileId);
      } catch {
        // A residual original command can only retrieve the already fixed result.
      }
      onRefresh();
    } catch (error) {
      if (error instanceof ApiError && [400, 404, 409, 422].includes(error.status ?? 0)) {
        try {
          clearPendingProfile(jobFileId);
          setPending(null);
          setIsRejected(true);
          setMessage(
            '修改未被接受，可能已有其他修改或顧問正在處理。請先讀取目前 JD 再決定，不會自動覆蓋。',
          );
        } catch {
          setMessage('修改未被接受，且待確認紀錄無法清除。請確認瀏覽器儲存權限。');
        }
      } else {
        setMessage('JD 修改結果尚未確認。請重新確認原請求，不會重複寫入或覆蓋後續修改。');
      }
    } finally {
      inFlight.current = false;
    }
  }

  return (
    <Dialog
      open
      fullWidth
      maxWidth="sm"
      aria-labelledby="edit-jd-profile-title"
      onClose={mutation.isPending ? undefined : onClose}
      slotProps={{ transition: { onEntered: () => titleInput.current?.focus() } }}
    >
      <form
        onSubmit={(event) => {
          void submit(event);
        }}
      >
        <DialogTitle id="edit-jd-profile-title">編輯 JD 基本資料</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <p>只儲存修改的欄位。未知可留空；刪除全部文字會清空該欄，不影響其他內容。</p>
            {message && <Alert severity="warning">{message}</Alert>}
            {pending && !message && !mutation.isPending && (
              <Alert severity="info">有尚未確認的 JD 修改，請先取得原結果。</Alert>
            )}
            {profileFields.map((field) => (
              <TextField
                key={field}
                label={profileLabels[field]}
                value={draft[field]}
                inputRef={field === 'job_title' ? titleInput : undefined}
                multiline={field === 'purpose'}
                minRows={field === 'purpose' ? 3 : undefined}
                onChange={(event) =>
                  setDraft((previous) => ({ ...previous, [field]: event.target.value }))
                }
                disabled={pending !== null || !!restored.error || isRejected}
                helperText={
                  field === 'purpose' ? '簡短說明替誰、透過哪類工作、達成什麼持續價值。' : undefined
                }
              />
            ))}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={onClose} disabled={mutation.isPending}>
            返回 JD
          </Button>
          {isRejected ? (
            <Button onClick={onRefresh}>讀取目前 JD</Button>
          ) : (
            <Button
              type="submit"
              variant="contained"
              disabled={mutation.isPending || !!restored.error}
            >
              {mutation.isPending ? '確認中…' : pending ? '重新確認修改結果' : '儲存基本資料'}
            </Button>
          )}
        </DialogActions>
      </form>
    </Dialog>
  );
}
