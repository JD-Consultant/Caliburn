/** A submission keeps its identity until the backend acknowledges the original result. */
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
import { creationCommand } from './job-file-commands';
import type { CreationRejection } from './job-file-commands';

interface Props {
  onClose: () => void;
  onCreated: (jobFileId: string) => void;
}

function creationMessage<C>(
  command: StoredCommandState<C, JobFile, CreationRejection>,
): string | null {
  switch (command.issue) {
    case null:
      break;
    case 'display':
      return '本次建立已成功，但畫面未能更新。請返回清單核對目前狀態。';
    case 'restore':
      return '無法讀取本分頁的待確認建立紀錄。請先確認瀏覽器儲存權限，勿重複建立。';
    case 'invalid':
      return '請填寫職務檔案名稱與受訪員工姓名，各 1–200 字，不能只有空白。';
    case 'retain':
      return '瀏覽器無法保留本次建立識別，尚未送出。請確認儲存權限後重試。';
  }
  const outcome = command.outcome;
  if (!outcome) return null;
  if (outcome.status === 'unknown')
    return '建立結果尚未確認。請重新確認原請求，不會另外建立一份檔案。';
  if (outcome.status === 'rejected' && outcome.reason === 'deleted') {
    const detail =
      outcome.acknowledgement === 'changed'
        ? '本分頁另有待確認請求，請返回清單核對。'
        : outcome.acknowledgement === 'unavailable'
          ? '瀏覽器待確認紀錄未能清除，請確認儲存權限後重新確認原結果。'
          : outcome.refreshFailed
            ? '清單未能重新讀取，請返回清單核對。'
            : '可返回清單，或另行建立新檔案。';
    return `這次建立的檔案已刪除，原請求不會重新建立。${detail}`;
  }
  if (outcome.acknowledgement === 'changed')
    return outcome.status === 'accepted'
      ? '本次建立已成功，但本分頁待確認紀錄已變更。請返回清單核對目前狀態。'
      : '本次建立未被接受，但本分頁待確認紀錄已變更。請返回清單核對目前狀態。';
  if (outcome.status === 'accepted')
    return outcome.refreshFailed
      ? '本次建立已成功，但清單未能重新讀取。請返回清單核對目前狀態。'
      : null;
  return outcome.acknowledgement === 'unavailable'
    ? '建立未被接受，且瀏覽器待確認紀錄未能清除。請確認儲存權限後重試。'
    : '這次建立未被接受，請檢查名稱與姓名後重新送出。';
}

export function CreateJobFileDialog({ onClose, onCreated }: Props) {
  const queryClient = useQueryClient();
  const submission = useStoredCommand(creationCommand(queryClient), (file) =>
    onCreated(file.job_file_id),
  );
  const nameInput = useRef<HTMLInputElement>(null);
  const pending = submission.pending;
  const hasPending = pending !== null;
  const [displayName, setDisplayName] = useState(pending?.display_name ?? '');
  const [employeeName, setEmployeeName] = useState(pending?.employee_name ?? '');
  const message = creationMessage(submission);
  const outcome = submission.outcome;
  const settledWithoutCurrentCommand =
    outcome?.status !== 'unknown' && outcome?.acknowledgement === 'changed'
      ? outcome.status === 'accepted'
        ? 'success'
        : 'rejected'
      : null;

  function submit(event: SubmitEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (submission.blocked) return;
    void submission.send(
      pending ?? {
        command_id: crypto.randomUUID(),
        display_name: displayName,
        employee_name: employeeName,
      },
    );
  }

  return (
    <Dialog
      open
      onClose={submission.isSending ? undefined : onClose}
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
            {message && (
              <Alert severity={settledWithoutCurrentCommand === 'success' ? 'info' : 'warning'}>
                {message}
              </Alert>
            )}
            {hasPending && !message && !submission.isSending && (
              <Alert severity="info">有尚未確認的建立請求，請先取得原結果。</Alert>
            )}
            <TextField
              inputRef={nameInput}
              label="職務檔案名稱"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              disabled={hasPending || submission.blocked}
              slotProps={{ htmlInput: { maxLength: 200 } }}
            />
            <TextField
              label="受訪員工姓名"
              value={employeeName}
              onChange={(e) => setEmployeeName(e.target.value)}
              required
              disabled={hasPending || submission.blocked}
              slotProps={{ htmlInput: { maxLength: 200 } }}
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button variant="outlined" onClick={onClose} disabled={submission.isSending}>
            返回清單
          </Button>
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
                ? '建立已成功'
                : settledWithoutCurrentCommand === 'rejected'
                  ? '建立未被接受'
                  : hasPending
                    ? '重新確認建立結果'
                    : '建立'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
