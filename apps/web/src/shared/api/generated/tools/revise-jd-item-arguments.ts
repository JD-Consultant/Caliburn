/* Generated from apps/api/contracts; do not edit. */

export type Source = CurrentInputSource | InterviewSource | MemorySource;
export type SourceTarget = ItemTarget | DetailTarget | CapabilityTarget;

export interface ReviseJdItemArguments {
  /**
   * read_jd 提供的既有項目定位；明細與能力關係以所屬 task 為外層目標。
   */
  read_ref: string;
  /**
   * @minItems 1
   */
  changes: [
    (
      | SetItemText
      | ClearItemText
      | SetConditionKind
      | AddTaskDetail
      | ReviseTaskDetail
      | RemoveTaskDetail
      | LinkCapability
      | UnlinkCapability
      | ReorderCapability
      | AddSource
      | RemoveSource
      | AlignSource
    ),
    ...(
      | SetItemText
      | ClearItemText
      | SetConditionKind
      | AddTaskDetail
      | ReviseTaskDetail
      | RemoveTaskDetail
      | LinkCapability
      | UnlinkCapability
      | ReorderCapability
      | AddSource
      | RemoveSource
      | AlignSource
    )[]
  ];
}
export interface SetItemText {
  action: 'set_field';
  /**
   * 任務 title/description；職責 title/scope_text；K/S name/description；協作 name/scope_text；條件 text。
   */
  field: 'title' | 'description' | 'scope_text' | 'name' | 'text';
  value: string;
}
export interface ClearItemText {
  action: 'clear_field';
  /**
   * 僅可清空該型別可空欄；仍須保留有意義內容。不以空文字刪項。
   */
  field: 'title' | 'description' | 'scope_text' | 'name';
}
export interface SetConditionKind {
  action: 'set_field';
  field: 'kind';
  value:
    | 'work_environment'
    | 'schedule_travel'
    | 'shared_authority'
    | 'shared_collaboration'
    | 'qualification';
}
export interface AddTaskDetail {
  action: 'add_detail';
  kind: 'outcome' | 'requirement';
  text: string;
  supporting_sources: Source[];
}
export interface CurrentInputSource {
  kind: 'current_input';
}
export interface InterviewSource {
  kind: 'interview';
  interview_sequence: number;
}
export interface MemorySource {
  kind: 'work_situation' | 'work_understanding';
  target_title: string;
}
export interface ReviseTaskDetail {
  action: 'revise_detail';
  detail_read_ref: string;
  text: string;
}
export interface RemoveTaskDetail {
  action: 'remove_detail';
  detail_read_ref: string;
}
export interface LinkCapability {
  action: 'set_capability';
  capability_read_ref: string;
  relationship: 'link';
  supporting_sources: Source[];
}
export interface UnlinkCapability {
  action: 'set_capability';
  capability_read_ref: string;
  relationship: 'unlink';
}
export interface ReorderCapability {
  action: 'reorder_capability';
  capability_read_ref: string;
  position: EdgePosition | RelativePosition;
}
export interface EdgePosition {
  kind: 'first' | 'last';
}
export interface RelativePosition {
  kind: 'before' | 'after';
  capability_read_ref: string;
}
export interface AddSource {
  action: 'add_source';
  target: SourceTarget;
  source: Source;
}
export interface ItemTarget {
  kind: 'item';
}
export interface DetailTarget {
  kind: 'detail';
  detail_read_ref: string;
}
export interface CapabilityTarget {
  kind: 'capability_relation';
  capability_read_ref: string;
}
export interface RemoveSource {
  action: 'remove_source';
  target: SourceTarget;
  citation_ref: string;
}
export interface AlignSource {
  action: 'confirm_reference_alignment';
  target: SourceTarget;
  citation_ref: string;
}
