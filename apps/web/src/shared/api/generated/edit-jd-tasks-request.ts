/* Generated from apps/api/contracts; do not edit. */

export type NullableText = string | null;
export type Text = string;
export type TaskChange = SetField | AddDetail | ReviseDetail | RemoveDetail;

/**
 * One bounded manual task edit at an observed formal JD revision. Detail groups are independent; moving preserves task identity.
 */
export interface EditJdTasksRequest {
  command_id: string;
  expected_revision_id: string;
  change: CreateTask | ReviseTask | MoveTask | ReorderDetail | DeleteTask;
}
export interface CreateTask {
  action: 'create_task';
  /**
   * Null means unassigned, not a fabricated responsibility group.
   */
  area_id: string | null;
  title: NullableText;
  description: NullableText;
  outcomes: Text[];
  requirements: Text[];
}
export interface ReviseTask {
  action: 'revise_task';
  task_id: string;
  /**
   * @minItems 1
   */
  changes: [TaskChange, ...TaskChange[]];
}
export interface SetField {
  action: 'set_field';
  field: 'title' | 'description';
  value: NullableText;
}
export interface AddDetail {
  action: 'add_detail';
  kind: 'outcome' | 'requirement';
  text: Text;
}
export interface ReviseDetail {
  action: 'revise_detail';
  detail_id: string;
  text: Text;
}
export interface RemoveDetail {
  action: 'remove_detail';
  detail_id: string;
}
export interface MoveTask {
  action: 'move_task';
  task_id: string;
  area_id: string | null;
  /**
   * Existing neighbour in the destination group; null means append.
   */
  before_task_id: string | null;
  /**
   * Only this task's content adjustments required by the move; [] retains all content.
   */
  changes: TaskChange[];
}
export interface ReorderDetail {
  action: 'reorder_detail';
  task_id: string;
  detail_id: string;
  /**
   * Same task and same kind only; null means last in its own group.
   */
  before_detail_id: string | null;
}
export interface DeleteTask {
  action: 'delete_task';
  task_id: string;
}
