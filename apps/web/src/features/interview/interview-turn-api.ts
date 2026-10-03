/** Scoped polling and original input commands; browser hints carry IDs only. */
import { queryOptions, skipToken } from '@tanstack/react-query';
import { Ajv2020 } from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import acceptedSchema from '../../../../api/contracts/http/accepted-interview-input.schema.json' with { type: 'json' };
import submitSchema from '../../../../api/contracts/http/submit-interview-input.schema.json' with { type: 'json' };
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import type { AcceptedInterviewInput } from '../../shared/api/generated/accepted-interview-input';
import type { SubmitInterviewInput } from '../../shared/api/generated/submit-interview-input';
import { ApiError, requestJson } from '../../shared/api/http';
import { isConsultantTurn, isCurrentConsultantTurn } from '../../shared/api/validation';

const validator = new Ajv2020();
addFormats(validator);
const isAcceptedInput = validator.compile<AcceptedInterviewInput>(acceptedSchema);
export const isSubmitInterviewInput = validator.compile<SubmitInterviewInput>(submitSchema);

export interface TurnHint {
  command_id: string;
  execution_id: string | null;
}

function hintKey(jobFileId: string): string {
  return `caliburn:interview-turn:${jobFileId}`;
}

function isUuid(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value);
}

function parseHint(raw: string): TurnHint {
  const hint: unknown = JSON.parse(raw);
  if (
    typeof hint !== 'object' ||
    hint === null ||
    !('command_id' in hint) ||
    !isUuid(hint.command_id) ||
    !('execution_id' in hint) ||
    (hint.execution_id !== null && !isUuid(hint.execution_id))
  )
    throw new Error('Invalid interview recovery hint');
  return { command_id: hint.command_id, execution_id: hint.execution_id };
}

export function readTurnHint(jobFileId: string): TurnHint | null {
  const raw = localStorage.getItem(hintKey(jobFileId));
  return raw === null ? null : parseHint(raw);
}

const HINT_CHANGED = 'caliburn:interview-turn-hint-changed';

function notifyHintChanged(): void {
  window.dispatchEvent(new Event(HINT_CHANGED));
}

export function retainTurnHint(jobFileId: string, hint: TurnHint): void {
  localStorage.setItem(
    hintKey(jobFileId),
    JSON.stringify({
      command_id: hint.command_id,
      execution_id: hint.execution_id,
    }),
  );
  notifyHintChanged();
}

export function clearTurnHint(jobFileId: string, commandId: string): void {
  if (readTurnHint(jobFileId)?.command_id !== commandId) return;
  localStorage.removeItem(hintKey(jobFileId));
  notifyHintChanged();
}

/** Same-tab writes and other tabs' `storage` events; for `useSyncExternalStore`. */
export function subscribeTurnHint(onChange: () => void): () => void {
  window.addEventListener(HINT_CHANGED, onChange);
  window.addEventListener('storage', onChange);
  return () => {
    window.removeEventListener(HINT_CHANGED, onChange);
    window.removeEventListener('storage', onChange);
  };
}

const snapshots = new Map<string, { raw: string | null; hint: TurnHint | null }>();

/**
 * Snapshot for `useSyncExternalStore`: never throws and returns one object while the stored text is
 * unchanged. A corrupt hint reads as null here; the composer reports the corruption itself.
 */
export function readTurnHintSnapshot(jobFileId: string): TurnHint | null {
  let raw: string | null;
  try {
    raw = localStorage.getItem(hintKey(jobFileId));
  } catch {
    return null;
  }
  const cached = snapshots.get(jobFileId);
  if (cached?.raw === raw) return cached.hint;
  let hint: TurnHint | null = null;
  if (raw !== null) {
    try {
      hint = parseHint(raw);
    } catch {
      hint = null;
    }
  }
  snapshots.set(jobFileId, { raw, hint });
  return hint;
}

/** These input-route errors occur before acceptance; generic 503/404 do not prove that. */
export function isInputAdmissionRejection(error: unknown): error is ApiError {
  if (!(error instanceof ApiError)) return false;
  return (
    error.status === 422 ||
    (error.status === 404 && error.code === 'job_file_not_found') ||
    (error.status === 503 &&
      (error.code === 'model_not_configured' ||
        error.code === 'consultant_unavailable' ||
        error.code === 'database_not_configured'))
  );
}

export async function submitInterviewInput(
  jobFileId: string,
  command: SubmitInterviewInput,
): Promise<AcceptedInterviewInput> {
  if (!isSubmitInterviewInput(command)) throw new ApiError('請填寫有內容的訪談文字。', 422);
  const accepted = await requestJson(
    `/api/job-files/${encodeURIComponent(jobFileId)}/inputs`,
    isAcceptedInput,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(command),
    },
  );
  if (accepted.job_file_id !== jobFileId || accepted.command_id !== command.command_id) {
    throw new ApiError('收到的輸入結果不屬於本次請求，尚未採用。');
  }
  return accepted;
}

export function isTerminalTurn(status: ConsultantTurn['status']): boolean {
  return status === 'completed' || status === 'cancelled' || status === 'failed';
}

export type ConsultantControl = ConsultantTurn['allowed_controls'][number];

export async function controlConsultantTurn(
  jobFileId: string,
  executionId: string,
  control: ConsultantControl,
): Promise<ConsultantTurn> {
  const turn = await requestJson(
    `/api/job-files/${encodeURIComponent(jobFileId)}/consultant-turns/${encodeURIComponent(executionId)}/${control}`,
    isConsultantTurn,
    { method: 'POST', cache: 'no-store' },
  );
  if (turn.job_file_id !== jobFileId || turn.execution_id !== executionId) {
    throw new ApiError('收到的控制結果不屬於這次訪談，尚未採用。');
  }
  return turn;
}

export function consultantTurnByCommandQuery(jobFileId: string, commandId: string | null) {
  return queryOptions({
    queryKey: ['consultant-turn-by-command', jobFileId, commandId],
    queryFn: commandId
      ? async ({ signal }) => {
          const turn = await requestJson(
            `/api/job-files/${encodeURIComponent(jobFileId)}/consultant-turns/by-command/${encodeURIComponent(commandId)}`,
            isConsultantTurn,
            { signal, cache: 'no-store' },
          );
          if (turn.job_file_id !== jobFileId) {
            throw new ApiError('收到的處理狀態不屬於這次訪談，尚未採用。');
          }
          return turn;
        }
      : skipToken,
    retry: false,
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
  });
}

export function consultantTurnQuery(jobFileId: string, executionId: string | null) {
  return queryOptions({
    queryKey: ['consultant-turn', jobFileId, executionId],
    queryFn: executionId
      ? async ({ signal }) => {
          const turn = await requestJson(
            `/api/job-files/${encodeURIComponent(jobFileId)}/consultant-turns/${encodeURIComponent(executionId)}`,
            isConsultantTurn,
            { signal, cache: 'no-store' },
          );
          if (turn.job_file_id !== jobFileId || turn.execution_id !== executionId) {
            throw new ApiError('收到的處理狀態不屬於這次訪談，尚未採用。');
          }
          return turn;
        }
      : skipToken,
    retry: false,
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: 'always',
    refetchInterval: (query) =>
      query.state.error || (query.state.data && isTerminalTurn(query.state.data.status))
        ? false
        : 1_000,
  });
}

/** Discover only; after a match the caller follows that execution, including its terminal result. */
export function currentConsultantTurnQuery(jobFileId: string) {
  return queryOptions({
    queryKey: ['current-consultant-turn', jobFileId],
    queryFn: async ({ signal }) => {
      const current = await requestJson(
        `/api/job-files/${encodeURIComponent(jobFileId)}/consultant-turns/current`,
        isCurrentConsultantTurn,
        { signal, cache: 'no-store' },
      );
      if (current.turn && current.turn.job_file_id !== jobFileId) {
        throw new ApiError('收到的處理狀態不屬於這份職務檔案，尚未採用。');
      }
      return current;
    },
    retry: false,
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: 'always',
  });
}
