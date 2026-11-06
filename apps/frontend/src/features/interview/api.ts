import type {
  AnswerTurnRequest,
  PlanResponse,
  QuestionExchange,
  StepView,
  SubmitTurnRequest,
  TranscriptMessage,
  TurnView,
} from '../../shared/api/generated/types.gen';
import {
  validateAnswerTurnRequest,
  validatePlanResponse,
  validateQuestionExchangeArray,
  validateStepViewArray,
  validateSubmitTurnRequest,
  validateTranscriptMessageArray,
  validateTurnView,
  validateTurnViewArray,
} from '../../shared/api/generated/validators';
import {
  HttpError,
  InvalidRequestError,
  InvalidResponseError,
  requestEmpty,
  requestJson,
} from '../../shared/api/http';

export function workspacePath(workspaceId: string): string {
  return `/workspaces/${encodeURIComponent(workspaceId)}`;
}
export function turnPath(workspaceId: string, turnId: string): string {
  return `${workspacePath(workspaceId)}/agent/turns/${encodeURIComponent(turnId)}`;
}
export function requireTurnScope(
  turn: TurnView,
  workspaceId: string,
  turnId = turn.turn_id,
): TurnView {
  if (
    turn.workspace_id.toLowerCase() !== workspaceId.toLowerCase() ||
    turn.turn_id.toLowerCase() !== turnId.toLowerCase()
  )
    throw new InvalidResponseError();
  return turn;
}
export async function listTurns(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<TurnView[]> {
  const turns = await requestJson(
    `${workspacePath(workspaceId)}/agent/turns`,
    { signal: signal ?? null },
    validateTurnViewArray,
  );
  turns.forEach((turn) => requireTurnScope(turn, workspaceId));
  return turns;
}
export async function getTurn(
  workspaceId: string,
  turnId: string,
  signal?: AbortSignal,
): Promise<TurnView> {
  return requireTurnScope(
    await requestJson(
      turnPath(workspaceId, turnId),
      { signal: signal ?? null },
      validateTurnView,
    ),
    workspaceId,
    turnId,
  );
}
export async function listMessages(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<TranscriptMessage[]> {
  return requestJson(
    `${workspacePath(workspaceId)}/interview/messages`,
    { signal: signal ?? null },
    validateTranscriptMessageArray,
  );
}
export async function listSteps(
  workspaceId: string,
  turnId: string,
  signal?: AbortSignal,
): Promise<StepView[]> {
  return requestJson(
    `${turnPath(workspaceId, turnId)}/steps`,
    { signal: signal ?? null },
    validateStepViewArray,
  );
}
export async function listQuestions(
  workspaceId: string,
  turnId: string,
  signal?: AbortSignal,
): Promise<QuestionExchange[]> {
  return requestJson(
    `${turnPath(workspaceId, turnId)}/questions`,
    { signal: signal ?? null },
    validateQuestionExchangeArray,
  );
}
export async function getPlan(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<PlanResponse> {
  const plan = await requestJson(
    `${workspacePath(workspaceId)}/plan`,
    { signal: signal ?? null },
    validatePlanResponse,
  );
  if (plan.workspace_id.toLowerCase() !== workspaceId.toLowerCase())
    throw new InvalidResponseError();
  return plan;
}
export async function submitTurn(
  workspaceId: string,
  body: SubmitTurnRequest,
): Promise<TurnView> {
  if (!validateSubmitTurnRequest(body)) throw new InvalidRequestError();
  return requireTurnScope(
    await requestJson(
      `${workspacePath(workspaceId)}/agent/turns`,
      { method: 'POST', body: JSON.stringify(body) },
      validateTurnView,
      [200, 202],
    ),
    workspaceId,
    body.turn_id,
  );
}
export async function answerTurn(
  workspaceId: string,
  turnId: string,
  body: AnswerTurnRequest,
): Promise<TurnView> {
  if (!validateAnswerTurnRequest(body)) throw new InvalidRequestError();
  return requireTurnScope(
    await requestJson(
      `${turnPath(workspaceId, turnId)}/answers`,
      { method: 'POST', body: JSON.stringify(body) },
      validateTurnView,
      [200, 202],
    ),
    workspaceId,
    turnId,
  );
}
export async function resumeTurn(workspaceId: string, turnId: string): Promise<TurnView> {
  return requireTurnScope(
    await requestJson(
      `${turnPath(workspaceId, turnId)}/resume`,
      { method: 'POST' },
      validateTurnView,
      202,
    ),
    workspaceId,
    turnId,
  );
}
export async function cancelTurn(workspaceId: string, turnId: string): Promise<void> {
  return requestEmpty(`${turnPath(workspaceId, turnId)}/cancel`, { method: 'POST' });
}

export function interviewError(error: unknown): string {
  if (error instanceof HttpError) {
    if (error.status === 404) return '目前資料已不存在或無法查閱，請重新讀取工作區。';
    if (error.status === 409) return '狀態已改變，請重新讀取後再確認操作。';
    if (error.status === 422) return '輸入不符合要求，請檢查內容。';
    if (error.status === 503)
      return '服務目前無法完成操作，請稍後重新確認；模型可能尚未配置或暫時無法使用。';
  }
  return '無法確認伺服器結果，請重新讀取或確認原請求。';
}
