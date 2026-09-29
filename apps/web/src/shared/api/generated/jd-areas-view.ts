/* Generated from apps/api/contracts; do not edit. */

/**
 * Ordered responsibility groups in one fixed formal JD revision; tasks are not expanded here.
 */
export interface JdAreasView {
  revision_id: string;
  areas: Area[];
}
export interface Area {
  area_id: string;
  title: string | null;
  scope_text: string | null;
}
