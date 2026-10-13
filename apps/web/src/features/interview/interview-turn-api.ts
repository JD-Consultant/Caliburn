import { isSubmitInterviewInput } from '../../shared/api/generated/http/validators.js';
/** Scoped polling and original input commands; browser hints carry IDs only. */
import { queryOptions, skipToken } from '@tanstack/react-query';

import type {
  ConsultantTurn,
  CurrentConsultantTurn,
  AcceptedInterviewInput,
  SubmitInterviewInput,
} from '../../shared/api/generated/http/types.gen';

import { isCanonicalUuid } from '../../shared/api/uuid';
import { ApiError, scope } from '../../shared/api/http';
import {
  submitInterviewInput as submit,
  pauseConsultantTurn,
  cancelConsultantTurn,
  resumeConsultantTurn,
  readConsultantTurnByCommand,
  readConsultantTurn,
  readCurrentConsultantTurn,
} from '../../shared/api/generated/http/sdk.gen';

export { isSubmitInterviewInput };

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
  return submit({
    path: { job_file_id: jobFileId },
    body: command,
    throwOnError: true,
    meta: {
      correlation: { jobFileId, commandId: command.command_id },
      scope: scope<AcceptedInterviewInput>(
        (value) => value.job_file_id === jobFileId && value.command_id === command.command_id,
      ),
    },
  }).then(({ data }) => data);
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
  const execute = {
    pause: pauseConsultantTurn,
    cancel: cancelConsultantTurn,
    resume: resumeConsultantTurn,
  }[control];
  return execute({
    path: { job_file_id: jobFileId, execution_id: executionId },
    cache: 'no-store',
    throwOnError: true,
    meta: {
      correlation: { jobFileId, executionId },
      scope: scope<ConsultantTurn>(
        (value) => value.job_file_id === jobFileId && value.execution_id === executionId,
      ),
    },
  }).then(({ data }) => data);
}

export function consultantTurnByCommandQuery(jobFileId: string, commandId: string | null) {
  return queryOptions({
    queryKey: ['consultant-turn-by-command', jobFileId, commandId],
    queryFn: commandId
      ? ({ signal }) =>
          readConsultantTurnByCommand({
            path: { job_file_id: jobFileId, command_id: commandId },
            signal,
            cache: 'no-store',
            throwOnError: true,
            meta: {
              correlation: { jobFileId, commandId },
              scope: scope<ConsultantTurn>((value) => value.job_file_id === jobFileId),
            },
          }).then(({ data }) => data)
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
      ? ({ signal }) =>
          readConsultantTurn({
            path: { job_file_id: jobFileId, execution_id: executionId },
            signal,
            cache: 'no-store',
            throwOnError: true,
            meta: {
              correlation: { jobFileId, executionId },
              scope: scope<ConsultantTurn>(
                (value) => value.job_file_id === jobFileId && value.execution_id === executionId,
              ),
            },
          }).then(({ data }) => data)
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
    queryFn: ({ signal }) =>
      readCurrentConsultantTurn({
        path: { job_file_id: jobFileId },
        signal,
        cache: 'no-store',
        throwOnError: true,
        meta: {
          correlation: { jobFileId },
          scope: scope<CurrentConsultantTurn>(
            (value) => value.turn === null || value.turn.job_file_id === jobFileId,
          ),
        },
      }).then(({ data }) => data),
    retry: false,
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: 'always',
  });
}
