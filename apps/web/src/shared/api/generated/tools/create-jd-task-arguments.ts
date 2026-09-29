/* Generated from apps/api/contracts; do not edit. */

export type Source = CurrentInputSource | InterviewSource | MemorySource;

export interface CreateJdTaskArguments {
  /**
   * 既有職責的 read_ref；null 表示未歸屬。
   */
  parent_read_ref: string | null;
  title: string | null;
  description: string | null;
  outcomes: TaskDetail[];
  requirements: TaskDetail[];
  required_knowledge: TaskCapability[];
  required_skills: TaskCapability[];
  supporting_sources: Source[];
}
export interface TaskDetail {
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
export interface TaskCapability {
  capability_read_ref: string;
  supporting_sources: Source[];
}
