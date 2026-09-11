/* Generated from actual analysis_agent.api Pydantic models. Do not edit. */

export type AnalysisApi =
  | DocumentInput
  | DocumentOutput
  | MessageInput
  | MessageOutput
  | RunOutput
  | MemoryStatusOutput
  | DocumentMetadataInput
  | JdRunLookupMissing
  | RunLookupReceived
  | ManualSaveRejection
  | ManualRecoveryRequest
  | (ManualRecoveryAvailable | ManualRecoveryUnknown | ManualRecoveryNoPending);
export type Title = string;
export type RequestKey = string;
export type Id = string;
export type Title1 = string;
export type CreatedAt = string;
export type Archived = boolean;
export type MetadataVersion = number;
export type RequestKey1 = string;
export type Text = string;
export type AbandonPending = boolean;
/**
 * App- or existing-source-owner-issued opaque reference. Its encoding is not a model contract.
 */
export type OpaqueRef = string;
/**
 * @minItems 1
 */
export type Path = [PathItem, ...PathItem[]];
export type PathItem = number;
export type Offset = number;
export type Id1 = string;
export type Role = string;
export type Text1 = string;
export type Id2 = string;
export type DocumentId = string;
export type Status = string;
export type ErrorCode = string | null;
export type ResumeCount = number;
export type UsageComplete = boolean;
export type Usage = {
  [k: string]: number;
} | null;
export type Outcome = {
  [k: string]: unknown;
} | null;
export type CanResume = boolean;
export type Status1 = string;
export type ErrorCode1 = string | null;
export type RecoveryCount = number;
export type DocumentMetadataInput = JdDocumentRename | JdDocumentSetArchived;
export type Command = "rename";
export type Title2 = string;
export type ExpectedMetadataVersion = number;
export type Command1 = "set_archived";
export type Archived1 = boolean;
export type ExpectedMetadataVersion1 = number;
export type Found = false;
export type Found1 = true;
export type InputReceived = boolean;
export type Admission = "not_admitted";
export type RequestKey2 = string;
export type Message = string;
export type RequestKey3 = string;
export type WriteBlocked = boolean;
export type CanRecover = boolean;
export type RestartRequired = boolean;
export type Status2 = "available";
export type RequestKey4 = string;
export type JdWriteStatus =
  | "committed"
  | "no_change"
  | "invalid_input"
  | "unsupported_content"
  | "target_missing"
  | "stale_base"
  | "engine_failed"
  | "save_failed"
  | "outcome_unknown"
  | "operation_conflict"
  | "busy";
export type DocumentEffect = "unchanged" | "committed" | "unknown";
export type ReceiptDurability = "confirmed" | "unconfirmed";
export type Origin = "ai" | "manual" | "initial";
/**
 * JSON-safe Plate operations when actually captured. Manual saves may use null; snapshots remain authoritative.
 */
export type NativeOperations = JsonObject[] | null;
export type JsonValue =
  | boolean
  | number
  | string
  | (JsonValue | null)[]
  | {
      [k: string]: JsonValue | null;
    }
  | null;
export type AffectedElementId = string;
export type AffectedElementIds = AffectedElementId[];
export type Code = string;
export type Message1 = string;
export type CommandIndex = number | null;
export type NextAction1 = "continue" | "correct_arguments" | "reread_current" | "reconcile_operation" | "wait" | "stop";
export type WriteBlocked1 = boolean;
export type CanRecover1 = boolean;
export type RestartRequired1 = boolean;
export type Status3 = "unknown";
export type RequestKey5 = string;
export type WriteBlocked2 = boolean;
export type CanRecover2 = boolean;
export type RestartRequired2 = boolean;
export type Status4 = "no_pending";
export type RequestKey6 = string | null;

export interface DocumentInput {
  title: Title;
  request_key: RequestKey;
}
export interface DocumentOutput {
  id: Id;
  title: Title1;
  created_at: CreatedAt;
  archived: Archived;
  metadata_version: MetadataVersion;
}
export interface MessageInput {
  request_key: RequestKey1;
  text: Text;
  abandon_pending?: AbandonPending;
  jd_selection?: JdSelectionCaptureClientInput | null;
}
export interface JdSelectionCaptureClientInput {
  base_revision_ref: OpaqueRef;
  range: SlateRange;
}
export interface SlateRange {
  anchor: SlatePoint;
  focus: SlatePoint;
}
export interface SlatePoint {
  path: Path;
  offset: Offset;
}
export interface MessageOutput {
  id: Id1;
  role: Role;
  text: Text1;
  [k: string]: unknown;
}
export interface RunOutput {
  id: Id2;
  document_id: DocumentId;
  status: Status;
  error_code: ErrorCode;
  resume_count: ResumeCount;
  usage_complete: UsageComplete;
  usage: Usage;
  outcome: Outcome;
  can_resume: CanResume;
  [k: string]: unknown;
}
export interface MemoryStatusOutput {
  status: Status1;
  error_code: ErrorCode1;
  recovery_count: RecoveryCount;
  [k: string]: unknown;
}
export interface JdDocumentRename {
  command: Command;
  title: Title2;
  expected_metadata_version: ExpectedMetadataVersion;
}
export interface JdDocumentSetArchived {
  command: Command1;
  archived: Archived1;
  expected_metadata_version: ExpectedMetadataVersion1;
}
export interface JdRunLookupMissing {
  found: Found;
}
export interface RunLookupReceived {
  found: Found1;
  input_received: InputReceived;
  run: RunOutput;
}
export interface ManualSaveRejection {
  admission?: Admission;
  request_key: RequestKey2;
  message: Message;
}
export interface ManualRecoveryRequest {
  request_key: RequestKey3;
}
export interface ManualRecoveryAvailable {
  write_blocked: WriteBlocked;
  can_recover: CanRecover;
  restart_required?: RestartRequired;
  status: Status2;
  request_key: RequestKey4;
  result: JdManualSaveResult;
}
export interface JdManualSaveResult {
  status: JdWriteStatus;
  operation_ref: OpaqueRef | null;
  base_revision_ref: OpaqueRef | null;
  result_revision_ref: OpaqueRef | null;
  change_ref: OpaqueRef | null;
  document_effect: DocumentEffect;
  receipt_durability: ReceiptDurability;
  actual_changes: JdActualChanges | null;
  error: JdToolErrorDetail | null;
  next_action: NextAction1;
}
export interface JdActualChanges {
  origin: Origin;
  before_revision_ref: OpaqueRef;
  after_revision_ref: OpaqueRef;
  native_operations: NativeOperations;
  affected_element_ids: AffectedElementIds;
}
export interface JsonObject {
  [k: string]: JsonValue | null;
}
export interface JdToolErrorDetail {
  code: Code;
  message: Message1;
  command_index: CommandIndex;
}
export interface ManualRecoveryUnknown {
  write_blocked: WriteBlocked1;
  can_recover: CanRecover1;
  restart_required?: RestartRequired1;
  status: Status3;
  request_key: RequestKey5;
}
export interface ManualRecoveryNoPending {
  write_blocked: WriteBlocked2;
  can_recover: CanRecover2;
  restart_required?: RestartRequired2;
  status: Status4;
  request_key: RequestKey6;
}
