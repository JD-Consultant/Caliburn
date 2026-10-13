/* Generated from apps/api/contracts; do not edit. */

export type Source = InterviewSource | MemorySource;

export interface CreateJdTaskArguments {
  /**
   * 新任務所屬的既有職責定位；null 表示未歸屬。原樣使用目前仍有效的 jd_map、read_jd 或成功建立回傳提供的 read_ref，不依名稱或序號自行組出。
   */
  parent_read_ref: string | null;
  /**
   * 任務短標題，用於辨認工作動作與對象；未提供標題用 null。title 與 description 至少一個有非空白文字。
   */
  title: string | null;
  /**
   * 任務正文，寫本人做什麼、作用對象及必要的條件與責任界線；不是導覽摘要。未提供正文用 null，不能與 title 同時為 null。
   */
  description: string | null;
  /**
   * 任務形成、交付或維持的結果與用途，每筆放在 text；依陣列順序建立。沒有已確認內容時用 []。
   */
  outcomes: TaskDetail[];
  /**
   * 任務執行或完成時須符合的品質、時限、條件與判準，每筆放在 text；依陣列順序建立，與成果不必一對一，沒有內容用 []。
   */
  requirements: TaskDetail[];
  /**
   * 此任務需使用的既有知識定義，以 capability_read_ref 連接；只接受 knowledge，依陣列順序排列，不在此建立或改寫定義，沒有連接項目用 []。
   */
  required_knowledge: TaskCapability[];
  /**
   * 此任務需使用的既有技能定義，以 capability_read_ref 連接；只接受 skill，依陣列順序排列，不在此建立或改寫定義，沒有連接項目用 []。
   */
  required_skills: TaskCapability[];
  /**
   * 直接支持本任務正文、成果、要求及能力使用的已讀依據；每個來源列一次，可混合訪談與 Memory。來源不從職責或能力本體自動繼承；本欄不改能力定義的引用。
   */
  supporting_sources: Source[];
}
export interface TaskDetail {
  /**
   * 一筆成果或要求的完整正文；意義由所在的 outcomes／requirements 陣列決定，須有非空白文字且不含 NUL。
   */
  text: string;
}
export interface TaskCapability {
  /**
   * 要連接的共用知識／技能定位，類別須符合所在陣列，每個定義只列一次。原樣使用目前仍有效的 jd_map、read_jd 或成功建立回傳提供的 read_ref，不依名稱或序號自行組出。
   */
  capability_read_ref: string;
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
