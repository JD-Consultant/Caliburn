/* Generated from apps/api/contracts; do not edit. */

export type NullableText = string | null;

/**
 * One bounded collaborator edit from the observed formal base. Replay the same command if the result is uncertain.
 */
export interface EditJdCollaboratorsRequest {
  command_id: string;
  expected_revision_id: string;
  change: CreateCollaborator | ReviseCollaborator | DeleteCollaborator | ReorderCollaborator;
}
export interface CreateCollaborator {
  action: 'create_collaborator';
  name: NullableText;
  scope_text: NullableText;
}
export interface ReviseCollaborator {
  action: 'revise_collaborator';
  collaborator_id: string;
  /**
   * @minItems 1
   * @maxItems 2
   */
  changes: [CollaboratorFieldChange] | [CollaboratorFieldChange, CollaboratorFieldChange];
}
export interface CollaboratorFieldChange {
  field: 'name' | 'scope_text';
  value: NullableText;
}
export interface DeleteCollaborator {
  action: 'delete_collaborator';
  collaborator_id: string;
}
export interface ReorderCollaborator {
  action: 'reorder_collaborator';
  collaborator_id: string;
  /**
   * Place before this existing collaborator; null means last. IDs select identity, never position.
   */
  before_collaborator_id: string | null;
}
