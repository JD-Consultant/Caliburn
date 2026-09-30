/* Generated from apps/api/contracts; do not edit. */

/**
 * 職務名稱／所屬單位／直接匯報對象／職務目的。匯報對象不等於所有成果的接收人；目的概括工作的持續價值，不是案例或任務清單。
 */
export type ProfileField = 'job_title' | 'organization_unit' | 'reports_to' | 'purpose';

export interface ReviseJdProfileArguments {
  /**
   * 只列本次要執行的變更；未列的欄位與來源保留。文字修改與來源增刪是不同動作，不必為更新文字重建整組來源。
   *
   * @minItems 1
   */
  changes: [
    SetProfileText | ClearProfileText | AddProfileSource | RemoveProfileSource | AlignProfileSource,
    ...(
      | SetProfileText
      | ClearProfileText
      | AddProfileSource
      | RemoveProfileSource
      | AlignProfileSource
    )[]
  ];
}
export interface SetProfileText {
  action: 'set_field';
  field: ProfileField;
  /**
   * 此欄完整的新文字；只更改文字，既有來源保留，來源變動另列。
   */
  value: string;
}
export interface ClearProfileText {
  action: 'clear_field';
  field: ProfileField;
}
export interface AddProfileSource {
  /**
   * 增加支持此欄內容的直接依據，不替換既有來源。綜合目的可由多則原話共同支持。
   */
  action: 'add_source';
  field: ProfileField;
  source: CurrentInputSource | InterviewSource | MemorySource;
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
export interface RemoveProfileSource {
  /**
   * 移除此欄的整筆引用，不是只排除原文中被更正的一句。局部更正後，仍須留下共同支持本欄保留事實的依據；失效、重複或已有充分替代的引用可移除。
   */
  action: 'remove_source';
  field: ProfileField;
  /**
   * read_jd 返回、屬於此欄的既有引用定位；不是訪談序號或 Memory 標題。
   */
  citation_ref: string;
}
export interface AlignProfileSource {
  /**
   * 明確宣告已重評此筆引用仍支持所選欄位的目前內容，並完成必要修訂。不是確認其他引用或整欄完成；僅讀過 diff、或此筆支持關係仍有未解衝突時不確認。
   */
  action: 'confirm_reference_alignment';
  field: ProfileField;
  /**
   * read_jd 返回、這次確實完成核對的既有引用定位。
   */
  citation_ref: string;
}
