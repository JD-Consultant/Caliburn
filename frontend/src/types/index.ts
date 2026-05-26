export type Stage =
  | "basic_info"
  | "icap_ref"
  | "interview"
  | "task_extraction"
  | "star"
  | "five_w2h"
  | "indicator"
  | "ksa"
  | "preview";

export interface User {
  id: string;
  email: string;
  name: string;
  company?: string;
  created_at: string;
}

export interface JobProfile {
  id: string;
  user_id: string;
  job_title: string;
  department: string;
  job_summary?: string;
  stage: Stage;
  completion_pct: number;
  graph_state?: GraphState;
  created_at: string;
  updated_at: string;
}

export type EvidenceSourceType =
  | "interview_quote"
  | "star_slot"
  | "five_w2h_field"
  | "icap_reference"
  | "manual_edit";

export type EvidenceKind = "direct" | "structured" | "inferred";

export interface EvidenceRef {
  source_type: EvidenceSourceType;
  evidence_kind?: EvidenceKind;
  source_id?: string;
  source_phase?: string;
  field?: string;
  quote?: string;
  value?: string | string[];
  confidence?: number;
}

export interface OcsDocument {
  version_info: { versions: { status: string; ocs_code: string }[] };
  ocs_profile: {
    ocs_code: string;
    ocs_name: { occupation_name: string };
    job_description: string;
    ocs_level: number;
    category: {
      job_categories: { name: string }[];
      industries: { name: string }[];
    };
  };
  ocs_content: {
    ocu_units: {
      ocu_code: string;
      ocu_name: string;
      tasks: {
        task_codes: { code: string; name: string }[];
        evidence_refs?: EvidenceRef[];
        display_label?: string;
        display_labels?: string[];
        competency_blocks: {
          competency_level: number;
          indicators: {
            code: string;
            text: string;
            evidence_refs?: EvidenceRef[];
            display_label?: string;
            display_labels?: string[];
          }[];
          outputs: {
            code: string;
            name: string;
            display_label?: string;
            display_labels?: string[];
          }[];
          knowledge: {
            code: string;
            name: string;
            source_type?: string;
            icap_ref?: string;
            display_label?: string;
            display_labels?: string[];
          }[];
          skills: {
            code: string;
            name: string;
            source_type?: string;
            icap_ref?: string;
            display_label?: string;
            display_labels?: string[];
          }[];
        }[];
      }[];
    }[];
  };
  ocs_attitude: {
    attitudes: {
      code: string;
      name: string;
      source_type?: string;
      icap_ref?: string;
      display_label?: string;
      display_labels?: string[];
    }[];
  };
}

export interface ReadinessSignal {
  key: string;
  label: string;
  detected: boolean;
  examples: string[];
  weight: number;
  follow_up_question: string;
}

export interface ReadinessDetail {
  score: number;
  ready: boolean;
  signals: ReadinessSignal[];
  missing_signals: ReadinessSignal[];
  detected_signals: ReadinessSignal[];
  suggested_follow_up_question: string | null;
}

export interface GraphState {
  extracted_tasks?: Task[];
  behavior_indicators?: BehaviorIndicator[];
  ksa_items?: KsaItem[];
  icap_candidates?: IcapCandidate[];
  icap_hit?: boolean;
  icap_mode?: IcapMode;
  current_task_index?: number;
  missing_fields?: string[];
  ocs_document?: OcsDocument;
  interview_readiness_detail?: ReadinessDetail;
  [key: string]: unknown;
}

export interface Task {
  task_name: string;
  description?: string;
  category?: string;
  frequency?: string;
  responsibility_type?: string;
  situation?: string;
  purpose?: string;
  stakeholders?: string[];
  tools?: string[];
  outputs?: string[];
  quality_standards?: string;
  star_case?: StarCase;
  behavior_indicator_5w2h?: string;
  behavior_indicator_abcd?: string;
  completeness_pct?: number;
  missing_fields?: string[];
}

export interface StarCase {
  situation?: string;
  task?: string;
  action?: string;
  result?: string;
}

export interface BehaviorIndicator {
  task_name: string;
  task_id?: string;
  indicator_5w2h?: string;
  indicator_abcd?: string;
  quality_score?: number;
  quality_status?: "ok" | "force_accepted";
}

export interface KsaItem {
  ksa_type: "K" | "S" | "A";
  content: string;
  source_type: "icap_official" | "company_defined";
}

export interface IcapCandidate {
  icap_id: string;
  ocs_code: string;
  icap_title: string;
  similarity: number;
  confidence: "high" | "medium" | "low";
  recommendation: "建議參考" | "部分參考" | "低信心";
  match_reason?: string;
}

export type IcapMode = "reference" | "hybrid" | "company_defined";

export interface InterviewMessage {
  id?: string;
  role: "user" | "ai";
  content: string;
  phase?: string;
  created_at?: string;
}
