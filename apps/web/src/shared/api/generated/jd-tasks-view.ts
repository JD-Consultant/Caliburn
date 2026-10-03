/* Generated from apps/api/contracts; do not edit. */

/**
 * Tasks at one fixed formal JD revision. Unassigned first, then responsibility groups in their order; each task and detail group preserves its own order.
 */
export interface JdTasksView {
  revision_id: string;
  tasks: WorkTask[];
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
