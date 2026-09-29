/* Generated from apps/api/contracts; do not edit. */

export type ConditionKind =
  | 'work_environment'
  | 'schedule_travel'
  | 'shared_authority'
  | 'shared_collaboration'
  | 'qualification';

/**
 * One bounded job-wide condition edit from a fixed formal base. Reclassification retains identity; it never propagates into task requirements.
 */
export interface EditJdConditionsRequest {
  command_id: string;
  expected_revision_id: string;
  change: CreateCondition | ReviseCondition | DeleteCondition | ReorderCondition;
}
export interface CreateCondition {
  action: 'create_condition';
  kind: ConditionKind;
  text: string;
}
export interface ReviseCondition {
  action: 'revise_condition';
  condition_id: string;
  /**
   * @minItems 1
   * @maxItems 2
   */
  changes:
    | [ConditionTextChange | ConditionKindChange]
    | [ConditionTextChange | ConditionKindChange, ConditionTextChange | ConditionKindChange];
}
export interface ConditionTextChange {
  field: 'text';
  value: string;
}
export interface ConditionKindChange {
  field: 'kind';
  value: ConditionKind;
}
export interface DeleteCondition {
  action: 'delete_condition';
  condition_id: string;
}
export interface ReorderCondition {
  action: 'reorder_condition';
  condition_id: string;
  /**
   * Within the current condition kind only; null places it last.
   */
  before_condition_id: string | null;
}
