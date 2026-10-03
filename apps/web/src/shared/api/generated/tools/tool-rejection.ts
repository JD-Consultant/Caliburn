/* Generated from apps/api/contracts; do not edit. */

/**
 * A confirmed refusal, not an unknown save outcome or an empty successful read. No raw exception, scope, credential or stack trace is exposed.
 */
export interface ToolRejection {
  status: 'rejected';
  code: string;
  message: string;
  next_action: string;
}
