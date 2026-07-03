// types. The old conversation-driven model (Stage union, GraphState,
// OcsDocument, Task, KsaItem, IcapCandidate, InterviewMessage, …) was retired
// with the old backend (Concern B); the interview state lives in the
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

// The OCS document shape is generated from packages/ocs-contract's JSON schema
// (single source of truth). The web layers front-end-only fields (_id/_uid/…)
// on top via these UI types = generated base (Omit + re-tighten) & UI fields.
// Contract #3 Part A; see docs/contract-strategy.md + ADR 0011.
import type {
  Category as GenCategory,
  CodeName as GenCodeName,
  CodeText as GenCodeText,
  CompetencyBlock as GenBlock,
  OCSDocument as GenDoc,
  OcsName as GenOcsName,
  OcsProfile as GenProfile,
  OcuUnit as GenUnit,
  TaskGroup as GenTask,
} from "@caliburn/ocs-contract";

export type ItemSource = "official" | "custom";

export interface SourceRef {
  ocs_code: string;        // 來源官方基準碼，如 INM3513-009v1
  occupation_name: string; // 來源職業名，如 AIoT應用工程師
  code: string;            // 該項在來源文件的原始碼（O1.1.1 / K01 / INM；O/P 暫為 ""）
  task_code?: string;      // 來源任務碼（任務範圍項目才有，如 T1.1）
  task_name?: string;      // 來源任務名
}

// Leaves: derived from the generated contract, with code/name(/text) tightened to
// non-null strings (the editing UI always holds strings, never null) + UI fields.
export type CodeName = Omit<GenCodeName, "code" | "name"> & {
  code: string;
  name: string;
  _id?: string;            // 穩定 UUID：dnd/編輯 key + 排序錨點
  _src?: ItemSource;       // 來源；加入當下即定
  _ref?: SourceRef;        // 官方來源；改內容→清空（轉自訂）
};

export type Indicator = Omit<GenCodeText, "code" | "text"> & {
  code: string;
  text: string;
  _id?: string;
  _src?: ItemSource;
  _ref?: SourceRef;
};

export type CompetencyBlock = Omit<
  GenBlock,
  "competency_level" | "indicators" | "outputs" | "knowledge" | "skills"
> & {
  competency_level: number | null;
  indicators: Indicator[];
  outputs: CodeName[];
  knowledge: CodeName[];
  skills: CodeName[];
};

export type OcsTask = Omit<GenTask, "task_codes" | "competency_blocks"> & {
  task_codes: CodeName[];
  competency_blocks: CompetencyBlock[];
  // 來源：v4 indexer task URN 拆解（ocs_code, task_code）；自訂/cherry-pick 任務 task_code 為 ""。
  provenance?: { ocs_code: string; task_code: string; urn?: string };
  _tid?: string; // 前端穩定 id（拖拉用；隨項目移動）
  _notes?: string; // D28 工作筆記（5W2H/CIT 原文，餵 AI＋給顧問）；非契約欄，finalize/export 剝除
  _levelSrc?: SourceRef & { level: number }; // 帶官方時記下「官方級別 + 來源（含任務）」；export 剝除
  _refs?: SourceRef[]; // 多來源（合併列選入）：全部來源；provenance 取首個（相容單來源讀者）
};

export type OcuUnit = Omit<GenUnit, "ocu_code" | "ocu_name" | "tasks"> & {
  ocu_code: string;
  ocu_name: string;
  source?: { ocs_code: string; occupation_name: string };
  tasks: OcsTask[];
  _refs?: SourceRef[]; // 多來源（合併職責列選入）
  _uid?: string; // 前端穩定 id（拖拉用）
};

export type OcsName = Omit<GenOcsName, "job_category_name" | "occupation_name"> & {
  job_category_name: string | null;
  occupation_name: string;
};

export type OcsCategory = Omit<GenCategory, "job_categories" | "occupations" | "industries"> & {
  job_categories: CodeName[];
  occupations: CodeName[];
  industries: CodeName[];
};

export type OcsProfile = Omit<
  GenProfile,
  "ocs_name" | "category" | "job_description" | "ocs_level"
> & {
  ocs_name: OcsName;
  category: OcsCategory;
  job_description: string;
  ocs_level: number | null;
};

export type OcsDocument = Omit<
  GenDoc,
  "version_info" | "ocs_profile" | "ocs_content" | "ocs_attitude" | "notes"
> & {
  version_info: { versions: unknown[] };
  ocs_profile: OcsProfile;
  ocs_content: { ocu_units: OcuUnit[] };
  ocs_attitude: { attitudes: CodeName[] };
  notes: { prerequisites: string[]; supplements: string[] };
};

// GET/PATCH/finalize/seed 的回傳信封（DocRepo._to_dict / no-doc 空殼）。
// revision（2a, ADR 0015）：單一列的編輯回合計數，PATCH 樂觀鎖 token 之一
// （另一為既有 version）；無文件的空殼固定 0。
export interface DocumentEnvelope {
  id: string | null;
  version: number;
  revision: number;
  status: DocStatus;
  content: OcsDocument;
}

export interface OcsSearchHit {
  ocs_code: string;
  ocs_name: string;
}

// 降級旗標（ADR 0018）：enrichment 端點在 indexer 掛時回 partial=true，
// 前端可提示「部分資料暫缺」；缺席或 false 視為完整。
export interface DegradeMeta {
  partial: boolean;
}

// ── AI 提議（D28 /ai/*）：結構化提議、不寫 DB；前端暫存→使用者套用→走現有 PATCH ──
// （recommend-ks/draft-op server 端仍在（ADR 0020 訪談引擎/agent 用）；web 填格改吃
// 知識包後不再呼叫，對應型別已退役。）

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

export interface OptionItem {
  code: string;
  name: string;
  sources?: string[];      // 既有：ocs_code 清單（向後相容）
  srcs?: SourceRef[];      // 新：完整來源（選單顯示用；首個 + 其餘）
}

// ── 知識包(ADR 0021):選職類後一次抓齊,所有選單的資料源;每官方值帶 srcs ──
// 鍵語意:值池 key=name/text、三類池 key=分類碼;tasks 池 srcs=source_tasks 的 URN;
// source_tasks 鍵=任務 URN。欄位名照 indexer-contract(手寫型別,ADR 0021 契約裁決)。
export interface PackSrc {
  ocs_code: string; ocs_name: string;
  ocu_code?: string | null; ocu_name?: string | null;
  task_code?: string | null; task_name?: string | null;
  code?: string | null; competency_level?: number | null;
}
export interface PoolRow { srcs: PackSrc[] }
export interface CodedPoolRow extends PoolRow { name: string }   // 三類池(key=國家分類碼)
export interface SourceTask {
  ocs_code: string; ocs_name: string;
  ocu_code?: string | null; ocu_name?: string | null;
  task_code: string; task_name: string;
  competency_level: number | null;
  o_refs: string[]; p_refs: string[]; k_refs: string[]; s_refs: string[];
}
export interface KnowledgePack {
  occupation_details: {
    ocs_code: string;
    ocs_name: { job_category_name?: string | null; occupation_name?: string | null };
    job_description: string; ocs_level: number | null;
  }[];
  pools: {
    units: Record<string, PoolRow>;
    tasks: Record<string, { srcs: string[] }>;
    knowledge: Record<string, PoolRow>; skills: Record<string, PoolRow>;
    outputs: Record<string, PoolRow>; indicators: Record<string, PoolRow>;
    attitudes: Record<string, PoolRow>;
    job_categories: Record<string, CodedPoolRow>;
    occupations: Record<string, CodedPoolRow>; industries: Record<string, CodedPoolRow>;
    prerequisites: Record<string, PoolRow>; supplements: Record<string, PoolRow>;
  };
  source_tasks: Record<string, SourceTask>;
  meta?: DegradeMeta;
}

