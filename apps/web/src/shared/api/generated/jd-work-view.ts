/* Generated from apps/api/contracts; do not edit. */

/**
 * Responsibility areas, tasks, shared knowledge/skills and their links from one fixed formal JD revision, for the manual grouped editor.
 */
export interface JdWorkView {
  revision_id: string;
  areas: Area[];
  tasks: WorkTask[];
  capabilities: Capability[];
  task_links: TaskLink[];
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
export interface Capability {
  capability_id: string;
  kind: 'knowledge' | 'skill';
  name: string | null;
  description: string | null;
}
export interface TaskLink {
  task_id: string;
  capability_id: string;
}
