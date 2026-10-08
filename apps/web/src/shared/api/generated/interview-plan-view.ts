/* Generated from apps/api/contracts; do not edit. */

/**
 * The job file's legally adopted consultant plan, read only. Null and deliberate empty text remain distinct; neither indicates interview completion.
 */
export interface InterviewPlanView {
  job_file_id: string;
  plan: string | null;
}
