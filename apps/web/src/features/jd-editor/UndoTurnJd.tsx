/** A conditional JD-only command; the server decides eligibility and preserves its original result. */
import { useId, useRef, useState } from 'react';
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
import { ApiError } from '../../shared/api/http';
import { reportDiagnostic } from '../../shared/diagnostics';
import { undoTurnJd } from './jd-undo-api';
import { TurnJdChanges } from './TurnJdChanges';

interface Props {
  jobFileId: string;
  executionId: string;
  refresh: () => Promise<void>;
}

export function UndoTurnJd({ jobFileId, executionId, refresh }: Props) {
  const [open, setOpen] = useState(false);
  const [refreshFailed, setRefreshFailed] = useState(false);
  const titleId = useId();
  const inFlight = useRef(false);
  const undo = useMutation({
    mutationFn: async (): Promise<{ refreshFailed: boolean }> => {
      await undoTurnJd(jobFileId, executionId);
      // Read today's formal JD, not the historical result returned by an idempotent replay.
      try {
        await refresh();
        return { refreshFailed: false };
      } catch {
        reportDiagnostic({ event: 'command_failure', kind: 'refresh', jobFileId, executionId });
        return { refreshFailed: true };
      }
    },
    retry: false,
    networkMode: 'always',
  });
  const rejected =
    undo.error instanceof ApiError &&
    undo.error.status === 409 &&
    [
      'consultant_turn_active',
      'jd_undo_unavailable',
      'jd_undo_conflict',
      'jd_command_conflict',
    ].includes(undo.error.code ?? '');

  async function confirmUndo(): Promise<void> {
    if (inFlight.current || rejected) return;
    inFlight.current = true;
    try {
      await undo.mutateAsync(undefined, {
        onSuccess(result) {
          setOpen(false);
          setRefreshFailed(result.refreshFailed);
        },
      });
    } catch {
      // Only an unconfirmed POST reaches here; read failures preserve known acceptance.
    } finally {
      inFlight.current = false;
    }
  }

  return (
    <Stack spacing={1} sx={{ mt: 1 }}>
      <div className="process-actions">
        <TurnJdChanges
          key={`${jobFileId}:${executionId}`}
          jobFileId={jobFileId}
          executionId={executionId}
        />
        {!undo.isSuccess && (
          <Button
            size="small"
            onClick={() => {
              undo.reset();
              setOpen(true);
            }}
          >
            撤回這輪 JD
          </Button>
        )}
      </div>
      {undo.isSuccess && (
        <Alert severity="success">這輪 JD 撤回已確認；訪談與工作記憶未撤回。</Alert>
      )}
      {refreshFailed && (
        <Alert severity="warning">撤回已保存，但畫面尚未更新。請重新開啟這份職務檔案。</Alert>
      )}
      <Dialog
        open={open}
        onClose={undo.isPending ? undefined : () => setOpen(false)}
        aria-labelledby={titleId}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle id={titleId}>確認撤回這輪 JD 修改</DialogTitle>
        <DialogContent>
          <Typography>只撤回這輪對 JD 的修改，不撤回訪談或工作記憶（Memory）。</Typography>
          <Typography sx={{ mt: 1 }}>
            若已有後續人工修改或其他 JD
            修改，伺服器將拒絕撤回，不覆蓋目前內容。是否可撤回由伺服器確認。
          </Typography>
          {undo.isError && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              {rejected
                ? '這輪目前不允許撤回，可能已有後續修改或處理中的訪談。沒有覆蓋目前 JD；請重讀目前稿後再判斷。'
                : '撤回結果尚未確認，不會自動重送。可重新確認同一輪撤回；關閉視窗不代表撤回未生效。'}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" disabled={undo.isPending} onClick={() => setOpen(false)}>
            關閉
          </Button>
          <Button
            color="error"
            variant="contained"
            disabled={undo.isPending || rejected}
            onClick={() => {
              void confirmUndo();
            }}
          >
            {undo.isPending
              ? '正在確認撤回…'
              : undo.isError && !rejected
                ? '重新確認同輪撤回'
                : '確認只撤回這輪 JD'}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
