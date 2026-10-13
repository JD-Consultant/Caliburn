/* Generated from apps/api/contracts; do not edit. */

/**
 * 引用所屬目標；本工具只接受 kind=item，表示外層 read_ref 指向的項目。任務成果／要求與能力用途皆歸任務，不另設子目標。
 */
export type SourceTarget = ItemTarget;
/**
 * 要加入此項的已讀訪談或 Memory 來源。任務來源支持正文、成果、要求與能力用途；能力定義自己的來源須選該定義另行修改。
 */
export type Source = InterviewSource | MemorySource;

export interface ReviseJdItemArguments {
  /**
   * 要修訂的既有職責、任務、知識／技能、協作或共通條件定位；成果／要求以其 task_read_ref 所指的任務作外層目標。原樣使用目前仍有效的 jd_map、read_jd 或成功建立回傳提供的 read_ref，不依名稱或序號自行組出。
   */
  read_ref: string;
  /**
   * 本次單一項目的文字、明細、能力關係及來源動作；未列部分保留。每個文字欄位、既有明細或既有引用只改一次；每個能力關係的連接狀態與順序各至多改一次，解除的關係不可同次排序。
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
  /**
   * set_field：以 value 完整取代欄位文字，來源變更另列。
   */
  action: 'set_field';
  /**
   * 依外層項目類別選欄：任務 title（名稱）／description（正文）；職責 title（名稱）／scope_text（範圍）；知識或技能 name（名稱）／description（定義正文）；協作 name（對象）／scope_text（合作範圍）；共通條件 text（正文）。
   */
  field: 'title' | 'description' | 'scope_text' | 'name' | 'text';
  /**
   * 該欄完整的新文字，不是 patch；須有非空白文字且不含 NUL。既有引用保留；實改的支持內容同步更新 JD 核對基準，Memory 來源版本仍由引用動作更新。
   */
  value: string;
}
export interface ClearItemText {
  /**
   * clear_field：把可空欄位設為 null；不刪除項目或其引用。
   */
  action: 'clear_field';
  /**
   * 依項目類別選可空欄：任務 title／description、職責 title／scope_text、知識或技能 name／description、協作 name／scope_text；每組至少一欄仍有內容。共通條件及成果／要求正文不可清空。
   */
  field: 'title' | 'description' | 'scope_text' | 'name';
}
export interface SetConditionKind {
  /**
   * set_field：更改外層共通條件的分類，保留其正文與物件身分。
   */
  action: 'set_field';
  /**
   * 固定填 kind，對應讀取結果的 condition_kind；僅外層為共通條件時適用。
   */
  field: 'kind';
  /**
   * 新的共通條件分類。work_environment＝工作環境；schedule_travel＝工時、排程與差旅；shared_authority＝跨任務共通權限；shared_collaboration＝跨任務共通協作；qualification＝任職資格。
   */
  value:
    | 'work_environment'
    | 'schedule_travel'
    | 'shared_authority'
    | 'shared_collaboration'
    | 'qualification';
}
export interface AddTaskDetail {
  /**
   * add_detail：在外層任務新增一筆成果或要求，加入該類明細末尾。
   */
  action: 'add_detail';
  /**
   * outcome＝形成、交付或維持的結果與用途；requirement＝執行或完成時的品質、時限、條件與判準。
   */
  kind: 'outcome' | 'requirement';
  /**
   * 這一筆成果／要求的完整非空正文；與任務共用 supporting_sources，不另填子項來源。
   */
  text: string;
}
export interface ReviseTaskDetail {
  /**
   * revise_detail：取代外層任務中一筆既有成果或要求的正文，保留明細身分與類別。
   */
  action: 'revise_detail';
  /**
   * 屬於外層任務的既有 outcome／requirement 定位，取自 read_jd 的任務明細或明細 item 結果之 read_ref；不可填其他任務明細。
   */
  detail_read_ref: string;
  /**
   * 該筆成果／要求完整的新正文；保留其他明細與任務引用，來源變更另列。
   */
  text: string;
}
export interface RemoveTaskDetail {
  /**
   * remove_detail：刪除外層任務的一筆成果或要求，保留任務及任務引用。
   */
  action: 'remove_detail';
  /**
   * 要刪的既有 outcome／requirement 定位，取自 read_jd；必須屬於外層 read_ref 所選任務。
   */
  detail_read_ref: string;
}
export interface LinkCapability {
  /**
   * set_capability：設定外層任務對既有知識／技能的使用關係。
   */
  action: 'set_capability';
  /**
   * 要讓此任務使用的既有知識或技能定義定位；尚無定義時先 create_jd_item。原樣使用目前仍有效的 jd_map、read_jd 或成功建立回傳提供的 read_ref，不依名稱或序號自行組出。
   */
  capability_read_ref: string;
  /**
   * 固定為 link，連接此任務與該共用定義；不改定義正文或其來源，也不另外接受用途文字。
   */
  relationship: 'link';
}
export interface UnlinkCapability {
  /**
   * set_capability：設定外層任務對既有知識／技能的使用關係。
   */
  action: 'set_capability';
  /**
   * 要解除本任務使用關係的知識／技能定位；取自已取得的任務 required_knowledge／required_skills。
   */
  capability_read_ref: string;
  /**
   * 固定為 unlink，只解除此任務的關聯；共用定義及其他任務的關係保留。
   */
  relationship: 'unlink';
}
export interface ReorderCapability {
  /**
   * reorder_capability：調整外層任務已連接的知識／技能順序，不改全 JD 共用定義的排列。
   */
  action: 'reorder_capability';
  /**
   * 本任務中要重新排序的已連接知識／技能定位；取自任務的 required_knowledge／required_skills，不能選未連接項目。
   */
  capability_read_ref: string;
  /**
   * 在本任務同類能力關係中的新位置；first／last 不填鄰項，before／after 指定另一個已連接的同類能力。
   */
  position: EdgePosition | RelativePosition;
}
export interface EdgePosition {
  /**
   * first 移到本任務同類能力的最前；last 移到最後，不提供鄰項。
   */
  kind: 'first' | 'last';
}
export interface RelativePosition {
  /**
   * before 放在指定鄰項之前；after 放在指定鄰項之後。
   */
  kind: 'before' | 'after';
  /**
   * 排序參照的鄰項，取自同一任務已連接的能力；與被排序項同為 knowledge 或同為 skill，不是外層要移動的項目。
   */
  capability_read_ref: string;
}
export interface AddSource {
  /**
   * 增加一筆直接支持所選內容的已讀來源；重加同一來源不會更新既有引用的版本或核對狀態，也不移除其他引用。
   */
  action: 'add_source';
  target: SourceTarget;
  source: Source;
}
export interface ItemTarget {
  /**
   * 固定為 item，引用屬於外層 read_ref 所選的 JD 項目；不填來源類別或成果／要求類別。
   */
  kind: 'item';
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
export interface RemoveSource {
  /**
   * 移除 citation_ref 指定的整筆引用；不改 JD 正文，也不刪除訪談或 Memory 正文。
   */
  action: 'remove_source';
  target: SourceTarget;
  /**
   * 取自 read_jd 中屬於外層項目的 supporting_sources[].citation_ref。能力 item 最外層引用屬於能力定義，used_by_tasks 中的引用屬於各任務，不可混用。
   */
  citation_ref: string;
}
export interface AlignSource {
  /**
   * 核清人工改稿或來源更新後，確認這筆仍保留的引用支持目前內容，更新其核對基準；正文無需修改時也可使用。Memory 對齊本輪固定發布版本中的同一物件，訪談仍指同一原話。顧問自己的編修不必再確認；更換來源用 add_source 與 remove_source，未核清不用此動作。任務核對包含正文、成果、要求及已連能力的用途與定義；能力本體來源另核。
   */
  action: 'confirm_reference_alignment';
  target: SourceTarget;
  /**
   * 取自 read_jd 中屬於外層項目的 supporting_sources[].citation_ref。能力 item 最外層引用屬於能力定義，used_by_tasks 中的引用屬於各任務，不可混用。
   */
  citation_ref: string;
}
