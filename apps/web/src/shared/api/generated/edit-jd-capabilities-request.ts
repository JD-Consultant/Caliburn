/* Generated from apps/api/contracts; do not edit. */

export type CreateCapability = CreateCapability1 & {
  action: 'create_capability';
  kind: 'knowledge' | 'skill';
  name: OptionalText;
  description: OptionalText;
};
export type CreateCapability1 =
  | {
      name?: string;
      [k: string]: unknown;
    }
  | {
      description?: string;
      [k: string]: unknown;
    };
export type OptionalText = string | null;

export interface EditJdCapabilitiesRequest {
  command_id: string;
  expected_revision_id: string;
  change:
    | CreateCapability
    | ReviseCapability
    | DeleteCapability
    | ReorderCapability
    | SetTaskCapability
    | ReorderTaskCapability;
}
export interface ReviseCapability {
  action: 'revise_capability';
  capability_id: string;
  /**
   * @minItems 1
   * @maxItems 2
   */
  changes: [FieldChange] | [FieldChange, FieldChange];
}
export interface FieldChange {
  field: 'name' | 'description';
  value: OptionalText;
}
export interface DeleteCapability {
  action: 'delete_capability';
  capability_id: string;
}
export interface ReorderCapability {
  action: 'reorder_capability';
  capability_id: string;
  before_capability_id: string | null;
}
export interface SetTaskCapability {
  action: 'set_task_capability';
  task_id: string;
  capability_id: string;
  linked: boolean;
}
export interface ReorderTaskCapability {
  action: 'reorder_task_capability';
  task_id: string;
  capability_id: string;
  before_capability_id: string | null;
}
