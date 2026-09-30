/** One file's local draft and server-verified consultant turn. */
import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Box, Button, Stack, TextField, Typography } from '@mui/material';
import type { SubmitInterviewInput } from '../../shared/api/generated/submit-interview-input';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import { ApiError, describeReadError } from '../../shared/api/http';
import { SendIcon } from '../../shared/ui/icons';
import {
  clearTurnHint,
  consultantTurnByCommandQuery,
  consultantTurnQuery,
  isSubmitInterviewInput,
  isInputAdmissionRejection,
  isTerminalTurn,
  readTurnHint,
  retainTurnHint,
  submitInterviewInput,
} from './interview-turn-api';
import type { TurnHint } from './interview-turn-api';
import { PublicTurnMessages, StreamingPublicTurnMessages } from './PublicTurnMessages';
import { ConsultantTurnControls } from './ConsultantTurnControls';

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
}

export function InterviewComposer(props: ComposerProps) {
  return <ComposerForFile key={props.jobFileId} {...props} />;
}

function ComposerForFile({ jobFileId }: ComposerProps) {
  const [restored] = useState(() => restoreHint(jobFileId));
  const [hint, setHint] = useState(restored.hint);
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState<SubmitInterviewInput | null>(null);
  const [message, setMessage] = useState(restored.error);
  const inFlight = useRef(false);
  const refreshed = useRef<string | null>(null);
  const queryClient = useQueryClient();
  const recoveringCommand = hint && !hint.execution_id && !pending ? hint.command_id : null;
  const recovery = useQuery(consultantTurnByCommandQuery(jobFileId, recoveringCommand));
  const executionId = hint?.execution_id ?? recovery.data?.execution_id ?? null;
  const turn = useQuery(consultantTurnQuery(jobFileId, executionId));
  const submission = useMutation({
    mutationFn: (command: SubmitInterviewInput) => submitInterviewInput(jobFileId, command),
    retry: false,
  });
  const verified = turn.isError ? undefined : (turn.data ?? recovery.data);

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

  useEffect(() => {
    if (verified?.status !== 'completed' || refreshed.current === verified.execution_id) return;
    refreshed.current = verified.execution_id;
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ['job-file', jobFileId, 'formal-interviews'] }),
      queryClient.invalidateQueries({ queryKey: ['jd-profile', jobFileId] }),
      queryClient.invalidateQueries({ queryKey: ['jd-work', jobFileId] }),
    ]).catch(() => {
      setMessage('訪談已保存，但畫面尚未更新。請重新開啟這份職務檔案。');
    });
  }, [verified?.status, verified?.execution_id, jobFileId, queryClient]);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (inFlight.current || restored.error || executionId) return;
    if (hint && !pending) return;
    const command = pending ?? { command_id: crypto.randomUUID(), text: draft };
    if (!isSubmitInterviewInput(command)) {
      setMessage('請填寫訪談內容，不能只有空白或包含無效字元。');
      return;
    }
    try {
      const existing = readTurnHint(jobFileId);
      if (existing && existing.command_id !== command.command_id) {
        setMessage('另一個頁面已有待確認訪談。請重新開啟這份檔案，先查回原處理狀態。');
        return;
      }
      retainTurnHint(jobFileId, { command_id: command.command_id, execution_id: null });
    } catch {
      setMessage('瀏覽器無法保留本次訪談識別，尚未送出。請確認儲存權限後重試。');
      return;
    }
    setHint({ command_id: command.command_id, execution_id: null });
    setPending(command);
    setMessage(null);
    inFlight.current = true;
    try {
      const accepted = await submission.mutateAsync(command);
      const acceptedHint = { command_id: command.command_id, execution_id: accepted.execution_id };
      setHint(acceptedHint);
      try {
        retainTurnHint(jobFileId, acceptedHint);
      } catch {
        setMessage('原輸入已受理，但瀏覽器未能保留處理識別。請保留此頁以查看結果。');
      }
    } catch (error) {
      // A later preflight rejection cannot disprove an earlier uncertain acceptance.
      if (!pending && isInputAdmissionRejection(error)) {
        try {
          clearTurnHint(jobFileId, command.command_id);
          setHint(null);
          setPending(null);
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
        setMessage('送出結果尚未確認，文字仍保留。請重新確認原請求，不會建立新的輸入。');
      }
    } finally {
      inFlight.current = false;
    }
  }

  function startNext(restoreText: boolean): void {
    if (!verified || !hint || !isTerminalTurn(verified.status)) return;
    try {
      clearTurnHint(jobFileId, hint.command_id);
    } catch {
      setMessage('無法清除上一個訪談識別，尚未開始新輸入。請確認瀏覽器儲存權限。');
      return;
    }
    setDraft(restoreText ? verified.input_text : '');
    setHint(null);
    setPending(null);
    setMessage(null);
    submission.reset();
  }

  const showForm = !executionId && (!hint || pending);
  return (
    <>
      <div className="composer-log">
        {verified &&
          verified.status !== 'completed' &&
          (verified.status === 'cancelled' ? (
            <div className="msg msg--pending">
              <details>
                <summary>查看原輸入</summary>
                <p style={{ whiteSpace: 'pre-wrap' }}>{verified.input_text}</p>
              </details>
            </div>
          ) : (
            <div className="msg msg--pending">
              <p className="msg-meta">本次原輸入（尚非正式訪談）</p>
              <p className="interview-text">{verified.input_text}</p>
            </div>
          ))}
        {verified &&
          (verified.status === 'active' ? (
            <StreamingPublicTurnMessages
              key={`${jobFileId}:${verified.execution_id}`}
              jobFileId={jobFileId}
              executionId={verified.execution_id}
              messages={verified.commentary}
            />
          ) : (
            <PublicTurnMessages
              messages={verified.commentary}
              terminal={isTerminalTurn(verified.status)}
            />
          ))}
      </div>
      <Box component="section" aria-label="訪談輸入" className="composer-dock">
        {message && <Alert severity="warning">{message}</Alert>}
        {executionId && turn.isPending && !verified && (
          <p role="status">正在核對這次訪談的處理狀態…</p>
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
            <Alert
              severity={
                verified.status === 'failed'
                  ? 'error'
                  : verified.status === 'completed'
                    ? 'success'
                    : 'info'
              }
            >
              {verified.status === 'active' && verified.pause_requested
                ? '暫停請求已受理，正在等待安全點停妥，尚未暫停。'
                : statusText[verified.status]}
            </Alert>
            <ConsultantTurnControls key={verified.execution_id} turn={verified} />
            {isTerminalTurn(verified.status) && (
              <Stack direction="row" spacing={1}>
                {verified.status !== 'completed' && (
                  <Button onClick={() => startNext(true)}>取回原文編輯</Button>
                )}
                <Button onClick={() => startNext(false)}>開始下一次訪談</Button>
              </Stack>
            )}
          </>
        )}
        {recoveringCommand && !executionId && recovery.isPending && (
          <p role="status">正在依原請求識別查回伺服器原輸入…</p>
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
            <Stack spacing={1}>
              <TextField
                label="訪談內容"
                multiline
                minRows={2}
                maxRows={8}
                fullWidth
                value={pending?.text ?? draft}
                onChange={(event) => setDraft(event.target.value)}
                disabled={hint !== null || restored.error !== null}
              />
              <Stack
                direction="row"
                spacing={2}
                sx={{ alignItems: 'center', justifyContent: 'space-between' }}
              >
                <Typography variant="caption" color="text.secondary">
                  原輸入會先保留；顧問完成並保存後，才會列入正式訪談並更新 JD。
                </Typography>
                <Button
                  type="submit"
                  variant="contained"
                  startIcon={<SendIcon />}
                  disabled={submission.isPending || restored.error !== null}
                  sx={{ flex: 'none' }}
                >
                  {submission.isPending ? '正在確認送出…' : pending ? '重新確認原請求' : '送出訪談'}
                </Button>
              </Stack>
            </Stack>
          </form>
        )}
      </Box>
    </>
  );
}
