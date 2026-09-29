/* Generated from apps/api/contracts; do not edit. */

/**
 * One explicit creation command. Transport resends reuse command_id; a new file uses a new command.
 */
export interface CreateJobFileRequest {
  command_id: string;
  display_name: string;
  employee_name: string;
}
