/* Generated from docs/specs/contracts/jd-editor-v2.schema.json. Do not edit. */

/**
 * App- or existing-source-owner-issued opaque reference. Its encoding is not a model contract.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "OpaqueRef".
 */
export type OpaqueRef = string;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "Sha256".
 */
export type Sha256 = string;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSourceRefs".
 */
export type JdSourceRefs = OpaqueRef[];
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSectionKind".
 */
export type JdSectionKind = "identity" | "purpose" | "work" | "knowledge" | "skills" | "conditions" | "other";
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdElementType".
 */
export type JdElementType =
  | "p"
  | "h1"
  | "h2"
  | "h3"
  | "blockquote"
  | "ul"
  | "ol"
  | "li"
  | "lic"
  | "table"
  | "tr"
  | "td"
  | "th"
  | "hr"
  | "jd_section"
  | "jd_duty"
  | "jd_task"
  | "jd_outcomes"
  | "jd_requirements"
  | "jd_knowledge"
  | "jd_skill";
/**
 * Saved clean element. The fixed profile validator additionally enforces the exact parent/child grammar and type-specific property placement.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedElement".
 */
export type JdSavedElement = {
  [k: string]: unknown;
} & {
  type: JdElementType;
  id: string;
  /**
   * @minItems 1
   */
  children: [JdText | JdSavedElement, ...(JdText | JdSavedElement)[]];
  source_refs?: JdSourceRefs;
  section_kind?: JdSectionKind;
  colSizes?: number[];
  marginLeft?: number;
  size?: number;
  colSpan?: number;
  rowSpan?: number;
  background?: string;
  borders?: JdBorders;
  attributes?: JdCellAttributes;
  knowledge_ids?: JdItemIds;
  skill_ids?: JdItemIds;
};
/**
 * Ordered same-revision semantic item IDs. The App verifies unique whole-document IDs, endpoint kind and existence; no current/history fallback.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdItemIds".
 */
export type JdItemIds = string[];
/**
 * New content has no Element IDs or semantic link fields. Create items first, confirm saving, reread the current base, then link saved Tasks with set_properties. Use empty paragraphs for unknown group content, never invented facts.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewElement".
 */
export type JdNewElement = {
  [k: string]: unknown;
} & {
  type: JdElementType;
  /**
   * @minItems 1
   */
  children: [JdText | JdNewElement, ...(JdText | JdNewElement)[]];
  source_refs?: JdSourceRefs;
  section_kind?: JdSectionKind;
  colSizes?: number[];
  marginLeft?: number;
  size?: number;
  colSpan?: number;
  rowSpan?: number;
  background?: string;
  borders?: JdBorders;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedBodyElement".
 */
export type JdSavedBodyElement = JdSavedElement & JdSavedElementOfBodyType;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedBlockquoteChild".
 */
export type JdSavedBlockquoteChild = JdSavedElement & {
  type: "p" | "h1" | "h2" | "h3" | "ul" | "ol" | "table" | "hr";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedList".
 */
export type JdSavedList = JdSavedElement & {
  type: "ul" | "ol";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedListItem".
 */
export type JdSavedListItem = JdSavedElement & {
  type: "li";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedListContent".
 */
export type JdSavedListContent = JdSavedElement & {
  type: "lic";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedTableRow".
 */
export type JdSavedTableRow = JdSavedElement & {
  type: "tr";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedTableCell".
 */
export type JdSavedTableCell = JdSavedElement & {
  type: "td" | "th";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedCellChild".
 */
export type JdSavedCellChild = JdSavedElement & {
  type: "p" | "ul" | "ol";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedDutyChild".
 */
export type JdSavedDutyChild = JdSavedElement & {
  type: "p" | "h1" | "h2" | "h3" | "blockquote" | "ul" | "ol" | "table" | "hr" | "jd_task";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedWorkSectionChild".
 */
export type JdSavedWorkSectionChild = JdSavedElement & {
  type: "p" | "h1" | "h2" | "h3" | "blockquote" | "ul" | "ol" | "table" | "hr" | "jd_duty" | "jd_task";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewBodyElement".
 */
export type JdNewBodyElement = JdNewElement & {
  type: "p" | "h1" | "h2" | "h3" | "blockquote" | "ul" | "ol" | "table" | "hr";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewBlockquoteChild".
 */
export type JdNewBlockquoteChild = JdNewElement & {
  type: "p" | "h1" | "h2" | "h3" | "ul" | "ol" | "table" | "hr";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewList".
 */
export type JdNewList = JdNewElement & {
  type: "ul" | "ol";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewListItem".
 */
export type JdNewListItem = JdNewElement & {
  type: "li";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewListContent".
 */
export type JdNewListContent = JdNewElement & {
  type: "lic";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewTableRow".
 */
export type JdNewTableRow = JdNewElement & {
  type: "tr";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewTableCell".
 */
export type JdNewTableCell = JdNewElement & {
  type: "td" | "th";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewCellChild".
 */
export type JdNewCellChild = JdNewElement & {
  type: "p" | "ul" | "ol";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewDutyChild".
 */
export type JdNewDutyChild = JdNewElement & {
  type: "p" | "h1" | "h2" | "h3" | "blockquote" | "ul" | "ol" | "table" | "hr" | "jd_task";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewWorkSectionChild".
 */
export type JdNewWorkSectionChild = JdNewElement & {
  type: "p" | "h1" | "h2" | "h3" | "blockquote" | "ul" | "ol" | "table" | "hr" | "jd_duty" | "jd_task";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdRootSavedElement".
 */
export type JdRootSavedElement = JdSavedElement & {
  type?: "p" | "h1" | "h2" | "h3" | "blockquote" | "ul" | "ol" | "table" | "hr" | "jd_section";
  [k: string]: unknown;
};
/**
 * Authoritative clean Plate value. Exact nested grammar, unique IDs, hr shape, list lic shape, table grid, and type-specific properties are also checked by jd-plate-clean-v2.
 *
 * @minItems 1
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdDocumentValue".
 */
export type JdDocumentValue = [JdRootSavedElement, ...JdRootSavedElement[]];
/**
 * Read the active JD before planning edits. Use {} for the current saved document and current-base targets, or exactly one issued revision_ref, target_ref, selection_ref or continuation_ref to read a fixed scope. Explicit revision reads are read-only even if that revision happens to be current. Read all relevant pages before changing a whole scope. The App supplies paths and positions; never calculate line numbers or offsets. A failure or unread page does not mean content is absent. read_failed/stop requires App recovery, not repeated model calls. Task targets include knowledge_refs/skill_refs; knowledge/skill targets include used_by_task_refs computed by the App. Read complete affected items/Tasks before changing shared meaning, following issued target refs and pagination. IDs inside saved fragments are not edit refs. Whole-document current/history reads expose the change that created the returned revision. To inspect earlier saved events, use its issued change_ref with jd_change_read, then read the returned before_revision_ref; stop at the stated baseline. Reading navigation references alone does not read the document content.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdReadModelInput".
 */
export type JdReadModelInput =
  | {}
  | {
      revision_ref: OpaqueRef;
    }
  | {
      target_ref: OpaqueRef;
    }
  | {
      selection_ref: OpaqueRef;
    }
  | {
      continuation_ref: OpaqueRef;
    };
/**
 * Ordered App-issued target references from the exact read revision. They are capabilities, not saved item IDs. App checks document/base, access and endpoint kind.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdItemRefs".
 */
export type JdItemRefs = OpaqueRef[];
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdUnsettableProperty".
 */
export type JdUnsettableProperty =
  | "source_refs"
  | "colSizes"
  | "marginLeft"
  | "size"
  | "colSpan"
  | "rowSpan"
  | "background"
  | "borders"
  | "knowledge_refs"
  | "skill_refs";
/**
 * Replace specified properties and/or remove named properties on one issued target. The sets must be disjoint. Preserve omitted fields. source_refs is a complete attachment list; [] or unset clears it. Cell spans use numeric values; the App handles saved HTML fallback attributes. Task knowledge_refs/skill_refs replace complete ordered relations; [] or unset clears them. App resolves endpoint kind, access and scope, then maps both set and unset to saved IDs. Never enter raw or temporary IDs.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSetPropertiesCommand".
 */
export type JdSetPropertiesCommand = JdPropertyUpdateConstraint &
  JdSetPropertiesCommand1 & {
    type: "set_properties";
    /**
     * App- or existing-source-owner-issued opaque reference. Its encoding is not a model contract.
     */
    target_ref: string;
    set?: JdEditableProperties;
    /**
     * @minItems 1
     */
    unset?: [JdUnsettableProperty, ...JdUnsettableProperty[]];
  };
/**
 * A property cannot be set and unset in one command. The App must also enforce this finite invariant before native transforms.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdPropertyUpdateConstraint".
 */
export type JdPropertyUpdateConstraint = {
  [k: string]: unknown;
};
export type JdSetPropertiesCommand1 = {
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdEditCommand".
 */
export type JdEditCommand =
  | JdInsertContentCommand
  | JdReplaceBlockContentCommand
  | JdReplaceSelectionCommand
  | JdSetPropertiesCommand
  | JdMoveContentCommand
  | JdUnwrapGroupCommand
  | JdRemoveContentCommand;
/**
 * Read actual saved changes using one issued change_ref, a same-document before_revision_ref and after_revision_ref pair, or the issued continuation_ref for that comparison. Before/after snapshots are authoritative; limited highlighting is not proof that nothing else changed. This tool cannot edit, accept, reject or restore a revision. On a read failure do not infer missing content or loop; follow the returned recovery action.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdChangeReadModelInput".
 */
export type JdChangeReadModelInput =
  | {
      change_ref: OpaqueRef;
    }
  | {
      before_revision_ref: OpaqueRef;
      after_revision_ref: OpaqueRef;
    }
  | {
      continuation_ref: OpaqueRef;
    };
/**
 * Python-resolved command for the fixed local Node adapter. Opaque model references are absent.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdResolvedEditCommand".
 */
export type JdResolvedEditCommand =
  | {
      type: "insert_content";
      target_id: string;
      placement: "before" | "after" | "prepend_child" | "append_child";
      /**
       * @minItems 1
       */
      content: [JdNewElement, ...JdNewElement[]];
    }
  | {
      type: "replace_block_content";
      target_id: string;
      /**
       * @minItems 1
       */
      content: [JdText, ...JdText[]];
    }
  | {
      type: "replace_selection";
      target_id: string;
      range: SlateRange;
      content: JdText[];
    }
  | JdResolvedPropertyUpdateConstraint
  | {
      type: "move_content";
      target_id: string;
      destination_id: string;
      placement: "before" | "after" | "prepend_child" | "append_child";
    }
  | {
      type: "unwrap_group";
      target_id: string;
    }
  | {
      type: "remove_content";
      target_id: string;
    };
/**
 * A property cannot be set and unset in one command. The App must also enforce this finite invariant before native transforms.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdResolvedPropertyUpdateConstraint".
 */
export type JdResolvedPropertyUpdateConstraint = {
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JsonValue".
 */
export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | {
      [k: string]: JsonValue;
    };
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdPlateTransformResult".
 */
export type JdPlateTransformResult = JdPlateTransformSuccess | JdPlateTransformFailure;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdPlateValidateValueResult".
 */
export type JdPlateValidateValueResult = JdPlateTransformSuccess | JdPlateTransformFailure;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdPlateReadSelectionResult".
 */
export type JdPlateReadSelectionResult = JdPlateReadSelectionSuccess | JdPlateTransformFailure;
/**
 * Element and its issued reference from one immutable read base. Task link refs and knowledge/skill incoming Task refs are derived from the full revision, including targets whose body is on another page. Read those targets before changing meaning; issuing a ref does not mean its body was read. All derived history refs remain read-only. Incoming Tasks follow document order.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdReadTarget".
 */
export type JdReadTarget = {
  [k: string]: unknown;
} & {
  target_ref: OpaqueRef;
  element: JdSavedElement;
  access: "current_base" | "read_only";
  knowledge_refs?: JdItemRefs;
  skill_refs?: JdItemRefs;
  used_by_task_refs?: JdItemRefs;
};
/**
 * Read-only failure. read_failed means infrastructure or decoding failed; the App stops and exposes a recovery path. No JD operation is created and no absent-content inference is valid.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdReadFailure".
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdChangeReadFailure".
 */
export type JdChangeReadFailure = {
  [k: string]: unknown;
} & {
  status: "invalid_input" | "unsupported_content" | "target_missing" | "busy" | "read_failed";
  document_effect: "unchanged";
  receipt_durability: "unconfirmed";
  error: JdToolErrorDetail;
  next_action: "correct_arguments" | "reread_current" | "wait" | "stop";
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdReadResult".
 */
export type JdReadResult = JdReadSuccess | JdChangeReadFailure;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdWriteStatus".
 */
export type JdWriteStatus =
  | "committed"
  | "no_change"
  | "invalid_input"
  | "unsupported_content"
  | "target_missing"
  | "stale_base"
  | "engine_failed"
  | "save_failed"
  | "outcome_unknown"
  | "operation_conflict"
  | "busy";
/**
 * Actual App-produced save result shared by AI and manual saving. Bound operations with an unconfirmed receipt require App reconciliation even when the current payload is known unchanged. The action on an immutable receipt is not rewritten when a later retry exhausts its runtime budget. wait/reconcile/stop are App control actions, not new model tools.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdWriteResult".
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdEditResult".
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdManualSaveResult".
 */
export type JdWriteResult = {
  [k: string]: unknown;
} & {
  status: JdWriteStatus;
  operation_ref: OpaqueRef | null;
  base_revision_ref: OpaqueRef | null;
  result_revision_ref: OpaqueRef | null;
  change_ref: OpaqueRef | null;
  document_effect: "unchanged" | "committed" | "unknown";
  receipt_durability: "confirmed" | "unconfirmed";
  actual_changes: JdActualChanges | null;
  error: JdToolErrorDetail | null;
  next_action: "continue" | "correct_arguments" | "reread_current" | "reconcile_operation" | "wait" | "stop";
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdChangeReadResult".
 */
export type JdChangeReadResult = JdChangeReadSuccess | JdChangeReadFailure;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedOutcomes".
 */
export type JdSavedOutcomes = JdSavedElement & {
  type: "jd_outcomes";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedRequirements".
 */
export type JdSavedRequirements = JdSavedElement & {
  type: "jd_requirements";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedKnowledgeItem".
 */
export type JdSavedKnowledgeItem = JdSavedElement & {
  type: "jd_knowledge";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedSkillItem".
 */
export type JdSavedSkillItem = JdSavedElement & {
  type: "jd_skill";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedTaskChild".
 */
export type JdSavedTaskChild = JdSavedBodyElement | JdSavedOutcomes | JdSavedRequirements;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedKnowledgeSectionChild".
 */
export type JdSavedKnowledgeSectionChild = JdSavedBodyElement | JdSavedKnowledgeItem;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedSkillsSectionChild".
 */
export type JdSavedSkillsSectionChild = JdSavedBodyElement | JdSavedSkillItem;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewOutcomes".
 */
export type JdNewOutcomes = JdNewElement & {
  type: "jd_outcomes";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewRequirements".
 */
export type JdNewRequirements = JdNewElement & {
  type: "jd_requirements";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewKnowledgeItem".
 */
export type JdNewKnowledgeItem = JdNewElement & {
  type: "jd_knowledge";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewSkillItem".
 */
export type JdNewSkillItem = JdNewElement & {
  type: "jd_skill";
  [k: string]: unknown;
};
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewTaskChild".
 */
export type JdNewTaskChild = JdNewBodyElement | JdNewOutcomes | JdNewRequirements;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewKnowledgeSectionChild".
 */
export type JdNewKnowledgeSectionChild = JdNewBodyElement | JdNewKnowledgeItem;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdNewSkillsSectionChild".
 */
export type JdNewSkillsSectionChild = JdNewBodyElement | JdNewSkillItem;
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdResolvedUnsettableProperty".
 */
export type JdResolvedUnsettableProperty =
  | "source_refs"
  | "colSizes"
  | "marginLeft"
  | "size"
  | "colSpan"
  | "rowSpan"
  | "background"
  | "borders"
  | "knowledge_ids"
  | "skill_ids";
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdDocumentMetadataCommand".
 */
export type JdDocumentMetadataCommand = JdDocumentRename | JdDocumentSetArchived;

/**
 * Active JD design contract v2: parallel Task outcome/requirement groups and same-revision knowledge/skill references. Frozen v1 remains historical; not a migration or production authority.
 */
export interface JdEditorV2ContractCandidate {}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdEngineProfile".
 */
export interface JdEngineProfile {
  format_version: 2;
  engine_profile: "jd-plate-clean-v2";
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdText".
 */
export interface JdText {
  text: string;
  bold?: true;
  italic?: true;
  underline?: true;
  strikethrough?: true;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdEmptyText".
 */
export interface JdEmptyText {
  text: "";
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdBorder".
 */
export interface JdBorder {
  size?: number;
  color?: string;
  style?: string;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdBorders".
 */
export interface JdBorders {
  top?: JdBorder;
  right?: JdBorder;
  bottom?: JdBorder;
  left?: JdBorder;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdCellAttributes".
 */
export interface JdCellAttributes {
  colspan?: string;
  rowspan?: string;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSavedElementOfBodyType".
 */
export interface JdSavedElementOfBodyType {
  type: "p" | "h1" | "h2" | "h3" | "blockquote" | "ul" | "ol" | "table" | "hr";
  [k: string]: unknown;
}
/**
 * Insert new supported elements at an issued current target. before/after means sibling; prepend_child/append_child means child of a compatible container. Do not supply IDs. Existing content stays intact.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdInsertContentCommand".
 */
export interface JdInsertContentCommand {
  type: "insert_content";
  /**
   * App- or existing-source-owner-issued opaque reference. Its encoding is not a model contract.
   */
  target_ref: string;
  placement: "before" | "after" | "prepend_child" | "append_child";
  /**
   * @minItems 1
   */
  content: [JdNewElement, ...JdNewElement[]];
}
/**
 * Replace only the text/marks inside one fully read p, h1, h2, h3 or lic block. Preserve the outer identity and attachments. To change sources, add explicit set_properties in the same batch; do not replace a whole task to rename its heading.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdReplaceBlockContentCommand".
 */
export interface JdReplaceBlockContentCommand {
  type: "replace_block_content";
  /**
   * App- or existing-source-owner-issued opaque reference. Its encoding is not a model contract.
   */
  target_ref: string;
  /**
   * @minItems 1
   */
  content: [JdText, ...JdText[]];
}
/**
 * Replace the exact App-issued UI selection inside one supported text block. Empty content deletes the selection. Never calculate offsets or search for the first matching string. Attachments remain unless explicitly changed.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdReplaceSelectionCommand".
 */
export interface JdReplaceSelectionCommand {
  type: "replace_selection";
  selection_ref: OpaqueRef;
  content: JdText[];
}
/**
 * Explicit property replacements only. Omitted properties remain unchanged. source_refs replaces the whole attachment list and is not an automatic verification claim. Numeric cell spans are intent, not grid merge/split commands. knowledge_refs/skill_refs apply only to a saved Task and replace the complete ordered link set. [] or unset clears; omission preserves. Copy issued refs after reading the relevant current-base items.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdEditableProperties".
 */
export interface JdEditableProperties {
  source_refs?: JdSourceRefs;
  section_kind?: JdSectionKind;
  colSizes?: number[];
  marginLeft?: number;
  size?: number;
  colSpan?: number;
  rowSpan?: number;
  background?: string;
  borders?: JdBorders;
  knowledge_refs?: JdItemRefs;
  skill_refs?: JdItemRefs;
}
/**
 * Move the entire existing subtree to a compatible issued destination, preserving IDs, content and source attachments. Do not recreate it with insert/delete. All targets must share the current base.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdMoveContentCommand".
 */
export interface JdMoveContentCommand {
  type: "move_content";
  /**
   * App- or existing-source-owner-issued opaque reference. Its encoding is not a model contract.
   */
  target_ref: string;
  /**
   * App- or existing-source-owner-issued opaque reference. Its encoding is not a model contract.
   */
  destination_ref: string;
  placement: "before" | "after" | "prepend_child" | "append_child";
}
/**
 * Remove a jd_section, jd_duty or jd_task container while keeping its existing children and their IDs/content/attachments. Sources attached only to the removed wrapper remain in history; do not automatically assign them to every child. Explicitly reattach a relevant source to a surviving issued child when needed.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdUnwrapGroupCommand".
 */
export interface JdUnwrapGroupCommand {
  type: "unwrap_group";
  /**
   * App- or existing-source-owner-issued opaque reference. Its encoding is not a model contract.
   */
  target_ref: string;
}
/**
 * Delete only the explicit target subtree. Its previous content and source attachments remain in history. Read the whole affected scope first; do not delete unrelated work during a correction.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdRemoveContentCommand".
 */
export interface JdRemoveContentCommand {
  type: "remove_content";
  /**
   * App- or existing-source-owner-issued opaque reference. Its encoding is not a model contract.
   */
  target_ref: string;
}
/**
 * Edit the one active JD only after reading its current saved content with jd_read. Write when the interview provides enough understanding of a task or a substantive correction; a conversation turn need not edit. Submit one meaningful atomic batch of supported commands using only issued current targets/selection. Include source_refs once on new elements or explicit set_properties, never as a top-level list. The App supplies document/base/operation identity, checks references, runs native edits and saves. Trust the returned saved result, not your intended change. For correct_arguments repair a new call; for reread_current read and replan; for wait, reconcile_operation or stop do not issue another write—the App handles recovery. History stays read-only. New Tasks contain separate jd_outcomes and jd_requirements groups (one each, empty paragraph allowed). Knowledge/skill items are standalone typed blocks. First create items without links; after confirmed saving reread the new base, then set Task knowledge_refs/skill_refs. Never invent temporary IDs or reuse previous-base refs. For shared item edits read affected Tasks; for deleting a referenced item explicitly unlink/relink all affected Tasks in the same batch or keep the item.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdEditModelInput".
 */
export interface JdEditModelInput {
  /**
   * @minItems 1
   */
  commands: [JdEditCommand, ...JdEditCommand[]];
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdToolRuntimeContext".
 */
export interface JdToolRuntimeContext {
  document_ref: OpaqueRef;
  run_ref: OpaqueRef;
  tool_call_id: string;
  profile: JdEngineProfile;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdEditRuntimeContext".
 */
export interface JdEditRuntimeContext {
  document_ref: OpaqueRef;
  run_ref: OpaqueRef;
  employee_input_ref: OpaqueRef;
  assistant_message_ref: OpaqueRef;
  tool_call_id: string;
  operation_ref: OpaqueRef;
  request_digest: Sha256;
  base_revision_ref: OpaqueRef;
  profile: JdEngineProfile;
  actor: "ai";
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdReadRuntimeRequest".
 */
export interface JdReadRuntimeRequest {
  context: JdToolRuntimeContext;
  input: JdReadModelInput;
  jd_selection?: JdSelectionCaptureClientInput;
}
/**
 * Browser-only selection captured from Plate after dirty content is saved; never provider-visible model input.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSelectionCaptureClientInput".
 */
export interface JdSelectionCaptureClientInput {
  base_revision_ref: OpaqueRef;
  range: SlateRange;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "SlateRange".
 */
export interface SlateRange {
  anchor: SlatePoint;
  focus: SlatePoint;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "SlatePoint".
 */
export interface SlatePoint {
  /**
   * @minItems 1
   */
  path: [number, ...number[]];
  offset: number;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdEditRuntimeRequest".
 */
export interface JdEditRuntimeRequest {
  context: JdEditRuntimeContext;
  input: JdEditModelInput;
  base_value: JdDocumentValue;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdChangeReadRuntimeRequest".
 */
export interface JdChangeReadRuntimeRequest {
  context: JdToolRuntimeContext;
  input: JdChangeReadModelInput;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdPlateTransformRequest".
 */
export interface JdPlateTransformRequest {
  profile: JdEngineProfile;
  base_value: JdDocumentValue;
  /**
   * @minItems 1
   */
  commands: [JdResolvedEditCommand, ...JdResolvedEditCommand[]];
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JsonObject".
 */
export interface JsonObject {
  [k: string]: JsonValue;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdToolErrorDetail".
 */
export interface JdToolErrorDetail {
  code: string;
  message: string;
  command_index: number | null;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdPlateTransformSuccess".
 */
export interface JdPlateTransformSuccess {
  ok: true;
  changed: boolean;
  value: JdDocumentValue;
  native_operations: JsonObject[];
  affected_element_ids: string[];
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdPlateTransformFailure".
 */
export interface JdPlateTransformFailure {
  ok: false;
  error: JdToolErrorDetail;
}
/**
 * Fixed-profile validation and normalization request for a complete manual value. It is not a fake edit command.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdPlateValidateValueRequest".
 */
export interface JdPlateValidateValueRequest {
  profile: JdEngineProfile;
  value: JdDocumentValue;
}
/**
 * Read-only native selection request over an already validated canonical value.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdPlateReadSelectionRequest".
 */
export interface JdPlateReadSelectionRequest {
  profile: JdEngineProfile;
  value: JdDocumentValue;
  range: SlateRange;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdPlateReadSelectionSuccess".
 */
export interface JdPlateReadSelectionSuccess {
  ok: true;
  target_id: string;
  range: SlateRange;
  fragment: JdSavedElement[];
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdReadSelection".
 */
export interface JdReadSelection {
  selection_ref: OpaqueRef;
  target_ref: OpaqueRef;
  content: JdText[];
  access: "current_base" | "read_only";
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdReadSuccess".
 */
export interface JdReadSuccess {
  status: "ok";
  read_kind: "current" | "history" | "target" | "selection";
  revision_ref: OpaqueRef;
  access: "current_base" | "read_only";
  fragment: (JdText | JdSavedElement)[];
  targets: JdReadTarget[];
  selection: JdReadSelection | null;
  source_refs: JdSourceRefs;
  /**
   * For whole-document current/history reads, contains exactly the committed change that created revision_ref, or an empty array for an initial revision without a creating change. Content continuation pages retain the same reference. This is not a complete list of earlier changes; inspect that change and follow its before_revision_ref to walk older revisions. No-change receipts are not revision-creating changes.
   */
  change_refs: OpaqueRef[];
  continuation_ref: OpaqueRef | null;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdActualChanges".
 */
export interface JdActualChanges {
  origin: "ai" | "manual" | "initial";
  before_revision_ref: OpaqueRef;
  after_revision_ref: OpaqueRef;
  /**
   * JSON-safe Plate operations when actually captured. Manual saves may use null; snapshots remain authoritative.
   */
  native_operations: JsonObject[] | null;
  affected_element_ids: string[];
}
/**
 * Browser manual-save input. The browser creates and retains request_key for the exact payload; route scope, digest, profile, and durable submission identity are server-owned.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdManualSaveClientInput".
 */
export interface JdManualSaveClientInput {
  request_key: string;
  base_revision_ref: OpaqueRef;
  value: JdDocumentValue;
}
/**
 * App-issued manual save envelope. It is not a model tool input and does not carry a tool_call_id.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdManualSaveRequest".
 */
export interface JdManualSaveRequest {
  document_ref: OpaqueRef;
  submission_ref: OpaqueRef;
  request_digest: Sha256;
  base_revision_ref: OpaqueRef;
  profile: JdEngineProfile;
  value: JdDocumentValue;
  origin: "manual";
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdChangeReadSuccess".
 */
export interface JdChangeReadSuccess {
  status: "ok";
  mode: "change" | "revision_comparison";
  change_ref: OpaqueRef | null;
  origin: "ai" | "manual" | "initial" | null;
  before_revision_ref: OpaqueRef;
  after_revision_ref: OpaqueRef;
  before_fragment: (JdText | JdSavedElement)[];
  after_fragment: (JdText | JdSavedElement)[];
  native_operations: JsonObject[] | null;
  source_refs: JdSourceRefs;
  presentation_limitations: string[];
  continuation_ref: OpaqueRef | null;
}
/**
 * App-resolved native property updates. Semantic knowledge_ids/skill_ids apply only to Tasks and contain same-base item IDs. Both set and unset names are translated from model refs; Node receives no opaque semantic target refs. Existing source_refs keep their separate source-owner meaning.
 *
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdResolvedEditableProperties".
 */
export interface JdResolvedEditableProperties {
  source_refs?: JdSourceRefs;
  section_kind?: JdSectionKind;
  colSizes?: number[];
  marginLeft?: number;
  size?: number;
  colSpan?: number;
  rowSpan?: number;
  background?: string;
  borders?: JdBorders;
  knowledge_ids?: JdItemIds;
  skill_ids?: JdItemIds;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdDocumentCreateInput".
 */
export interface JdDocumentCreateInput {
  title: string;
  request_key: string;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdDocumentMetadata".
 */
export interface JdDocumentMetadata {
  id: string;
  title: string;
  created_at: string;
  archived: boolean;
  metadata_version: number;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdDocumentRename".
 */
export interface JdDocumentRename {
  command: "rename";
  title: string;
  expected_metadata_version: number;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdDocumentSetArchived".
 */
export interface JdDocumentSetArchived {
  command: "set_archived";
  archived: boolean;
  expected_metadata_version: number;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdRunLookupMissing".
 */
export interface JdRunLookupMissing {
  found: false;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdRunLookupReceived".
 */
export interface JdRunLookupReceived {
  found: true;
  input_received: boolean;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSourceSegment".
 */
export interface JdSourceSegment {
  message_id: string;
  role: string;
  text: string;
  text_offset: number;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSourceTurn".
 */
export interface JdSourceTurn {
  input_id: string;
  status: string;
  answer_succeeded: boolean;
}
/**
 * This interface was referenced by `JdEditorV2ContractCandidate`'s JSON-Schema
 * via the `definition` "JdSourceReadResult".
 */
export interface JdSourceReadResult {
  reference: string;
  projection: string;
  segments: JdSourceSegment[];
  turns: JdSourceTurn[];
  omitted_content_types: string[];
  next_offset: number | null;
}

export type JdEditResult = JdWriteResult;

export type JdManualSaveResult = JdWriteResult;
