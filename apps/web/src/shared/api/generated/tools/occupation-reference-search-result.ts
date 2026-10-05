/* Generated from apps/api/contracts; do not edit. */

export interface OccupationReferenceSearchResult {
  /**
   * @maxItems 5
   */
  references:
    | []
    | [OccupationReference]
    | [OccupationReference, OccupationReference]
    | [OccupationReference, OccupationReference, OccupationReference]
    | [OccupationReference, OccupationReference, OccupationReference, OccupationReference]
    | [
        OccupationReference,
        OccupationReference,
        OccupationReference,
        OccupationReference,
        OccupationReference
      ];
}
export interface OccupationReference {
  reference_id: string;
  source_sha256: string;
  source_file: string;
  ocs_code: string;
  title: string;
  overview: string;
  catalog_scope: 'all_parsed_task_groups';
  units: ReferenceUnit[];
}
export interface ReferenceUnit {
  unit_id: string;
  code: string | null;
  name: string | null;
  tasks: ReferenceTaskSummary[];
}
export interface ReferenceTaskSummary {
  task_id: string;
  names: ReferenceTaskName[];
  competency_block_count: number;
}
export interface ReferenceTaskName {
  code: string | null;
  name: string | null;
}
