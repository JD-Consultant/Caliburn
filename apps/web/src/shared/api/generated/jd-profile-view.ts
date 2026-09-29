/* Generated from apps/api/contracts; do not edit. */

/**
 * The four editable JD profile fields at one fixed revision. Null means no value has been supplied, not a confirmed absence.
 */
export interface JdProfileView {
  revision_id: string;
  profile: Profile;
}
export interface Profile {
  job_title: string | null;
  organization_unit: string | null;
  reports_to: string | null;
  purpose: string | null;
}
