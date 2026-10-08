/** One file's local draft and server-verified consultant turn. */
import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { ReactNode, SubmitEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Box, Button, InputBase } from '@mui/material';
import type { SubmitInterviewInput } from '../../shared/api/generated/submit-interview-input';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import { ApiError, describeReadError } from '../../shared/api/http';
import { ArrowUpIcon } from '../../shared/ui/icons';
import {
  clearTurnHint,
  consultantTurnByCommandQuery,
  consultantTurnQuery,
  currentConsultantTurnQuery,
  isSubmitInterviewInput,
  isInputAdmissionRejection,
  isTerminalTurn,
  readTurnHint,
  readTurnHintSnapshot,
  retainTurnHint,
  subscribeTurnHint,
  submitInterviewInput,
} from './interview-turn-api';
import type { TurnHint } from './interview-turn-api';
import { ConsultantTurnControls } from './ConsultantTurnControls';
import { CompletedTurnRefresh } from './CompletedTurnRefresh';
import { isSendKey } from './send-key';
import { TurnLog } from './TurnLog';

const statusText: Record<ConsultantTurn['status'], string> = {
  active: '顧問正在處理，尚未正式完成。',
  paused: '這次處理已暫停，原輸入仍保留，尚未正式完成。',
  completed: '這次訪談已完成並保存。',
  cancelled: '這次處理已取消，原輸入未列入正式訪談。',
  failed: '這次處理未能完成，原輸入未列入正式訪談。請確認服務狀態後再主動送出。',
};

function restoreHint(jobFileId: string): { hint: TurnHint | null; error: string | null } {
  try {
    return { hint: readTurnHint(jobFileId), error: null };
  } catch {
    return {
      hint: null,
      error: '無法讀取待確認訪談識別。請確認瀏覽器儲存權限後重新開啟，勿重複送出。',
    };
  }
}

interface ComposerProps {
  jobFileId: string;
  /** Floats just above the dock (the page's "back to the newest message" button); the dock positions it. */
  aboveDock?: ReactNode;
}

export function InterviewComposer(props: ComposerProps) {
  return <ComposerForFile key={props.jobFileId} {...props} />;
}

function ComposerForFile({ jobFileId, aboveDock }: ComposerProps) {
  const [restored] = useState(() => restoreHint(jobFileId));
  const hint = useSyncExternalStore(subscribeTurnHint, () => readTurnHintSnapshot(jobFileId));
  const [draft, setDraft] = useState('');
  const [pendingInput, setPending] = useState<SubmitInterviewInput | null>(null);
  const retainedInput = pendingInput?.command_id === hint?.command_id ? pendingInput : null;
  const [message, setMessage] = useState(restored.error);
  const inFlight = useRef(false);
  const queryClient = useQueryClient();
  const recoveringCommand = hint && !hint.execution_id && !retainedInput ? hint.command_id : null;
  const recovery = useQuery(consultantTurnByCommandQuery(jobFileId, recoveringCommand));
  const discovery = useQuery({
    ...currentConsultantTurnQuery(jobFileId),
    enabled: (query) => !hint && !restored.error && !query.state.data?.turn,
  });
  const executionId = hint
    ? (hint.execution_id ?? recovery.data?.execution_id ?? null)
    : (discovery.data?.turn?.execution_id ?? null);
  const turn = useQuery(consultantTurnQuery(jobFileId, executionId));
  const submission = useMutation({
    mutationFn: (command: SubmitInterviewInput) => submitInterviewInput(jobFileId, command),
    retry: false,
  });
  const verified = turn.isError ? undefined : turn.data;
  const discovering = !hint && !executionId && !restored.error;
  const readyForNewInput = discovery.isSuccess && !discovery.isFetching && !discovery.data.turn;
  const canStartNextInput = verified?.status === 'completed';
  // Completion may be confirmed through another page, not just this POST's acknowledgement.
  const pending = canStartNextInput ? null : retainedInput;

  useEffect(() => {
    if (!recoveringCommand || !recovery.data) return;
    try {
      if (readTurnHint(jobFileId)?.command_id === recoveringCommand) {
        retainTurnHint(jobFileId, {
          command_id: recoveringCommand,
          execution_id: recovery.data.execution_id,
        });
      }
    } catch {
      // The command hint already persists; another reload can resolve that same ID again.
    }
  }, [recoveringCommand, recovery.data, jobFileId]);

  async function submit(event: SubmitEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (inFlight.current || restored.error || (executionId && !canStartNextInput)) return;
    if (hint && !pending && !canStartNextInput) return;
    if (!pending && !readyForNewInput && !canStartNextInput) return;
    const command = pending ?? { command_id: crypto.randomUUID(), text: draft };
    if (!isSubmitInterviewInput(command)) {
      setMessage('請填寫訪談內容，不能只有空白或包含無效字元。');
      return;
    }
    try {
      const existing = readTurnHint(jobFileId);
      const replacesCompletedHint =
        canStartNextInput &&
        existing?.command_id === hint?.command_id &&
        existing?.execution_id === verified.execution_id;
      if (existing && existing.command_id !== command.command_id && !replacesCompletedHint) {
        setMessage('另一個頁面已有待確認訪談。請重新開啟這份檔案，先查回原處理狀態。');
        return;
      }
      retainTurnHint(jobFileId, { command_id: command.command_id, execution_id: null });
    } catch {
      setMessage('瀏覽器無法保留本次訪談識別，尚未送出。請確認儲存權限後重試。');
      return;
    }
    setPending(command);
    setDraft('');
    setMessage(null);
    inFlight.current = true;
    if (canStartNextInput) {
      // A rejected new input must rediscover current work, not reuse the old completion.
      void queryClient.resetQueries({
        queryKey: currentConsultantTurnQuery(jobFileId).queryKey,
        exact: true,
      });
    }
    try {
      const accepted = await submission.mutateAsync(command);
      const acceptedHint = { command_id: command.command_id, execution_id: accepted.execution_id };
      try {
        retainTurnHint(jobFileId, acceptedHint);
      } catch {
        setMessage('原輸入已受理，但瀏覽器未能保留處理識別。請保留此頁以查看結果。');
      }
      // If saving the execution hint failed, the retained command is now resolved by GET.
      setPending(null);
    } catch (error) {
      // A later preflight rejection cannot disprove an earlier uncertain acceptance.
      if (!pending && isInputAdmissionRejection(error)) {
        try {
          clearTurnHint(jobFileId, command.command_id);
          setPending(null);
          setDraft(command.text);
          setMessage(
            error.code === 'model_not_configured'
              ? '尚未設定模型服務，這次輸入未被接受，文字仍保留。請先完成後端模型設定。'
              : error.status === 503
                ? '本機服務尚未就緒，這次輸入未被接受，文字仍保留。請確認服務設定後再送出。'
                : '這次輸入未被接受，文字仍保留。請確認檔案與內容後再送出。',
          );
        } catch {
          setMessage('輸入未被接受，但待確認識別無法清除。請確認瀏覽器儲存權限。');
        }
      } else if (error instanceof ApiError && error.status === 409) {
        setMessage(
          '同一檔案已有處理中的訪談，或原命令內容不符。請先核對原請求；不會另建一次輸入。',
        );
      } else {
        // Render uncertainty from the unresolved command, so a later confirmation retires it.
        setMessage(null);
      }
    } finally {
      inFlight.current = false;
    }
  }

  function startNext(restoreText: boolean): void {
    if (!verified || !isTerminalTurn(verified.status)) return;
    try {
      if (hint) clearTurnHint(jobFileId, hint.command_id);
    } catch {
      setMessage('無法清除上一個訪談識別，尚未開始新輸入。請確認瀏覽器儲存權限。');
      return;
    }
    setDraft(restoreText ? verified.input_text : '');
    setPending(null);
    setMessage(null);
    submission.reset();
    // Forget the discovery observation, not the retained execution or original input command.
    void queryClient.resetQueries({
      queryKey: currentConsultantTurnQuery(jobFileId).queryKey,
      exact: true,
    });
  }

  const showForm = canStartNextInput || (!executionId && (!hint || pending));
  const sendLabel = submission.isPending
    ? '正在確認送出…'
    : pending
      ? '重新確認原請求'
      : '送出訪談';
  // A plain send is icon-only, as in every chat composer (ChatGPT, Claude, AI Elements' PromptInput);
  // the two states that need words keep their label.
  const iconOnlySend = !submission.isPending && !pending;
  const sendDisabled =
    submission.isPending ||
    restored.error !== null ||
    (!pending && !readyForNewInput && !canStartNextInput);
  return (
    <>
      <div className="composer-log">
        {verified && verified.status !== 'completed' && (
          <TurnLog jobFileId={jobFileId} turn={verified} />
        )}
      </div>
      <Box component="section" aria-label="訪談輸入" className="composer-dock">
        {aboveDock}
        {message && <Alert severity="warning">{message}</Alert>}
        {pending && submission.isError && !message && (
          <Alert severity="warning">
            送出結果尚未確認，文字仍保留。請重新確認原請求，不會建立新的輸入。
          </Alert>
        )}
        {discovering && discovery.isFetching && (
          <p role="status" className="dock-note">
            正在查詢這份檔案是否有進行中的處理…
          </p>
        )}
        {discovering && discovery.isError && (
          <Alert
            severity="error"
            action={
              <Button
                color="inherit"
                onClick={() => {
                  void discovery.refetch();
                }}
              >
                重新查詢進行中處理
              </Button>
            }
          >
            {describeReadError(discovery.error)}
          </Alert>
        )}
        {executionId && turn.isPending && !verified && (
          <p role="status" className="dock-note">
            正在核對這次訪談的處理狀態…
          </p>
        )}
        {executionId && turn.isError && (
          <Alert
            severity="error"
            action={
              <Button
                color="inherit"
                onClick={() => {
                  void turn.refetch();
                }}
              >
                重新讀取狀態
              </Button>
            }
          >
            {describeReadError(turn.error)}
          </Alert>
        )}
        {verified && (
          <>
            {verified.status === 'completed' ? (
              <>
                <p role="status" className="dock-note">
                  {statusText.completed}
                </p>
                <CompletedTurnRefresh key={verified.execution_id} jobFileId={jobFileId} />
              </>
            ) : (
              <Alert severity={verified.status === 'failed' ? 'error' : 'info'}>
                {verified.status === 'active' && verified.pause_requested
                  ? '暫停請求已受理，正在等待安全點停妥，尚未暫停。'
                  : statusText[verified.status]}
              </Alert>
            )}
            <ConsultantTurnControls key={verified.execution_id} turn={verified} />
            {isTerminalTurn(verified.status) && verified.status !== 'completed' && (
              <div className="dock-controls">
                <Button variant="outlined" onClick={() => startNext(true)}>
                  取回原文編輯
                </Button>
                <Button variant="contained" onClick={() => startNext(false)}>
                  開始下一次訪談
                </Button>
              </div>
            )}
          </>
        )}
        {recoveringCommand && !executionId && recovery.isPending && (
          <p role="status" className="dock-note">
            正在依原請求識別查回伺服器原輸入…
          </p>
        )}
        {recoveringCommand && !executionId && recovery.isError && (
          <Alert
            severity="warning"
            action={
              <Button
                color="inherit"
                onClick={() => {
                  void recovery.refetch();
                }}
              >
                重新查回原請求
              </Button>
            }
          >
            {recovery.error instanceof ApiError && recovery.error.status === 404
              ? '尚未查到原請求的受理結果。原文未保存在瀏覽器；請稍後查回，不會另建輸入。'
              : describeReadError(recovery.error)}
          </Alert>
        )}
        {showForm && (
          <form
            onSubmit={(event) => {
              void submit(event);
            }}
          >
            <div className="composer-card">
              <InputBase
                className="composer-input"
                multiline
                minRows={1}
                maxRows={8}
                fullWidth
                placeholder="輸入訪談內容…"
                slotProps={{ input: { 'aria-label': '訪談內容' } }}
                value={pending?.text ?? draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (!isSendKey(event)) return;
                  // Enter presses the send button, or does nothing while that is disabled; it never breaks a line.
                  event.preventDefault();
                  if (!sendDisabled) event.currentTarget.form?.requestSubmit();
                }}
                disabled={(hint !== null && !canStartNextInput) || restored.error !== null}
              />
              <Button
                type="submit"
                variant="contained"
                startIcon={<ArrowUpIcon strokeWidth={2.25} />}
                aria-label={iconOnlySend ? sendLabel : undefined}
                title={iconOnlySend ? `${sendLabel}（Enter）` : undefined}
                disabled={sendDisabled}
                className={iconOnlySend ? 'composer-send composer-send--icon' : 'composer-send'}
              >
                {iconOnlySend ? null : sendLabel}
              </Button>
            </div>
            <p className="composer-hint">
              原輸入會先保留；顧問完成並保存後，才會列入正式訪談並更新 JD。
            </p>
          </form>
        )}
      </Box>
    </>
  );
}
