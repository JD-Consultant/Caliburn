/* Generated from apps/api/contracts; do not edit. */

export interface JdCapabilitiesView {
  revision_id: string;
  capabilities: Capability[];
  task_links: TaskLink[];
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
