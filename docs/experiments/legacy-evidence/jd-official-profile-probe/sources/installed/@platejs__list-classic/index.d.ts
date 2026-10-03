import { n as TTodoListItemElement, t as BaseTodoListPlugin } from "./BaseTodoListPlugin-C3ztdXje";
import * as platejs6 from "platejs";
import { Ancestor, Descendant, EditorNodesOptions, ElementEntry, NodeEntry, OmitFirst, OverrideEditor, Path, PluginConfig, Point, SlateEditor, TElement, TLocation, TRange } from "platejs";

//#region src/lib/transforms/indentListItems.d.ts
declare const indentListItems: (editor: SlateEditor) => void;
//#endregion
//#region src/lib/transforms/insertListItem.d.ts
type InsertListItemOptions = {
  inheritCheckStateOnLineEndBreak?: boolean;
  inheritCheckStateOnLineStartBreak?: boolean;
};
/** Insert list item if selection in li>p. TODO: test */
declare const insertListItem: (editor: SlateEditor, options?: InsertListItemOptions) => boolean;
//#endregion
//#region src/lib/transforms/insertTodoListItem.d.ts
/** Insert todo list item if selection in li>p. TODO: test */
declare const insertTodoListItem: (editor: SlateEditor) => boolean;
//#endregion
//#region src/lib/transforms/moveListItemDown.d.ts
type MoveListItemDownOptions = {
  list: ElementEntry;
  listItem: ElementEntry;
};
declare const moveListItemDown: (editor: SlateEditor, {
  list,
  listItem
}: MoveListItemDownOptions) => false | undefined;
//#endregion
//#region src/lib/transforms/moveListItemSublistItemsToListItemSublist.d.ts
type MoveListItemSublistItemsToListItemSublistOptions = {
  /** The list item to merge. */
  fromListItem: ElementEntry;
  /** The list item where to merge. */
  toListItem: ElementEntry;
  /** Move to the start of the list instead of the end. */
  start?: boolean;
};
/**
 * Move fromListItem sublist list items to the end of `toListItem` sublist. If
 * there is no `toListItem` sublist, insert one.
 */
declare const moveListItemSublistItemsToListItemSublist: (editor: SlateEditor, {
  fromListItem,
  start,
  toListItem
}: MoveListItemSublistItemsToListItemSublistOptions) => boolean;
//#endregion
//#region src/lib/transforms/moveListItemUp.d.ts
type MoveListItemUpOptions = {
  list: ElementEntry;
  listItem: ElementEntry;
};
/** Move a list item up. */
declare const moveListItemUp: (editor: SlateEditor, {
  list,
  listItem
}: MoveListItemUpOptions) => boolean;
//#endregion
//#region src/lib/transforms/moveListItems.d.ts
type MoveListItemsOptions = {
  at?: EditorNodesOptions['at'];
  enableResetOnShiftTab?: boolean;
  increase?: boolean;
};
declare const moveListItems: (editor: SlateEditor, {
  at,
  enableResetOnShiftTab,
  increase
}?: MoveListItemsOptions) => boolean | undefined;
//#endregion
//#region src/lib/transforms/moveListItemsToList.d.ts
type MergeListItemIntoListOptions = {
  /**
   * Delete `fromListItem` sublist if true.
   *
   * @default true
   */
  deleteFromList?: boolean;
  /** List items of the list will be moved. */
  fromList?: ElementEntry;
  /** List items of the sublist of this node will be moved. */
  fromListItem?: ElementEntry;
  fromStartIndex?: number;
  to?: Path;
  /** List items will be moved in this list. */
  toList?: ElementEntry;
  /** List position where to move the list items. */
  toListIndex?: number | null;
};
/**
 * Move the list items of the sublist of `fromListItem` to `toList` (if
 * `fromListItem` is defined). Move the list items of `fromList` to `toList` (if
 * `fromList` is defined).
 */
declare const moveListItemsToList: (editor: SlateEditor, {
  deleteFromList,
  fromList,
  fromListItem,
  fromStartIndex,
  to: _to,
  toList,
  toListIndex
}: MergeListItemIntoListOptions) => boolean;
//#endregion
//#region src/lib/transforms/moveListSiblingsAfterCursor.d.ts
declare const moveListSiblingsAfterCursor: (editor: SlateEditor, {
  at,
  to
}: {
  at: Path;
  to: Path;
}) => boolean | void;
//#endregion
//#region src/lib/transforms/removeFirstListItem.d.ts
/** If list is not nested and if li is not the first child, move li up. */
declare const removeFirstListItem: (editor: SlateEditor, {
  list,
  listItem
}: {
  list: ElementEntry;
  listItem: ElementEntry;
}) => boolean;
//#endregion
//#region src/lib/transforms/removeListItem.d.ts
type RemoveListItemOptions = {
  list: ElementEntry;
  listItem: ElementEntry;
  reverse?: boolean;
};
/** Remove list item and move its sublist to list if any. */
declare const removeListItem: (editor: SlateEditor, {
  list,
  listItem,
  reverse
}: RemoveListItemOptions) => boolean;
//#endregion
//#region src/lib/transforms/toggleList.d.ts
declare const toggleList: (editor: SlateEditor, {
  type
}: {
  type: string;
}) => boolean;
declare const toggleBulletedList: (editor: SlateEditor) => boolean;
declare const toggleTaskList: (editor: SlateEditor, defaultChecked?: boolean) => boolean;
declare const toggleNumberedList: (editor: SlateEditor) => boolean;
//#endregion
//#region src/lib/transforms/unindentListItems.d.ts
type UnindentListItemsOptions = Omit<MoveListItemsOptions, 'increase'>;
declare const unindentListItems: (editor: SlateEditor, options?: UnindentListItemsOptions) => boolean | undefined;
//#endregion
//#region src/lib/transforms/unwrapList.d.ts
declare const unwrapList: (editor: SlateEditor, {
  at
}?: {
  at?: Path;
}) => void;
//#endregion
//#region src/lib/BaseListPlugin.d.ts
type ListConfig = PluginConfig<'listClassic', {
  enableResetOnShiftTab?: boolean;
  /** Inherit the checked state of above node after insert break at the end */
  inheritCheckStateOnLineEndBreak?: boolean;
  /** Inherit the checked state of below node after insert break at the start */
  inheritCheckStateOnLineStartBreak?: boolean;
  /** Valid children types for list items, in addition to p and ul types. */
  validLiChildrenTypes?: string[];
}, {}, {
  toggle: {
    bulletedList: OmitFirst<typeof toggleBulletedList>;
    list: OmitFirst<typeof toggleList>;
    numberedList: OmitFirst<typeof toggleNumberedList>;
    taskList: OmitFirst<typeof toggleTaskList>;
  };
}>;
declare const BaseBulletedListPlugin: platejs6.SlatePlugin<PluginConfig<"ul", {}, {}, Record<"ul", {
  toggle: () => void;
}>, {}>>;
declare const BaseNumberedListPlugin: platejs6.SlatePlugin<PluginConfig<"ol", {}, {}, Record<"ol", {
  toggle: () => void;
}>, {}>>;
declare const BaseTaskListPlugin: platejs6.SlatePlugin<PluginConfig<"taskList", {
  inheritCheckStateOnLineEndBreak: boolean;
  inheritCheckStateOnLineStartBreak: boolean;
}, {}, Record<"taskList", {
  toggle: () => void;
}>, {}>>;
declare const BaseListItemPlugin: platejs6.SlatePlugin<PluginConfig<"li", {}, {}, {}, {}>>;
declare const BaseListItemContentPlugin: platejs6.SlatePlugin<PluginConfig<"lic", {}, {}, {}, {}>>;
/** Enables support for bulleted, numbered and to-do lists. */
declare const BaseListPlugin: platejs6.SlatePlugin<PluginConfig<"listClassic", {
  enableResetOnShiftTab?: boolean;
  /** Inherit the checked state of above node after insert break at the end */
  inheritCheckStateOnLineEndBreak?: boolean;
  /** Inherit the checked state of below node after insert break at the start */
  inheritCheckStateOnLineStartBreak?: boolean;
  /** Valid children types for list items, in addition to p and ul types. */
  validLiChildrenTypes?: string[];
}, {}, {
  toggle: {
    bulletedList: (() => boolean) & (() => boolean);
    list: ((args_0: {
      type: string;
    }) => boolean) & ((args_0: {
      type: string;
    }) => boolean);
    numberedList: (() => boolean) & (() => boolean);
    taskList: ((defaultChecked?: boolean | undefined) => boolean) & ((defaultChecked?: boolean | undefined) => boolean);
  };
}, {}>>;
//#endregion
//#region src/lib/BulletedListRules.d.ts
declare const BulletedListRules: {
  markdown: (options?: {
    variant?: "*" | "-" | undefined;
    enabled?: ((context: platejs6.SelectionInputRuleContext<SlateEditor> | platejs6.InsertTextInputRuleContext<SlateEditor> | platejs6.InsertBreakInputRuleContext<SlateEditor> | platejs6.InsertDataInputRuleContext<SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs6.AnyInputRule<unknown>;
};
//#endregion
//#region src/lib/OrderedListRules.d.ts
declare const OrderedListRules: {
  markdown: (options?: {
    variant?: "." | ")" | undefined;
    enabled?: ((context: platejs6.SelectionInputRuleContext<SlateEditor> | platejs6.InsertTextInputRuleContext<SlateEditor> | platejs6.InsertBreakInputRuleContext<SlateEditor> | platejs6.InsertDataInputRuleContext<SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs6.AnyInputRule<unknown>;
};
//#endregion
//#region src/lib/TaskListRules.d.ts
declare const TaskListRules: {
  markdown: (options?: {
    checked?: boolean | undefined;
    enabled?: ((context: platejs6.SelectionInputRuleContext<SlateEditor> | platejs6.InsertTextInputRuleContext<SlateEditor> | platejs6.InsertBreakInputRuleContext<SlateEditor> | platejs6.InsertDataInputRuleContext<SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs6.AnyInputRule<unknown>;
};
//#endregion
//#region src/lib/withDeleteBackwardList.d.ts
declare const withDeleteBackwardList: OverrideEditor<ListConfig>;
//#endregion
//#region src/lib/withDeleteForwardList.d.ts
declare const withDeleteForwardList: OverrideEditor<ListConfig>;
//#endregion
//#region src/lib/withDeleteFragmentList.d.ts
declare const withDeleteFragmentList: OverrideEditor<ListConfig>;
//#endregion
//#region src/lib/withInsertBreakList.d.ts
declare const withInsertBreakList: OverrideEditor<ListConfig>;
//#endregion
//#region src/lib/withInsertFragmentList.d.ts
declare const withInsertFragmentList: OverrideEditor<ListConfig>;
//#endregion
//#region src/lib/withList.d.ts
declare const withList: OverrideEditor<ListConfig>;
//#endregion
//#region src/lib/withNormalizeList.d.ts
/** Normalize list node to force the ul>li>p+ul structure. */
declare const withNormalizeList: OverrideEditor<ListConfig>;
//#endregion
//#region src/lib/normalizers/normalizeListItem.d.ts
/**
 * Recursively get all the:
 *
 * - Block children
 * - Inline children except those at excludeDepth
 */
declare const getDeepInlineChildren: (editor: SlateEditor, {
  children
}: {
  children: NodeEntry<Descendant>[];
}) => NodeEntry<Descendant>[];
/**
 * If the list item has no child: insert an empty list item container. Else:
 * move the children that are not valid to the list item container.
 */
declare const normalizeListItem: (editor: SlateEditor, {
  listItem,
  validLiChildrenTypes
}: {
  listItem: ElementEntry;
} & ListConfig["options"]) => boolean;
//#endregion
//#region src/lib/normalizers/normalizeNestedList.d.ts
declare const normalizeNestedList: (editor: SlateEditor, {
  nestedListItem
}: {
  nestedListItem: ElementEntry;
}) => boolean | undefined;
//#endregion
//#region src/lib/queries/getHighestEmptyList.d.ts
/**
 * Find the highest end list that can be deleted. Its path should be different
 * to diffListPath. If the highest end list 2+ items, return liPath. Get the
 * parent list until:
 *
 * - The list has less than 2 items.
 * - Its path is not equals to diffListPath.
 */
declare const getHighestEmptyList: (editor: SlateEditor, {
  diffListPath,
  liPath
}: {
  liPath: Path;
  diffListPath?: Path;
}) => Path | undefined;
//#endregion
//#region src/lib/queries/getListItemEntry.d.ts
/**
 * Returns the nearest li and ul / ol wrapping node entries for a given path
 * (default = selection)
 */
declare const getListItemEntry: (editor: SlateEditor, {
  at
}?: {
  at?: TLocation | null;
}) => {
  list: ElementEntry;
  listItem: ElementEntry;
} | undefined;
//#endregion
//#region src/lib/queries/getListRoot.d.ts
/** Searches upward for the root list element */
declare const getListRoot: (editor: SlateEditor, at?: Path | Point | TRange | null) => ElementEntry | undefined;
//#endregion
//#region src/lib/queries/getListTypes.d.ts
declare const getListTypes: (editor: SlateEditor) => string[];
//#endregion
//#region src/lib/queries/getTaskListProps.d.ts
type GetPropsIfTaskListLiNodeOptions = {
  liNode: TElement;
  inherit?: boolean;
};
declare const getPropsIfTaskListLiNode: (editor: SlateEditor, {
  inherit,
  liNode: node
}: GetPropsIfTaskListLiNodeOptions) => {
  checked: boolean;
} | undefined;
declare const getPropsIfTaskList: (editor: SlateEditor, type: string, partial?: {
  checked?: boolean;
}) => {
  checked: boolean;
} | undefined;
//#endregion
//#region src/lib/queries/getTodoListItemEntry.d.ts
/**
 * Returns the nearest li and ul / ol wrapping node entries for a given path
 * (default = selection)
 */
declare const getTodoListItemEntry: (editor: SlateEditor, {
  at
}?: {
  at?: TLocation | null;
}) => {
  list: ElementEntry;
  listItem: ElementEntry;
} | undefined;
//#endregion
//#region src/lib/queries/hasListChild.d.ts
/** Is there a list child in the node. */
declare const hasListChild: (editor: SlateEditor, node: Ancestor) => boolean;
//#endregion
//#region src/lib/queries/isAcrossListItems.d.ts
/** Is selection across blocks with list items */
declare const isAcrossListItems: (editor: SlateEditor, at?: TRange | null) => boolean;
//#endregion
//#region src/lib/queries/isListNested.d.ts
/** Is the list nested, i.e. its parent is a list item. */
declare const isListNested: (editor: SlateEditor, listPath: Path) => boolean;
//#endregion
//#region src/lib/queries/isListRoot.d.ts
declare const isListRoot: (editor: SlateEditor, node: Descendant) => boolean;
//#endregion
//#region src/lib/queries/someList.d.ts
declare const someList: (editor: SlateEditor, type: string) => boolean;
//#endregion
export { BaseBulletedListPlugin, BaseListItemContentPlugin, BaseListItemPlugin, BaseListPlugin, BaseNumberedListPlugin, BaseTaskListPlugin, BaseTodoListPlugin, BulletedListRules, GetPropsIfTaskListLiNodeOptions, InsertListItemOptions, ListConfig, MergeListItemIntoListOptions, MoveListItemDownOptions, MoveListItemSublistItemsToListItemSublistOptions, MoveListItemUpOptions, MoveListItemsOptions, OrderedListRules, RemoveListItemOptions, TTodoListItemElement, TaskListRules, UnindentListItemsOptions, getDeepInlineChildren, getHighestEmptyList, getListItemEntry, getListRoot, getListTypes, getPropsIfTaskList, getPropsIfTaskListLiNode, getTodoListItemEntry, hasListChild, indentListItems, insertListItem, insertTodoListItem, isAcrossListItems, isListNested, isListRoot, moveListItemDown, moveListItemSublistItemsToListItemSublist, moveListItemUp, moveListItems, moveListItemsToList, moveListSiblingsAfterCursor, normalizeListItem, normalizeNestedList, removeFirstListItem, removeListItem, someList, toggleBulletedList, toggleList, toggleNumberedList, toggleTaskList, unindentListItems, unwrapList, withDeleteBackwardList, withDeleteForwardList, withDeleteFragmentList, withInsertBreakList, withInsertFragmentList, withList, withNormalizeList };