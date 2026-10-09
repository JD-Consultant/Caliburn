/** Scoped polling and original input commands; browser hints carry IDs only. */
import { queryOptions, skipToken } from '@tanstack/react-query';
import { createSchemaValidator } from '../../shared/api/schema-policy';
import acceptedSchema from '../../../../api/contracts/http/accepted-interview-input.schema.json' with { type: 'json' };
import submitSchema from '../../../../api/contracts/http/submit-interview-input.schema.json' with { type: 'json' };
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import type { AcceptedInterviewInput } from '../../shared/api/generated/accepted-interview-input';
import type { SubmitInterviewInput } from '../../shared/api/generated/submit-interview-input';
import { isCanonicalUuid } from '../../shared/api/uuid';
import { ApiError, requestJson } from '../../shared/api/http';
import { isConsultantTurn, isCurrentConsultantTurn } from '../../shared/api/validation';

const validator = createSchemaValidator();
const isAcceptedInput = validator.compile<AcceptedInterviewInput>(acceptedSchema);
export const isSubmitInterviewInput = validator.compile<SubmitInterviewInput>(submitSchema);

export interface TurnHint {
  command_id: string;
  execution_id: string | null;
}

function hintKey(jobFileId: string): string {
  return `caliburn:interview-turn:${jobFileId}`;
}

function parseHint(raw: string): TurnHint {
  const hint: unknown = JSON.parse(raw);
  if (
    typeof hint !== 'object' ||
    hint === null ||
    !('command_id' in hint) ||
    !isCanonicalUuid(hint.command_id) ||
    !('execution_id' in hint) ||
    (hint.execution_id !== null && !isCanonicalUuid(hint.execution_id))
  )
    throw new Error('Invalid interview recovery hint');
  return { command_id: hint.command_id, execution_id: hint.execution_id };
}

export function readTurnHint(jobFileId: string): TurnHint | null {
  const raw = localStorage.getItem(hintKey(jobFileId));
  return raw === null ? null : parseHint(raw);
}

const HINT_CHANGED = 'caliburn:interview-turn-hint-changed';
const INTERVIEW_DELETED = 'caliburn:interview-deleted';

/** Stop live reservations synchronously, before React commits the workspace unmount. */
export function subscribeInterviewDeletion(jobFileId: string, onDeleted: () => void): () => void {
  const listener = (event: Event) => {
    if (event instanceof CustomEvent && event.detail === jobFileId) onDeleted();
  };
  window.addEventListener(INTERVIEW_DELETED, listener);
  return () => window.removeEventListener(INTERVIEW_DELETED, listener);
}

function notifyHintChanged(): void {
  window.dispatchEvent(new Event(HINT_CHANGED));
}

/** Every read/compare/write shares the same origin-wide file lock; network never runs here. */
async function withHintLock<T>(
  jobFileId: string,
  action: () => T,
  signal?: AbortSignal,
): Promise<T> {
  if (!navigator.locks) throw new Error('Web Locks unavailable');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5_000);
  try {
    const acquisitionSignal = signal
      ? AbortSignal.any([signal, controller.signal])
      : controller.signal;
    return await navigator.locks.request(hintKey(jobFileId), { signal: acquisitionSignal }, () => {
      acquisitionSignal.throwIfAborted();
      return action();
    });
  } finally {
    clearTimeout(timeout);
  }
}

function writeHint(jobFileId: string, hint: TurnHint): void {
  localStorage.setItem(hintKey(jobFileId), JSON.stringify(hint));
  notifyHintChanged();
}

/** Reserve only an empty slot or the exact previously verified completed hint. */
export async function retainTurnHint(
  jobFileId: string,
  hint: TurnHint,
  completedHint: TurnHint | null = null,
  signal?: AbortSignal,
): Promise<void> {
  await withHintLock(
    jobFileId,
    () => {
      const existing = readTurnHint(jobFileId);
      if (existing?.command_id === hint.command_id) {
        if (existing.execution_id !== null) return;
      } else if (
        existing &&
        (!completedHint ||
          existing.command_id !== completedHint.command_id ||
          existing.execution_id !== completedHint.execution_id)
      ) {
        throw new Error('Another interview command is pending');
      }
      writeHint(jobFileId, hint);
    },
    signal,
  );
}

/** Late acknowledgements may resolve their own existing command, never recreate or replace one. */
export async function resolveTurnHint(jobFileId: string, hint: TurnHint): Promise<void> {
  await withHintLock(jobFileId, () => {
    const existing = readTurnHint(jobFileId);
    if (
      !existing ||
      existing.command_id !== hint.command_id ||
      (existing.execution_id !== null && existing.execution_id !== hint.execution_id)
    )
      return;
    writeHint(jobFileId, hint);
  });
}

export async function clearTurnHint(jobFileId: string, commandId: string): Promise<void> {
  await withHintLock(jobFileId, () => {
    if (readTurnHint(jobFileId)?.command_id !== commandId) return;
    localStorage.removeItem(hintKey(jobFileId));
    notifyHintChanged();
  });
}

/** Confirmed deletion prevents later POST acknowledgements from restoring local recovery data. */
export async function clearDeletedInterview(jobFileId: string): Promise<void> {
  window.dispatchEvent(new CustomEvent(INTERVIEW_DELETED, { detail: jobFileId }));
  await withHintLock(jobFileId, () => {
    localStorage.removeItem(hintKey(jobFileId));
    notifyHintChanged();
  });
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
  if (!isSubmitInterviewInput(command))
    throw new ApiError('請填寫有內容的訪談文字。', { status: 422 });
  const accepted = await requestJson(
    `/api/job-files/${encodeURIComponent(jobFileId)}/inputs`,
    isAcceptedInput,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(command),
      correlation: { jobFileId, commandId: command.command_id },
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
    { method: 'POST', cache: 'no-store', correlation: { jobFileId, executionId } },
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
