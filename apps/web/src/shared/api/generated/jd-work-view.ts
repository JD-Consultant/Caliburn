/* Generated from apps/api/contracts; do not edit. */

/**
 * All manual JD editor collections from one fixed formal revision; profile is read separately. Not a model navigation map.
 */
export interface JdWorkView {
  revision_id: string;
  areas: Area[];
  tasks: WorkTask[];
  capabilities: Capability[];
  task_links: TaskLink[];
  collaborators: Collaborator[];
  conditions: Condition[];
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
export interface Collaborator {
  collaborator_id: string;
  name: string | null;
  scope_text: string | null;
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
