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
  source_kind: 'interview' | 'work_situation' | 'work_understanding';
  source_label: string;
  needs_recheck: boolean;
}
