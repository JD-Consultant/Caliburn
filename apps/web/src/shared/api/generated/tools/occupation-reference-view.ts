/* Generated from apps/api/contracts; do not edit. */

/**
 * 公開公版參考的完整已解析任務導覽；不是員工事實或完整度判定。
 */
export interface OccupationReferenceView {
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
