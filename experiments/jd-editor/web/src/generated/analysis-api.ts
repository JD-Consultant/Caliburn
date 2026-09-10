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
  | ManualSaveRejection;
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
