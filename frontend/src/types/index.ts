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

export interface JobProfile {
  id: string;
  user_id: string;
  job_title: string;
  department?: string | null;
  job_summary?: string | null;
  created_at: string;
  updated_at: string;
}
