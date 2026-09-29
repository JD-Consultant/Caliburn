/* Generated from apps/api/contracts; do not edit. */

/**
 * Rename only the label at the observed name_revision. Reuse the same command and payload to recover its original result.
 */
export interface RenameJobFileRequest {
  command_id: string;
  expected_name_revision: number;
  display_name: string;
}
