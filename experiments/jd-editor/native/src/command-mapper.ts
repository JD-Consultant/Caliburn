import type {
  JdResolvedEditCommand,
  JdResolvedEditableProperties,
  JdResolvedUnsettableProperty,
} from "@caliburn/jd-editor-contract";
/** Generator cannot express allOf/not; the original schema validates this mapper input. */
type TypedBranch = Extract<JdResolvedEditCommand, { type: string }>;
export type ResolvedCommand =
  | TypedBranch
  | {
      type: "set_properties";
      target_id: string;
      set?: JdResolvedEditableProperties;
      unset?: JdResolvedUnsettableProperty[];
    };
export function mapCommand(command: JdResolvedEditCommand): ResolvedCommand {
  return command as ResolvedCommand;
}
