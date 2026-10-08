/* Generated from apps/api/contracts; do not edit. */

/**
 * Complete saved consultant planning text. Null means no plan has been created; an empty string is deliberate empty text. Neither is a failure or interview completion result.
 */
export type InterviewPlan = InterviewPlan1;

export interface InterviewPlan1 {
  plan: string | null;
}
