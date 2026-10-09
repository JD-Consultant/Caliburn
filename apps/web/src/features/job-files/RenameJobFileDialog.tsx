/** Rename a label from an observed base; never silently upgrade a rejected command. */
import { useRef, useState } from 'react';
import type { SubmitEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
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
import { useStoredCommand } from '../../shared/commands/use-stored-command';
import type { StoredCommandState } from '../../shared/commands/use-stored-command';
import { focusDialogInput } from '../../shared/ui/dialog-focus';
import { renameCommand } from './job-file-commands';

interface Props {
  file: JobFile;
  onClose: () => void;
}

function renameMessage<C>(command: StoredCommandState<C, JobFile>): string | null {
  switch (command.issue) {
    case null:
      break;
    case 'display':
      return '本次改名已成功，但畫面未能更新。請返回清單核對目前狀態。';
    case 'restore':
      return '無法讀取本分頁的待確認改名紀錄。請確認瀏覽器儲存權限，勿重複改名。';
    case 'invalid':
      return '名稱須為 1–200 字，不能只有空白。';
    case 'retain':
      return '瀏覽器無法保留本次改名識別，尚未送出。請確認儲存權限後重試。';
  }
  const outcome = command.outcome;
  if (!outcome) return null;
  if (outcome.status === 'unknown')
    return '改名結果尚未確認。請重新確認原請求，不會再次覆蓋後來的名稱。';
  if (outcome.acknowledgement === 'changed')
    return outcome.status === 'accepted'
      ? '本次改名已成功，但本分頁待確認紀錄已變更。請返回清單核對目前狀態。'
      : '本次改名未被接受，但本分頁待確認紀錄已變更。請返回清單核對目前狀態。';
  if (outcome.status === 'accepted')
    return outcome.refreshFailed
      ? '本次改名已成功，但目前名稱未能重新讀取。請返回清單核對目前狀態。'
      : null;
  return outcome.acknowledgement === 'unavailable'
    ? '改名未被接受，且待確認紀錄無法清除。請確認瀏覽器儲存權限。'
    : '改名未被接受。請讀取目前名稱後再決定，不會自動覆蓋其他修改。';
}

export function RenameJobFileDialog({ file, onClose }: Props) {
  const queryClient = useQueryClient();
  const definition = renameCommand(file.job_file_id, queryClient);
  const submission = useStoredCommand(definition, onClose);
  const pending = submission.pending;
  const [displayName, setDisplayName] = useState(pending?.display_name ?? file.display_name);
  const message = renameMessage(submission);
  const outcome = submission.outcome;
  const isRejected = outcome?.status === 'rejected' && outcome.acknowledgement === 'cleared';
  const settledWithoutCurrentCommand =
    outcome?.status !== 'unknown' && outcome?.acknowledgement === 'changed'
      ? outcome.status === 'accepted'
        ? 'success'
        : 'rejected'
      : null;
  const nameInput = useRef<HTMLInputElement>(null);

  function submit(event: SubmitEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (submission.blocked || isRejected) return;
    void submission.send(
      pending ?? {
        command_id: crypto.randomUUID(),
        expected_name_revision: file.name_revision,
        display_name: displayName,
      },
    );
  }

  return (
    <Dialog
      open
      onClose={submission.isSending ? undefined : onClose}
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
            {message && (
              <Alert severity={settledWithoutCurrentCommand === 'success' ? 'info' : 'warning'}>
                {message}
              </Alert>
            )}
            {pending && !message && !submission.isSending && (
              <Alert severity="info">有尚未確認的改名請求，請先取得原結果。</Alert>
            )}
            <TextField
              inputRef={nameInput}
              label="職務檔案名稱"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              required
              disabled={pending !== null || submission.blocked || isRejected}
              slotProps={{ htmlInput: { maxLength: 200 } }}
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button variant="outlined" onClick={onClose} disabled={submission.isSending}>
            返回清單
          </Button>
          {isRejected ? (
            <Button
              variant="contained"
              onClick={() => {
                // The list owns any failed read after this dialog closes.
                void Promise.resolve()
                  .then(() => definition.refresh())
                  .catch(() => {});
                onClose();
              }}
            >
              讀取目前名稱
            </Button>
          ) : (
            <Button
              type="submit"
              variant="contained"
              disabled={
                submission.isSending || submission.blocked || settledWithoutCurrentCommand !== null
              }
            >
              {submission.isSending
                ? '確認中…'
                : settledWithoutCurrentCommand === 'success'
                  ? '改名已成功'
                  : settledWithoutCurrentCommand === 'rejected'
                    ? '改名未被接受'
                    : pending
                      ? '重新確認改名結果'
                      : '儲存名稱'}
            </Button>
          )}
        </DialogActions>
      </form>
    </Dialog>
  );
}
