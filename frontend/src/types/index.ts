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
}

export interface OcuUnit {
  ocu_code: string;
  ocu_name: string;
  tasks: OcsTask[];
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
