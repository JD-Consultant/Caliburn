/** Input admission and the local draft; recovery persists IDs only under the file's Web Lock. */
import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import type { SubmitInterviewInput } from '../../shared/api/generated/submit-interview-input';
import { ApiError } from '../../shared/api/http';
import {
  clearTurnHint,
  currentConsultantTurnQuery,
  isInputAdmissionRejection,
  isSubmitInterviewInput,
  isTerminalTurn,
  resolveTurnHint,
  retainTurnHint,
  submitInterviewInput,
  subscribeInterviewDeletion,
} from './interview-turn-api';
import type { TurnHint } from './interview-turn-api';

interface InputAttempt {
  command: SubmitInterviewInput;
  retry: boolean;
  completedHint: TurnHint | null;
  startsNextInput: boolean;
  signal: AbortSignal;
}

type InputOutcome =
  | { status: 'not-sent' }
  | { status: 'accepted'; hintSaved: boolean }
  | { status: 'rejected'; error: ApiError; hintCleared: boolean }
  | { status: 'conflict' }
  | { status: 'unknown' };

export function useInterviewInput(jobFileId: string) {
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState<SubmitInterviewInput | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const inFlight = useRef(false);
  const lifetime = useRef(new AbortController());
  const cache = useQueryClient();

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    const unsubscribe = subscribeInterviewDeletion(jobFileId, () => controller.abort());
    return () => {
      controller.abort();
      unsubscribe();
    };
  }, [jobFileId]);

  function rediscover(): void {
    // Query exposes any failed read; resetting discovery never submits another input.
    void cache
      .resetQueries({
        queryKey: currentConsultantTurnQuery(jobFileId).queryKey,
        exact: true,
      })
      .catch(() => {});
  }

  const mutation = useMutation({
    mutationFn: async (attempt: InputAttempt): Promise<InputOutcome> => {
      const { command, completedHint, signal } = attempt;
      try {
        await retainTurnHint(
          jobFileId,
          { command_id: command.command_id, execution_id: null },
          completedHint,
          signal,
        );
        signal.throwIfAborted();
      } catch {
        return { status: 'not-sent' };
      }
      setDraft('');
      setMessage(null);
      if (attempt.startsNextInput) rediscover();

      let accepted;
      try {
        accepted = await submitInterviewInput(jobFileId, command);
      } catch (error) {
        if (signal.aborted) return { status: 'unknown' };
        // A later admission rejection cannot disprove an earlier uncertain acceptance.
        if (!attempt.retry && isInputAdmissionRejection(error)) {
          try {
            await clearTurnHint(jobFileId, command.command_id);
            return { status: 'rejected', error, hintCleared: true };
          } catch {
            return { status: 'rejected', error, hintCleared: false };
          }
        }
        return error instanceof ApiError && error.status === 409
          ? { status: 'conflict' }
          : { status: 'unknown' };
      }
      if (signal.aborted) return { status: 'accepted', hintSaved: false };
      try {
        await resolveTurnHint(jobFileId, {
          command_id: command.command_id,
          execution_id: accepted.execution_id,
        });
        return { status: 'accepted', hintSaved: true };
      } catch {
        // The POST remains known accepted; by-command GET can resolve the retained ID.
        return { status: 'accepted', hintSaved: false };
      }
    },
    retry: false,
  });

  async function send(
    command: SubmitInterviewInput,
    previous: Pick<InputAttempt, 'retry' | 'completedHint' | 'startsNextInput'>,
  ): Promise<void> {
    const signal = lifetime.current.signal;
    if (signal.aborted || inFlight.current) return;
    if (!isSubmitInterviewInput(command)) {
      setMessage('請填寫訪談內容，不能只有空白或包含無效字元。');
      return;
    }
    inFlight.current = true;
    setPending(command);
    setMessage(null);
    try {
      await mutation.mutateAsync(
        { command, ...previous, signal },
        {
          onSuccess(outcome) {
            if (signal.aborted) return;
            switch (outcome.status) {
              case 'not-sent':
                setPending(previous.retry ? command : null);
                setMessage(
                  !navigator.locks
                    ? '瀏覽器不支援安全的跨頁提交，尚未送出。請使用支援 Web Locks 的瀏覽器。'
                    : '無法安全保留本次訪談識別，尚未送出。請確認其他頁面的待確認訪談及儲存權限後重試。',
                );
                break;
              case 'accepted':
                if (!outcome.hintSaved)
                  setMessage('原輸入已受理，但瀏覽器未能保留處理識別。請保留此頁以查看結果。');
                setPending(null);
                break;
              case 'rejected':
                if (!outcome.hintCleared) {
                  setMessage('輸入未被接受，但待確認識別無法清除。請確認瀏覽器儲存權限。');
                  break;
                }
                setPending(null);
                setDraft(command.text);
                setMessage(
                  outcome.error.code === 'model_not_configured'
                    ? '尚未設定模型服務，這次輸入未被接受，文字仍保留。請先完成後端模型設定。'
                    : outcome.error.status === 503
                      ? '本機服務尚未就緒，這次輸入未被接受，文字仍保留。請確認服務設定後再送出。'
                      : '這次輸入未被接受，文字仍保留。請確認檔案與內容後再送出。',
                );
                break;
              case 'conflict':
                setMessage(
                  '同一檔案已有處理中的訪談，或原命令內容不符。請先核對原請求；不會另建一次輸入。',
                );
                break;
              case 'unknown':
                setMessage(null);
                break;
            }
          },
        },
      );
    } finally {
      inFlight.current = false;
    }
  }

  async function startNext(turn: ConsultantTurn, hint: TurnHint | null, restoreText: boolean) {
    if (!isTerminalTurn(turn.status)) return;
    const signal = lifetime.current.signal;
    if (signal.aborted) return;
    try {
      if (hint) await clearTurnHint(jobFileId, hint.command_id);
    } catch {
      if (!signal.aborted)
        setMessage('無法清除上一個訪談識別，尚未開始新輸入。請確認瀏覽器儲存權限。');
      return;
    }
    if (signal.aborted) return;
    setDraft(restoreText ? turn.input_text : '');
    setPending(null);
    setMessage(null);
    mutation.reset();
    rediscover();
  }

  return {
    draft,
    setDraft,
    pending,
    message,
    isSending: mutation.isPending,
    isUncertain: mutation.data?.status === 'unknown',
    send,
    startNext,
  };
}
