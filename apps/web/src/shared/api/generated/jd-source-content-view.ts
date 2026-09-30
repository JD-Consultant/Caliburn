/* Generated from apps/api/contracts; do not edit. */

/**
 * Read-only evidence along a citation's original fixed chain, never arbitrary Memory history or candidates.
 */
export interface JdSourceContentView {
  revision_id: string;
  citation_id: string;
  content: MemoryContent | InterviewContent;
}
export interface MemoryContent {
  kind: 'work_situation' | 'work_understanding';
  title: string;
  description: string;
  body: string;
  references: SourceLink[];
}
export interface SourceLink {
  source_ref: string;
  kind: 'interview' | 'work_situation';
  label: string;
}
export interface InterviewContent {
  kind: 'interview';
  interview_sequence: number;
  speaker: 'app' | 'employee' | 'consultant';
  interview_text: string;
}
