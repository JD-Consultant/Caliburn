/** 永久刪除只接受明確確認；失敗保留相同目標，供使用者手動重試。 */
import { useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material';
import type { JobFile } from '../../shared/api/generated/job-file-list';
import { ApiError } from '../../shared/api/http';
import { deleteJobFile } from './job-file-api';

type Props = {
  file: JobFile;
  onClose: () => void;
  onDeleted: (jobFileId: string) => Promise<void>;
};

export function DeleteJobFileDialog({ file, onClose, onDeleted }: Props) {
  const cancelButton = useRef<HTMLButtonElement>(null);
  const deletion = useMutation({
    mutationFn: () => deleteJobFile(file.job_file_id),
    retry: false,
    onSuccess: () => onDeleted(file.job_file_id),
  });

  return (
    <Dialog
      open
      onClose={deletion.isPending ? undefined : onClose}
      fullWidth
      maxWidth="sm"
      aria-labelledby="delete-file-title"
      aria-describedby="delete-file-description"
      slotProps={{
        transition: {
          onEntered: () => {
            const active = document.activeElement;
            const dialog = cancelButton.current?.closest('[role="dialog"]');
            // 使用者已選擇按鈕時，不在動畫結束後搶回焦點。
            if (active instanceof HTMLButtonElement && dialog?.contains(active)) return;
            cancelButton.current?.focus();
          },
        },
      }}
    >
      <DialogTitle id="delete-file-title">刪除職務檔案</DialogTitle>
      <DialogContent>
        <Stack spacing={2} id="delete-file-description">
          <Typography component="p">
            確定永久刪除「{file.display_name}」（受訪者：{file.employee_name}）？
          </Typography>
          <Typography component="p">
            此檔案的所有訪談、職務說明書（JD）、Memory 與執行紀錄都將永久刪除，且不可復原。
          </Typography>
          {deletion.isError && (
            <Alert severity="error">
              {deletion.error instanceof ApiError && deletion.error.code === 'job_file_busy'
                ? '請先完成或取消顧問工作，或等候 Memory 整理結束，再刪除檔案。'
                : '刪除結果尚未確認，可能已完成刪除。請重試刪除同一份檔案以確認結果。'}
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button ref={cancelButton} autoFocus onClick={onClose} disabled={deletion.isPending}>
          取消
        </Button>
        <Button
          variant="contained"
          color="error"
          disabled={deletion.isPending}
          onClick={() => deletion.mutate()}
        >
          {deletion.isPending ? '正在刪除…' : deletion.isError ? '重試刪除' : '永久刪除'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
