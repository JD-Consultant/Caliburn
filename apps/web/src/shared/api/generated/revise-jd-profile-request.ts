/* Generated from apps/api/contracts; do not edit. */

export type ProfileField = 'job_title' | 'organization_unit' | 'reports_to' | 'purpose';

/**
 * Revise only the specified profile fields from the observed formal JD revision. Reuse the original command and payload when its result is uncertain.
 */
export interface ReviseJdProfileRequest {
  command_id: string;
  expected_revision_id: string;
  /**
   * @minItems 1
   * @maxItems 4
   */
  changes:
    | [SetField | ClearField]
    | [SetField | ClearField, SetField | ClearField]
    | [SetField | ClearField, SetField | ClearField, SetField | ClearField]
    | [SetField | ClearField, SetField | ClearField, SetField | ClearField, SetField | ClearField];
}
export interface SetField {
  action: 'set_field';
  field: ProfileField;
  value: string;
}
export interface ClearField {
  action: 'clear_field';
  field: ProfileField;
}
