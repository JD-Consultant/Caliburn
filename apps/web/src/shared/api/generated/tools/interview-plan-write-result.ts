/* Generated from apps/api/contracts; do not edit. */

/**
 * Reliable saved candidate text effects; not Turn adoption or analysis completion. The diff describes actual before/after text and is not executable V4A or an echoed request.
 */
export type InterviewPlanWriteResult = InterviewPlanUpdated | InterviewPlanUnchanged;

export interface InterviewPlanUpdated {
  status: 'updated';
  diff: string;
}
export interface InterviewPlanUnchanged {
  status: 'unchanged';
}
