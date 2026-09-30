/* Generated from apps/api/contracts; do not edit. */

/**
 * Direct evidence belonging to one currently formal JD revision. Reading never confirms alignment.
 */
export interface JdSourcesView {
  revision_id: string;
  references: Reference[];
}
export interface Reference {
  citation_id: string;
  target_label: string;
  target?: Target;
  source_kind: 'interview' | 'work_situation' | 'work_understanding';
  source_label: string;
  needs_recheck: boolean;
}
/**
 * The JD item this reference supports, by identity. target_label is only its human label; never resolve a target by label. Absent when the server predates this field.
 */
export interface Target {
  kind:
    | 'profile_field'
    | 'area'
    | 'task'
    | 'detail'
    | 'capability'
    | 'collaborator'
    | 'condition'
    | 'task_capability';
  /**
   * Set only for profile_field.
   */
  field: ('job_title' | 'organization_unit' | 'reports_to' | 'purpose') | null;
  item_id: string | null;
  /**
   * The owning task, set only for detail and task_capability.
   */
  task_id: string | null;
}
