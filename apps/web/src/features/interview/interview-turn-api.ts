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
import { isConsultantTurn } from '../../shared/api/validation';

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

export function readTurnHint(jobFileId: string): TurnHint | null {
  const raw = localStorage.getItem(hintKey(jobFileId));
  if (raw === null) return null;
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

export function retainTurnHint(jobFileId: string, hint: TurnHint): void {
  localStorage.setItem(
    hintKey(jobFileId),
    JSON.stringify({
      command_id: hint.command_id,
      execution_id: hint.execution_id,
    }),
  );
}

export function clearTurnHint(jobFileId: string, commandId: string): void {
  if (readTurnHint(jobFileId)?.command_id === commandId)
    localStorage.removeItem(hintKey(jobFileId));
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
