/* Generated from apps/api/contracts; do not edit. */

/**
 * Only formal interview messages, ordered within the selected job file. Not execution progress or uncompleted inputs.
 */
export interface InterviewHistory {
  messages: InterviewMessage[];
}
export interface InterviewMessage {
  source_id: string;
  interview_sequence: number;
  speaker: 'app' | 'employee' | 'consultant';
  interview_text: string;
  /**
   * The original consultant Turn for this formal reply, for scoped public commentary lookup. Null for App/employee messages or when no reply association exists. Navigation only; not a source or private context reference.
   */
  execution_id: string | null;
}
