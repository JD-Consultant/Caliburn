/* Generated from apps/api/contracts; do not edit. */

/**
 * 公版任務完整已解析細節，與員工 JD 任務可多對多對應。
 */
export interface OccupationReferenceTaskView {
  reference_id: string;
  source_sha256: string;
  task_id: string;
  unit_id: string;
  names: ReferenceTaskName[];
  competency_blocks: ReferenceCompetencyBlock[];
}
export interface ReferenceTaskName {
  code: string | null;
  name: string | null;
}
export interface ReferenceCompetencyBlock {
  competency_level: number | null;
  outputs: NamedContent[];
  indicators: Indicator[];
  knowledge: NamedContent[];
  skills: NamedContent[];
}
export interface NamedContent {
  code: string | null;
  name: string | null;
}
export interface Indicator {
  code: string | null;
  text: string | null;
}
