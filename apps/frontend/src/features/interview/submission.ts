import type { SubmitTurnRequest, TurnView } from '../../shared/api/generated/types.gen';
import { validateSubmitTurnRequest } from '../../shared/api/generated/validators';
import { getTurn, submitTurn } from './api';
import {
  HttpError,
  InvalidRequestError,
  InvalidResponseError,
} from '../../shared/api/http';
import { useSyncExternalStore } from 'react';

export class UnconfirmedSubmission extends Error {
  constructor() {
    super('原請求尚未確認，請沿同一輪識別重新確認。');
  }
}
function storageKey(workspaceId: string): string {
  return `caliburn:pending-turn:${workspaceId.toLowerCase()}`;
}
const submissionChanged = 'caliburn:pending-turn-changed';
const storageUnavailableMessage =
  '無法讀取待確認的操作，請確認瀏覽器儲存權限後重新開啟。';
function subscribe(listener: () => void): () => void {
  window.addEventListener(submissionChanged, listener);
  return () => window.removeEventListener(submissionChanged, listener);
}
export function usePendingSubmission(workspaceId: string) {
  const raw = useSyncExternalStore(subscribe, () => {
    try {
      return sessionStorage.getItem(storageKey(workspaceId));
    } catch {
      return 'unavailable';
    }
  });
  try {
    const request: unknown = raw === null ? null : JSON.parse(raw);
    if (request !== null && !validateSubmitTurnRequest(request))
      throw new UnconfirmedSubmission();
    return { request, error: null };
  } catch {
    return {
      request: null,
      error: storageUnavailableMessage,
    };
  }
}
export function readPendingSubmission(workspaceId: string): SubmitTurnRequest | null {
  const raw = sessionStorage.getItem(storageKey(workspaceId));
  if (raw === null) return null;
  const value: unknown = JSON.parse(raw);
  if (!validateSubmitTurnRequest(value)) throw new UnconfirmedSubmission();
  return value;
}
export function retainSubmission(workspaceId: string, request: SubmitTurnRequest): void {
  sessionStorage.setItem(storageKey(workspaceId), JSON.stringify(request));
  window.dispatchEvent(new Event(submissionChanged));
}
export function clearSubmission(workspaceId: string): void {
  sessionStorage.removeItem(storageKey(workspaceId));
  window.dispatchEvent(new Event(submissionChanged));
}

/** Unknown acknowledgement is resolved by reading the original id before any explicit resend. */
export async function submitAndRecover(
  workspaceId: string,
  request: SubmitTurnRequest,
): Promise<TurnView> {
  try {
    return await submitTurn(workspaceId, request);
  } catch (error) {
    if (
      error instanceof InvalidRequestError ||
      (error instanceof HttpError && [400, 404, 409, 422].includes(error.status))
    )
      throw error;
    try {
      const turn = await getTurn(workspaceId, request.turn_id);
      if (turn.input !== request.input) throw new InvalidResponseError();
      return turn;
    } catch {
      throw new UnconfirmedSubmission();
    }
  }
}

export function readPendingCancellation(workspaceId: string): {
  turnId: string | null;
  error: string | null;
} {
  try {
    return {
      turnId: sessionStorage.getItem(
        `caliburn:pending-cancel:${workspaceId.toLowerCase()}`,
      ),
      error: null,
    };
  } catch {
    return { turnId: null, error: storageUnavailableMessage };
  }
}
export function retainCancellation(workspaceId: string, turnId: string): void {
  sessionStorage.setItem(`caliburn:pending-cancel:${workspaceId.toLowerCase()}`, turnId);
}
export function clearCancellation(workspaceId: string): void {
  sessionStorage.removeItem(`caliburn:pending-cancel:${workspaceId.toLowerCase()}`);
}
