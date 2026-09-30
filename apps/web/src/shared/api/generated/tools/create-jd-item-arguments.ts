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
  title: string | null;
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
  description: string | null;
  supporting_sources: Source[];
}
export interface CollaboratorItem {
  kind: 'collaborator';
  name: string | null;
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
  text: string;
  supporting_sources: Source[];
}
