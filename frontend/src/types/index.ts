// v3 types. The old conversation-driven model (Stage union, GraphState,
// OcsDocument, Task, KsaItem, IcapCandidate, InterviewMessage, …) was retired
// with the old backend (Concern B); the v3 interview state lives in the
// LangGraph checkpointer and is surfaced via interrupt payloads, not here.

export interface User {
  id: string;
  email: string;
  name: string;
  company?: string;
  created_at: string;
}

export type DocStatus = "none" | "draft" | "final";

export interface JobProfile {
  id: string;
  user_id: string;
  job_title: string;
  department?: string | null;
  job_summary?: string | null;
  created_at: string;
  updated_at: string;
  // D27: list 端點補的文件狀態（單筆 GET 用 schema 預設 none/0）。
  doc_status?: DocStatus;
  completion?: number;
}

// ── OCS document contract (D27) ──────────────────────────────────────────────
// of-record = 一份合法 OCS JSON（jd-pdf-to-json 契約）。MVP 採「每任務一個
// competency_block」；K/S/A item 為 {code,name}（code 可空字串），P 為 {code,text}。

export interface CodeName {
  code: string;
  name: string;
}

export interface Indicator {
  code: string;
  text: string;
}

export interface CompetencyBlock {
  competency_level: number | null;
  indicators: Indicator[];
  outputs: CodeName[];
  knowledge: CodeName[];
  skills: CodeName[];
}

export interface OcsTask {
  task_codes: CodeName[];
  competency_blocks: CompetencyBlock[];
  provenance?: { ocs_code: string; task_id: string };
  _tid?: string; // 前端穩定 id（拖拉用；隨項目移動）
}

export interface OcuUnit {
  ocu_code: string;
  ocu_name: string;
  source?: { ocs_code: string; occupation_name: string };
  tasks: OcsTask[];
  _uid?: string; // 前端穩定 id（拖拉用）
}

export interface OcsName {
  job_category_name: string | null;
  occupation_name: string;
}

export interface OcsCategory {
  job_categories: CodeName[];
  occupations: CodeName[];
  industries: CodeName[];
}

export interface OcsProfile {
  ocs_code: string;
  ocs_name: OcsName;
  category: OcsCategory;
  job_description: string;
  ocs_level: number | null;
}

export interface OcsDocument {
  version_info: { versions: unknown[] };
  ocs_profile: OcsProfile;
  ocs_content: { ocu_units: OcuUnit[] };
  ocs_attitude: { attitudes: CodeName[] };
  notes: { prerequisites: string[]; supplements: string[] };
  // 前端全域候選池（使用者新增的 K/S/A，跨任務共用；非 OCS 契約欄，finalize 可忽略）
  _pool?: { knowledge: CodeName[]; skills: CodeName[]; attitudes: CodeName[] };
}

// GET/PATCH/finalize/seed 的回傳信封（DocRepo._to_dict / no-doc 空殼）。
export interface DocumentEnvelope {
  id: string | null;
  version: number;
  status: DocStatus;
  content: OcsDocument;
}

export interface KsaPool {
  knowledge: CodeName[];
  skills: CodeName[];
  attitudes: CodeName[];
}

export interface OcsSearchHit {
  ocs_code: string;
  job_title: string;
}

// 選任務候選（task-candidates）：依職類 → 職責(unit) 分組。
export interface CandidateTask {
  task_id: string;
  task_title: string;
}
export interface CandidateUnit {
  unit_id: string;
  unit_title: string;
  tasks: CandidateTask[];
}
export interface CandidateGroup {
  ocs_code: string;
  occupation_name: string;
  units: CandidateUnit[];
}
export interface TaskCandidates {
  groups: CandidateGroup[];
}

// build-tasks 送出的一筆勾選任務。unit_title 留白＝cherry-pick（職責名讓使用者填）。
export interface PickedTask {
  ocs_code: string;
  unit_id: string;
  unit_title: string;
  occupation_name: string;
  task_id: string;
  task_name: string;
}
