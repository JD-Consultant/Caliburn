// Compile-time consumer checks; runtime constraints remain in the source schema.
import type {
  ChatStartInput,
  ChatRunState,
  ChatHistoryPage,
  ChatMessage,
  ChatProblem,
  ChatBoundResult,
  ChatConfirmedResult,
  ChatRunRunning,
  ChatRunFailedSaved,
  ChatRunFailedNotSaved,
  ChatRunNotFound,
  ChatSettledEffects,
  ChatEmptyUnconfirmedEffects,
} from "../src/jd_relational/generated/jd-chat-http";
import type {
  ManualDocumentState,
  ManualBlockedState,
} from "../src/jd_relational/generated/jd-manual-http";
import type {
  CommittedResult,
  UnknownOutcomeResult,
  UnboundBusy,
} from "../src/jd_relational/generated/jd-result";

const request: ChatStartInput = {
  run_id: "32345678-90ab-cdef-1234-567890abcdef",
  text: "原話\r\n  每月處理異常。😀",
  expected_jd_revision_ref: "original-signed-revision",
};
// @ts-expect-error A start cannot silently omit the original revision.
const missingRevision: ChatStartInput = { run_id: request.run_id, text: request.text };
// @ts-expect-error The start body does not copy route or dataset ownership.
const duplicateScope: ChatStartInput = { ...request, dataset_id: "dataset" };

declare const blocked: ManualBlockedState;
declare const writable: Extract<ManualDocumentState, { write_blocked: false }>;
declare const committed: CommittedResult;
declare const unknown: UnknownOutcomeResult;
declare const unbound: UnboundBusy;

const boundKnown: ChatBoundResult = committed;
const boundUnknown: ChatBoundResult = unknown;
const confirmed: ChatConfirmedResult = committed;
// @ts-expect-error Unbound request failures are not effects of a run.
const boundRejected: ChatBoundResult = unbound;
// @ts-expect-error Unknown outcomes are not confirmed write receipts.
const confirmedUnknown: ChatConfirmedResult = unknown;
// @ts-expect-error Settled effects cannot contain unknown outcomes.
const unsettled: ChatSettledEffects = { state: "settled", results: [unknown] };
// @ts-expect-error not_found cannot invent even a confirmed effect.
const invented: ChatEmptyUnconfirmedEffects = { state: "unconfirmed", results: [committed] };

const scope = { dataset_id: "dataset", document_id: "document", run_id: request.run_id };
const running: ChatRunRunning = {
  ...scope,
  write_state: blocked,
  run_status: "running",
  input_state: "unconfirmed",
  response_message_id: null,
  stop_requested: false,
  jd_effects: { state: "unconfirmed", results: [committed, unknown] },
};
const failed: ChatRunFailedSaved = {
  ...scope,
  write_state: writable,
  run_status: "failed",
  input_state: "saved",
  response_message_id: "native-saved-text-message",
  stop_requested: null,
  jd_effects: { state: "settled", results: [committed] },
};
const unsaved: ChatRunFailedNotSaved = {
  ...failed,
  input_state: "not_saved",
  response_message_id: null,
  jd_effects: { state: "settled", results: [] },
};
const notFound: ChatRunNotFound = {
  ...scope,
  write_state: blocked,
  run_status: "not_found",
  input_state: "unconfirmed",
  response_message_id: null,
  stop_requested: null,
  jd_effects: { state: "unconfirmed", results: [] },
};
const states: ChatRunState[] = [running, failed, unsaved, notFound];
// @ts-expect-error Running does not grant an unblocked write state.
const runningWritable: ChatRunRunning = { ...running, write_state: writable };
// @ts-expect-error Unknown input does not mean input was not saved.
const inventedUnsaved: ChatRunState = { ...notFound, input_state: "not_saved" };
// @ts-expect-error Numeric truthiness is not a stop request flag.
const numericStop: ChatRunState = { ...running, stop_requested: 1 };
// @ts-expect-error A known unsaved input cannot have a saved response.
const unsavedResponse: ChatRunFailedNotSaved = { ...unsaved, response_message_id: "message" };

const publicMessage: ChatMessage = { message_id: "native-id", run_id: request.run_id,
  role: "assistant", text: "請補充這項工作的範圍。" };
const history: ChatHistoryPage = { dataset_id: scope.dataset_id, document_id: scope.document_id,
  anchor: "fixed-snapshot", messages: [publicMessage], next_cursor: null };
const empty: ChatHistoryPage = { ...history, anchor: null, messages: [], next_cursor: null };
// @ts-expect-error An empty history cannot invent a next page without an anchor.
const emptyCursor: ChatHistoryPage = { ...empty, next_cursor: "cursor" };
// @ts-expect-error An empty history cannot invent a message without an anchor.
const emptyMessage: ChatHistoryPage = { ...empty, messages: [publicMessage] };
// @ts-expect-error Tool messages are not public chat messages.
const privateRole: ChatMessage = { ...publicMessage, role: "tool" };
// @ts-expect-error Provider internal data has no public projection field.
const privateData: ChatMessage = { ...publicMessage, thinking: "private" };

const problem: ChatProblem = { type: "about:blank", title: "Conflict", status: 409,
  detail: "請查回原回合。", instance: `urn:uuid:${request.run_id}`,
  code: "run_conflict", next_action: "lookup_run" };
const disabledAi: ChatProblem = { ...problem, title: "Service Unavailable", status: 503,
  code: "ai_unavailable", next_action: "stop",
  detail: "AI 訪談尚未啟用；請保留輸入。目前仍可查看原有對話及編輯 JD。" };
// @ts-expect-error An App Problem is not an HTTP success or a run result.
const successProblem: ChatProblem = { ...problem, status: 200 };
// @ts-expect-error Problems cannot claim the original input or JD was rolled back.
const rollback: ChatProblem = { ...problem, rolled_back: true };

void [states, history, empty, boundKnown, boundUnknown, confirmed, disabledAi];
