/* Generated from apps/api/contracts; do not edit. */

export interface JdConditionsView {
  revision_id: string;
  conditions: Condition[];
}
export interface Condition {
  condition_id: string;
  kind:
    | 'work_environment'
    | 'schedule_travel'
    | 'shared_authority'
    | 'shared_collaboration'
    | 'qualification';
  text: string;
}
