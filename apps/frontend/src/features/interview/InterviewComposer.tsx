import { useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert, Box, Button, InputBase } from '@mui/material';
import { ArrowUpIcon } from '../../shared/ui/icons';
import type { SubmitTurnRequest, TurnView } from '../../shared/api/generated/types.gen';
import { HttpError, InvalidRequestError } from '../../shared/api/http';
import { interviewError } from './api';
import {
  clearSubmission,
  retainSubmission,
  readPendingSubmission,
  submitAndRecover,
  usePendingSubmission,
} from './submission';
import { interviewKeys } from './queries';
import { isSendKey } from './send-key';

export function InterviewComposer({
  workspaceId,
  disabled,
  controlsDisabled = false,
  onWorkspaceChanged,
}: {
  workspaceId: string;
  disabled: boolean;
  controlsDisabled?: boolean;
  onWorkspaceChanged: () => void;
}) {
  const client = useQueryClient();
  const input = useRef<HTMLTextAreaElement>(null);
  const { request: pending, error: storageError } = usePendingSubmission(workspaceId);
  const [draft, setDraft] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const submission = useMutation({
    mutationFn: async (request: SubmitTurnRequest) => {
      retainSubmission(workspaceId, request);
      setDraft('');
      void client.invalidateQueries({ queryKey: interviewKeys.turns(workspaceId) });
      return submitAndRecover(workspaceId, request);
    },
    onSuccess: (turn, request) => {
      // Cancellation may have already confirmed and retired this in-flight submission.
      if (readPendingSubmission(workspaceId)?.turn_id !== request.turn_id) {
        onWorkspaceChanged();
        return;
      }
      if (client.getQueryState(interviewKeys.turns(workspaceId))) {
        client.setQueryData(interviewKeys.turn(workspaceId, turn.turn_id), turn);
        client.setQueryData<TurnView[]>(interviewKeys.turns(workspaceId), (turns) => [
          ...(turns ?? []).filter((item) => item.turn_id !== turn.turn_id),
          turn,
        ]);
      }
      try {
        clearSubmission(workspaceId);
      } catch {
        setNotice('伺服器已受理，但瀏覽器暫存清理失敗。重新確認仍使用相同輪識別。');
      }
      onWorkspaceChanged();
    },
  });
  const canSend =
    !submission.isPending &&
    !controlsDisabled &&
    !storageError &&
    (pending !== null || (!disabled && draft.trim() !== ''));
  async function send(): Promise<void> {
    if (!canSend) return;
    setNotice(null);
    const request = readPendingSubmission(workspaceId) ?? {
      turn_id: crypto.randomUUID(),
      input: draft,
    };
    try {
      await submission.mutateAsync(request);
    } catch (error) {
      if (
        error instanceof InvalidRequestError ||
        (error instanceof HttpError && [400, 404, 409, 422].includes(error.status))
      ) {
        setDraft(request.input);
        clearSubmission(workspaceId);
        void client.invalidateQueries({ queryKey: interviewKeys.turns(workspaceId) });
      }
      setNotice(interviewError(error));
      return;
    }
    setDraft('');
    input.current?.focus();
  }
  return (
    <Box component="section" aria-label="訪談輸入" className="composer-dock">
      {(notice || storageError) && (
        <Alert severity="warning">{notice ?? storageError}</Alert>
      )}
      {pending && (
        <Alert severity="info">原請求尚待確認，將沿同一輪識別查回或重送相同內容。</Alert>
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <div className="composer-card">
          <InputBase
            inputRef={input}
            className="composer-input"
            multiline
            minRows={1}
            maxRows={8}
            fullWidth
            placeholder="輸入訪談內容…"
            slotProps={{ input: { 'aria-label': '訪談內容' } }}
            value={pending?.input ?? draft}
            onChange={(event) => setDraft(event.target.value)}
            readOnly={pending !== null}
            disabled={submission.isPending || storageError !== null}
            onKeyDown={(event) => {
              if (isSendKey(event)) {
                event.preventDefault();
                if (canSend) event.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <Button
            type="submit"
            variant="contained"
            aria-label={pending ? '重新確認原請求' : '送出訪談'}
            disabled={!canSend}
            className="composer-send"
            startIcon={<ArrowUpIcon />}
          >
            {pending ? '重新確認' : submission.isPending ? '送出中' : '送出'}
          </Button>
        </div>
        <p className="composer-hint">
          Enter 送出，Shift＋Enter 換行。處理中可先保留下一則草稿。
        </p>
      </form>
    </Box>
  );
}
