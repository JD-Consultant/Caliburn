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
  // 來源：v4 indexer task URN 拆解（ocs_code, task_code）；自訂/cherry-pick 任務 task_code 為 ""。
  provenance?: { ocs_code: string; task_code: string; urn?: string };
  _tid?: string; // 前端穩定 id（拖拉用；隨項目移動）
  _notes?: string; // D28 工作筆記（5W2H/CIT 原文，餵 AI＋給顧問）；非契約欄，finalize/export 剝除
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
}

// GET/PATCH/finalize/seed 的回傳信封（DocRepo._to_dict / no-doc 空殼）。
export interface DocumentEnvelope {
  id: string | null;
  version: number;
  status: DocStatus;
  content: OcsDocument;
}

export interface OcsSearchHit {
  ocs_code: string;
  ocs_name: string;
}

// 選任務候選（task-candidates）：依職類 → 職責(unit) 分組。
export interface CandidateTask {
  task_code: string;
  task_name: string;
  urn: string;
}
export interface CandidateUnit {
  ocu_code: string;
  ocu_name: string;
  tasks: CandidateTask[];
}
export interface CandidateGroup {
  ocs_code: string;
  ocs_name: string;
  units: CandidateUnit[];
}
export interface TaskCandidates {
  groups: CandidateGroup[];
}

// build-tasks 送出的一筆勾選任務。ocu_name 留白＝cherry-pick（職責名讓使用者填）。
export interface PickedTask {
  ocs_code: string;
  ocu_code: string;
  ocu_name: string;
  ocs_name: string;
  task_code: string;
  task_name: string;
}

// ── 表頭候選池（D29 /header-meta）：多 OCS 聯集去重；勾選後 PATCH 寫文件表頭 ──
// 每候選帶 sources（哪些 ocs_code 帶入），供「最後一個來源移除才下架」。
export interface HeaderMetaCandidate {
  code: string;
  name: string;
  sources: string[];
}
export interface HeaderMetaText {
  text: string;
  sources: string[];
}
export interface HeaderMetaPrimaryOption {
  ocs_code: string;
  occupation_name: string;
  job_category_name: string;
  job_description: string;
  ocs_level: number | null;
}
export interface HeaderMeta {
  primary: {
    ocs_code: string;
    occupation_name: string;
    job_category_name: string;
    job_description: string;
    ocs_level: number | null;
  };
  primary_options: HeaderMetaPrimaryOption[];
  job_categories: HeaderMetaCandidate[];
  occupations: HeaderMetaCandidate[];
  industries: HeaderMetaCandidate[];
  attitudes: HeaderMetaCandidate[];
  prerequisites: HeaderMetaText[];
  supplements: HeaderMetaText[];
}

// ── AI 提議（D28 /ai/*）：結構化提議、不寫 DB；前端暫存→使用者套用→走現有 PATCH ──
export type AiSource = "catalog" | "ai";

// recommend-ks：每項標來源；K/S 帶一句理由（catalog 篩選/AI 生成）。
export interface KsSuggestion {
  code: string;
  name: string;
  source: AiSource;
  reason?: string;
}
export interface RecommendKsResult {
  knowledge: KsSuggestion[];
  skills: KsSuggestion[];
}

// draft-op：產出(O)/指標(P) 提議，帶來源。
export interface OutputSuggestion {
  name: string;
  source: AiSource;
}
export interface IndicatorSuggestion {
  text: string;
  source: AiSource;
}
export interface DraftOpResult {
  outputs: OutputSuggestion[];
  indicators: IndicatorSuggestion[];
}

// extract-tasks：預勾的 catalog 任務 UUID + 候選自訂任務（名）。
export interface ExtractTasksResult {
  suggested_task_ids: string[];
  custom_candidates: { name: string }[];
}

// structure-task：自訂任務一句描述 → 任務名 + 職責建議。
export interface StructureTaskResult {
  task_name: string;
  unit_suggestion: string;
}

// clarify：太薄時回一個追問；否則 null。
export interface ClarifyResult {
  question: string | null;
}

export interface OptionItem {
  code: string;
  name: string;
  sources?: string[];
}
