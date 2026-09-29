/* Generated from apps/api/contracts; do not edit. */

/**
 * Ordered collaborators in one fixed formal JD revision; tasks are not expanded here.
 */
export interface JdCollaboratorsView {
  revision_id: string;
  collaborators: Collaborator[];
}
export interface Collaborator {
  collaborator_id: string;
  name: string | null;
  scope_text: string | null;
}
