/* Generated from apps/api/contracts; do not edit. */

export type NullableText = string | null;

/**
 * One bounded responsibility-group edit from the observed formal base. Replay the same command if the result is uncertain.
 */
export interface EditJdAreasRequest {
  command_id: string;
  expected_revision_id: string;
  change: CreateArea | ReviseArea | DeleteArea | ReorderArea;
}
export interface CreateArea {
  action: 'create_area';
  title: NullableText;
  scope_text: NullableText;
}
export interface ReviseArea {
  action: 'revise_area';
  area_id: string;
  /**
   * @minItems 1
   * @maxItems 2
   */
  changes: [AreaFieldChange] | [AreaFieldChange, AreaFieldChange];
}
export interface AreaFieldChange {
  field: 'title' | 'scope_text';
  value: NullableText;
}
export interface DeleteArea {
  action: 'delete_area';
  area_id: string;
}
export interface ReorderArea {
  action: 'reorder_area';
  area_id: string;
  /**
   * Place before this existing group; null means last. IDs select identity, never position.
   */
  before_area_id: string | null;
}
