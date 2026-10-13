/* Generated from apps/api/contracts; do not edit. */

export type Source = InterviewSource | MemorySource;

export interface CreateJdItemArguments {
  /**
   * 本次新建的單一項目；kind 決定哪一組欄位適用，supporting_sources 只支持該項本身。
   */
  item: ResponsibilityAreaItem | CapabilityItem | CollaboratorItem | JobWideConditionItem;
}
export interface ResponsibilityAreaItem {
  /**
   * 固定為 responsibility_area，建立可容納任務的職責。
   */
  kind: 'responsibility_area';
  /**
   * 職責名稱，概括共同工作目的或責任範圍；可為 null，但 title 與 scope_text 至少一欄有內容。
   */
  title: string | null;
  /**
   * 職責範圍正文，說明涵蓋哪些工作及必要界線；無須另補範圍文字時可為 null，但不能與 title 同時為 null。
   */
  scope_text: string | null;
  /**
   * 直接支持此職責名稱與範圍的已讀依據；不會自動傳給日後歸入此職責的任務。
   */
  supporting_sources: Source[];
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
export interface CapabilityItem {
  /**
   * knowledge 建立知識定義；skill 建立技能定義。兩者都是可供多個任務使用的共用項目。
   */
  kind: 'knowledge' | 'skill';
  /**
   * 知識／技能名稱；可為 null，但 name 與 description 至少一欄有內容。
   */
  name: string | null;
  /**
   * 定義正文：知識是工作需理解的概念、規則與適用範圍；技能是運用方法完成工作或處理問題的能力。可為 null，但不能與 name 同時為 null。
   */
  description: string | null;
  /**
   * 直接支持此知識／技能定義的已讀依據；與每個使用任務的 supporting_sources 分開，不會自動建立任務關聯。
   */
  supporting_sources: Source[];
}
export interface CollaboratorItem {
  /**
   * 固定為 collaborator，建立一個主要協作對象。
   */
  kind: 'collaborator';
  /**
   * 協作對象的名稱、角色或單位；可為 null，但 name 與 scope_text 至少一欄有內容。
   */
  name: string | null;
  /**
   * 與此對象配合或交接的事項及雙方責任界線；可為 null，但不能與 name 同時為 null。
   */
  scope_text: string | null;
  /**
   * 直接支持此協作對象及合作範圍的已讀依據；不替代任務自己的來源。
   */
  supporting_sources: Source[];
}
export interface JobWideConditionItem {
  /**
   * 固定為 job_wide_condition，建立跨任務適用的共通條件。
   */
  kind: 'job_wide_condition';
  /**
   * 共通條件的分類。work_environment＝工作環境；schedule_travel＝工時、排程與差旅；shared_authority＝跨任務共通權限；shared_collaboration＝跨任務共通協作；qualification＝任職資格。
   */
  condition_kind:
    | 'work_environment'
    | 'schedule_travel'
    | 'shared_authority'
    | 'shared_collaboration'
    | 'qualification';
  /**
   * 此共通條件的完整正文，須有非空白文字且不含 NUL；只適用單一任務的內容放該任務。
   */
  text: string;
  /**
   * 直接支持此條件正文及其跨任務適用範圍的已讀依據。
   */
  supporting_sources: Source[];
}
