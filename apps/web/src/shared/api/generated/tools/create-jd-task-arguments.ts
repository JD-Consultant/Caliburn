/* Generated from apps/api/contracts; do not edit. */

export type Source = CurrentInputSource | InterviewSource | MemorySource;

export interface CreateJdTaskArguments {
  /**
   * 既有職責的 read_ref；null 表示未歸屬。
   */
  parent_read_ref: string | null;
  /**
   * 可辨認本人工作動作與對象的短標題；不是每個案例各建一項任務。
   */
  title: string | null;
  /**
   * 本人做什麼及必要的適用條件、頻率與責任界線；已有事實才寫，不以通用職業知識補齊。
   */
  description: string | null;
  /**
   * 形成或維持的結果、交付物與用途，不是操作步驟。沒有已知內容時用 []。
   */
  outcomes: TaskDetail[];
  /**
   * 已知的完成判準、執行條件或責任界線；與成果並列，不逐項配對，不捏造 KPI。沒有已知內容時用 []。
   */
  requirements: TaskDetail[];
  required_knowledge: TaskCapability[];
  required_skills: TaskCapability[];
  /**
   * 直接支持任務標題與說明的依據；多項事實可用多筆來源。成果、要求與 K/S 關係各自提供依據，不繼承本清單。
   */
  supporting_sources: Source[];
}
export interface TaskDetail {
  text: string;
  /**
   * 直接支持這一項成果或要求的來源；不能一律複製整個任務的來源。
   */
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
export interface TaskCapability {
  /**
   * read_jd 返回的既有知識或技能定位；尚不存在時先 create_jd_item，不猜 ID。
   */
  capability_read_ref: string;
  /**
   * 支持這項任務確實需要該能力的依據，不只是能力定義本身的來源。
   */
  supporting_sources: Source[];
}
