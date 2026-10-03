/* Generated from apps/api/contracts; do not edit. */

export type Source = CurrentInputSource | InterviewSource | MemorySource;
export type SourceTarget = ItemTarget | DetailTarget | CapabilityTarget;

export interface ReviseJdItemArguments {
  /**
   * read_jd 提供的既有項目定位；明細與能力關係以所屬 task 為外層目標。
   */
  read_ref: string;
  /**
   * 只列本次要執行的變更；未列的內容與來源保留。改文字不等於替換來源集合，新增來源也不需要先刪除既有來源。
   *
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
  /**
   * 此欄完整的新文字，不是 patch；保留本次未更正的有效事實。這個動作不更改來源。
   */
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
  /**
   * outcome：交付或維持的結果與用途；requirement：已知的完成判準、執行條件或責任界線。不能把一次作法推定為固定要求。
   */
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
  /**
   * 此成果或要求的完整新文字；其他明細與既有來源保留，來源變動另列。
   */
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
  /**
   * 增加支持此內容的直接依據，不替換既有來源。綜合內容可由多則原話共同支持。
   */
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
  /**
   * 移除此 target 的整筆引用，不是只排除原文中被更正的一句。局部更正後，仍須留下共同支持本項保留事實的依據；失效、重複或已有充分替代的引用可移除。
   */
  action: 'remove_source';
  target: SourceTarget;
  /**
   * read_jd 返回、屬於此 target 的既有引用定位；不是訪談序號或 Memory 標題。
   */
  citation_ref: string;
}
export interface AlignSource {
  /**
   * 明確宣告已重評此筆引用仍支持所選 target 的目前內容，並完成必要修訂。不是確認其他引用或整項完成；僅讀過 diff、或此筆支持關係仍有未解衝突時不確認。
   */
  action: 'confirm_reference_alignment';
  target: SourceTarget;
  /**
   * read_jd 返回、這次確實完成核對的既有引用定位。
   */
  citation_ref: string;
}
