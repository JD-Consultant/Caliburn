/* Generated from apps/api/contracts; do not edit. */

/**
 * 去識別化的任務提示：只有任務名稱與其知識/技能/產出/行為指標，不含任何職位身分。
 */
export interface TaskHintSearchResult {
  hints: TaskHint[];
}
export interface TaskHint {
  names: TaskName[];
  competency_blocks: CompetencyBlock[];
}
export interface TaskName {
  code: string | null;
  name: string | null;
}
export interface CompetencyBlock {
  competency_level: number | null;
  outputs: NamedContent[];
  indicators: Indicator[];
  knowledge: NamedContent[];
  skills: NamedContent[];
}
export interface NamedContent {
  code: string | null;
  name: string | null;
}
export interface Indicator {
  code: string | null;
  text: string | null;
}
