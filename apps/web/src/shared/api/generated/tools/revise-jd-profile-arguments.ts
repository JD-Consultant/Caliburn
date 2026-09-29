/* Generated from apps/api/contracts; do not edit. */

export type ProfileField = 'job_title' | 'organization_unit' | 'reports_to' | 'purpose';

export interface ReviseJdProfileArguments {
  /**
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
  value: string;
}
export interface ClearProfileText {
  action: 'clear_field';
  field: ProfileField;
}
export interface AddProfileSource {
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
  action: 'remove_source';
  field: ProfileField;
  citation_ref: string;
}
export interface AlignProfileSource {
  action: 'confirm_reference_alignment';
  field: ProfileField;
  citation_ref: string;
}
