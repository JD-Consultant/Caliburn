/* Generated from apps/api/contracts; do not edit. */

/**
 * Responsibility areas and tasks from one fixed formal JD revision, for the manual grouped editor.
 */
export interface JdWorkView {
  revision_id: string;
  areas: Area[];
  tasks: WorkTask[];
}
export interface Area {
  area_id: string;
  title: string | null;
  scope_text: string | null;
}
export interface WorkTask {
  task_id: string;
  area_id: string | null;
  title: string | null;
  description: string | null;
  outcomes: Detail[];
  requirements: Detail[];
}
export interface Detail {
  detail_id: string;
  text: string;
}
