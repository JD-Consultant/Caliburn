/* Generated from apps/api/contracts; do not edit. */

export type Source = CurrentInputSource | InterviewSource | MemorySource;

export interface CreateJdItemArguments {
  /**
   * 建立一個職責、共用知識／技能、協作對象或共通條件；任務及其成果／要求使用其他既定入口。
   */
  item: ResponsibilityAreaItem | CapabilityItem | CollaboratorItem | JobWideConditionItem;
}
export interface ResponsibilityAreaItem {
  kind: 'responsibility_area';
  /**
   * 按共同工作目的或責任範圍命名；不是單一案例名稱。
   */
  title: string | null;
  /**
   * 此職責涵蓋的已知工作範圍及必要邊界；名稱已足夠清楚時可為 null。
   */
  scope_text: string | null;
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
export interface CapabilityItem {
  kind: 'knowledge' | 'skill';
  name: string | null;
  /**
   * 知識：工作需理解的概念；技能：運用知識與方法完成工作的能力。從實際工作推得，不從職稱或工具名猜測。
   */
  description: string | null;
  supporting_sources: Source[];
}
export interface CollaboratorItem {
  kind: 'collaborator';
  name: string | null;
  /**
   * 與此對象合作或交接的事項及責任邊界；不推定對方是主管或核准人。
   */
  scope_text: string | null;
  supporting_sources: Source[];
}
export interface JobWideConditionItem {
  kind: 'job_wide_condition';
  condition_kind:
    | 'work_environment'
    | 'schedule_travel'
    | 'shared_authority'
    | 'shared_collaboration'
    | 'qualification';
  /**
   * 確有依據且跨任務適用的環境、時間／差旅、權限、協作或資格條件；只適用單項任務時寫在該任務，不擴大為全職務規則。
   */
  text: string;
  supporting_sources: Source[];
}
