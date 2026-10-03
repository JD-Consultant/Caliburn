/* Generated from apps/api/contracts; do not edit. */

export interface JobFileList {
  job_files: JobFile[];
}
/**
 * User-facing metadata; names are labels, job_file_id is the isolation identity.
 */
export interface JobFile {
  job_file_id: string;
  display_name: string;
  /**
   * Opaque freshness counter for the display label, not a JD or Memory revision.
   */
  name_revision: number;
  employee_name: string;
  created_at: string;
}
