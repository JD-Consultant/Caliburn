/** Commands target the existing turn; only refreshed server state declares their effect. */
import { useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Stack, Typography } from '@mui/material';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import { CloseIcon, PauseIcon, PlayIcon } from '../../shared/ui/icons';
import { ApiError } from '../../shared/api/http';
import { consultantTurnQuery, controlConsultantTurn, isTerminalTurn } from './interview-turn-api';
import type { ConsultantControl } from './interview-turn-api';

const labels = { pause: '暫停處理', resume: '繼續處理', cancel: '取消處理' };
const icons = { pause: <PauseIcon />, resume: <PlayIcon />, cancel: <CloseIcon /> };

export function ConsultantTurnControls({ turn }: { turn: ConsultantTurn }) {
  const queryClient = useQueryClient();
  const inFlight = useRef(false);
  const command = useMutation({
    mutationFn: (control: ConsultantControl) =>
      controlConsultantTurn(turn.job_file_id, turn.execution_id, control),
    retry: false,
    networkMode: 'always',
    onSettled: () =>
      queryClient.invalidateQueries({
        queryKey: consultantTurnQuery(turn.job_file_id, turn.execution_id).queryKey,
        exact: true,
      }),
  });

  async function act(control: ConsultantControl): Promise<void> {
    if (inFlight.current || !turn.allowed_controls.some((allowed) => allowed === control)) return;
    inFlight.current = true;
    try {
      await command.mutateAsync(control);
    } catch {
      // The mutation exposes a safe warning; the original turn is re-read even on lost replies.
    } finally {
      inFlight.current = false;
    }
  }

  if (isTerminalTurn(turn.status)) return null;
  return (
    <Stack spacing={1}>
      {command.isError && (
        <Alert severity="warning">
          {command.error instanceof ApiError && command.error.status === 409
            ? '目前狀態不允許這項控制，已重新查詢原處理狀態。請依目前狀態選擇下一步。'
            : '控制結果尚未確認，已重新查詢原處理狀態；不會自動重送。請依目前狀態選擇下一步。'}
        </Alert>
      )}
      {command.isPending && <Typography role="status">正在確認控制結果…</Typography>}
      {turn.allowed_controls.length > 0 && (
        <Stack direction="row" spacing={1}>
          {turn.allowed_controls.map((control) => (
            <Button
              key={control}
              color={control === 'cancel' ? 'warning' : 'primary'}
              variant="outlined"
              size="small"
              startIcon={icons[control]}
              disabled={command.isPending}
              onClick={() => {
                void act(control);
              }}
            >
              {labels[control]}
            </Button>
          ))}
        </Stack>
      )}
      {turn.allowed_controls.some((control) => control === 'cancel') && (
        <Typography variant="body2">
          取消會放棄本輪候選與原輸入的正式採用，保留本輪開始前的正式 JD 與工作記憶。
        </Typography>
      )}
    </Stack>
  );
}
