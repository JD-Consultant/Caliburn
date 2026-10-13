/* Generated from apps/api/contracts; do not edit. */

/**
 * 要設定、清空或處理引用的單一基本資料／目的欄位；引用動作與 read_jd(view=profile) 的 supporting_sources 分組對應。job_title＝職務名稱；organization_unit＝所屬單位；reports_to＝直接匯報對象；purpose＝職務目的。
 */
export type ProfileField = 'job_title' | 'organization_unit' | 'reports_to' | 'purpose';

export interface ReviseJdProfileArguments {
  /**
   * 本次欄位與來源動作。未列出的文字及引用保留；每個文字欄位只設定或清空一次，每筆既有引用只移除或確認一次，同一來源不要重複新增。
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
  /**
   * set_field：用 value 完整取代所選欄位文字，來源另列動作。
   */
  action: 'set_field';
  field: ProfileField;
  /**
   * 該欄完整的新文字，不是差異片段；須含非空白內容且不含 NUL。
   */
  value: string;
}
export interface ClearProfileText {
  /**
   * clear_field：把所選欄位設為 null；既有引用保留，必要的來源移除另列。
   */
  action: 'clear_field';
  field: ProfileField;
}
export interface AddProfileSource {
  /**
   * 增加一筆直接支持所選內容的已讀來源；重加同一來源不會更新既有引用的版本或核對狀態，也不移除其他引用。
   */
  action: 'add_source';
  field: ProfileField;
  /**
   * 要加入此欄的已讀訪談或 Memory 來源；依類別填訪談序號或正文完整標題，App 綁定合法範圍與版本。
   */
  source: InterviewSource | MemorySource;
}
export interface InterviewSource {
  /**
   * 固定為 interview，引用指定序號的訪談原話。
   */
  kind: 'interview';
  /**
   * 直接支持內容的已讀訪談序號：歷史原話使用 context 的 historical_interview.messages 或 read_interview 結果中對應原文的 interview_sequence；本次員工原話使用本次 input 提供的 interview_sequence，不自行推算。
   */
  interview_sequence: number;
}
export interface MemorySource {
  /**
   * 來源類別：work_situation 是已發布工作情境；work_understanding 是已發布工作理解。
   */
  kind: 'work_situation' | 'work_understanding';
  /**
   * 所選類別中、已讀正文的完整 title，原樣取自本輪可見的工作情境／工作理解結果。App 以它定位本輪固定發布版本中的物件；不填 JD 名稱、歷史舊名或自行摘要的標題。
   */
  target_title: string;
}
export interface RemoveProfileSource {
  /**
   * 移除 citation_ref 指定的整筆引用；不改 JD 正文，也不刪除訪談或 Memory 正文。
   */
  action: 'remove_source';
  field: ProfileField;
  /**
   * 取自已取得且仍有效的 read_jd(view=profile) 結果中，supporting_sources[field] 的 citation_ref；必須屬於本次 field，不是來源序號、標題或其他欄的引用。
   */
  citation_ref: string;
}
export interface AlignProfileSource {
  /**
   * 核清人工改稿或來源更新後，確認這筆仍保留的引用支持目前內容，更新其核對基準；正文無需修改時也可使用。Memory 對齊本輪固定發布版本中的同一物件，訪談仍指同一原話。顧問自己的編修不必再確認；更換來源用 add_source 與 remove_source，未核清不用此動作。
   */
  action: 'confirm_reference_alignment';
  field: ProfileField;
  /**
   * 取自已取得且仍有效的 read_jd(view=profile) 結果中，supporting_sources[field] 的 citation_ref；必須屬於本次 field，不是來源序號、標題或其他欄的引用。
   */
  citation_ref: string;
}
