/* Generated from apps/api/contracts; do not edit. */

/**
 * Complete navigation of the App-bound visible JD. Previews are excerpts, not edit bases or instructions. Empty collections are complete empty results. read_ref selects an item, never grants permission or selects a version.
 */
export interface JdMap {
  profile: JdProfileMap;
  responsibility_areas: JdAreaMap[];
  unassigned_work_tasks: JdTaskMap[];
  required_knowledge: JdNamedMapItem[];
  required_skills: JdNamedMapItem[];
  main_collaborators: JdNamedMapItem[];
  job_wide_conditions: JdConditionMapItem[];
}
export interface JdProfileMap {
  job_title: string | null;
  organization_unit: string | null;
  reports_to: string | null;
  job_purpose_preview?: string;
}
export interface JdAreaMap {
  read_ref: string;
  title: string | null;
  scope_preview?: string;
  work_tasks: JdTaskMap[];
}
export interface JdTaskMap {
  read_ref: string;
  title: string | null;
  work_preview?: string;
  outcome_count: number;
  requirement_count: number;
}
export interface JdNamedMapItem {
  read_ref: string;
  name: string | null;
}
export interface JdConditionMapItem {
  read_ref: string;
  description_preview: string;
}
