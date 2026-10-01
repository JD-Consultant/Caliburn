import { A as moveListItemsToList, B as getHighestEmptyList, C as insertTodoListItem, D as removeFirstListItem, E as moveListItems, F as getTodoListItemEntry, H as isListNested, I as getPropsIfTaskList, L as getPropsIfTaskListLiNode, M as isListRoot, N as isAcrossListItems, O as moveListItemUp, P as hasListChild, R as getListRoot, S as moveListItemSublistItemsToListItemSublist, T as insertListItem, V as getListTypes, _ as toggleBulletedList, a as BaseNumberedListPlugin, b as toggleTaskList, c as withNormalizeList, d as normalizeListItem, f as withInsertFragmentList, g as withDeleteBackwardList, h as withDeleteForwardList, i as BaseListPlugin, j as moveListItemDown, k as unwrapList, l as normalizeNestedList, m as withDeleteFragmentList, n as BaseListItemContentPlugin, o as BaseTaskListPlugin, p as withInsertBreakList, r as BaseListItemPlugin, s as withList, t as BaseBulletedListPlugin, u as getDeepInlineChildren, v as toggleList, w as BaseTodoListPlugin, x as removeListItem, y as toggleNumberedList, z as getListItemEntry } from "./BaseListPlugin-n9uuTtLe.js";
import { KEYS, NodeApi, PathApi, createRuleFactory, match } from "platejs";

//#region src/lib/queries/someList.ts
const someList = (editor, type) => getListItemEntry(editor)?.list?.[0].type === type;

//#endregion
//#region src/lib/transforms/indentListItems.ts
const indentListItems = (editor) => {
	moveListItems(editor, { increase: true });
};

//#endregion
//#region src/lib/transforms/moveListSiblingsAfterCursor.ts
const moveListSiblingsAfterCursor = (editor, { at, to }) => {
	const offset = at.at(-1);
	at = PathApi.parent(at);
	const listNode = NodeApi.get(editor, at);
	const listEntry = [listNode, at];
	if (!match(listNode, [], { type: getListTypes(editor) }) || PathApi.isParent(at, to)) return false;
	return editor.tf.moveNodes({
		at: listEntry[1],
		children: true,
		fromIndex: offset + 1,
		to
	});
};

//#endregion
//#region src/lib/transforms/unindentListItems.ts
const unindentListItems = (editor, options = {}) => moveListItems(editor, {
	...options,
	increase: false
});

//#endregion
//#region src/lib/BulletedListRules.ts
const isListInputBlocked$2 = (editor) => editor.api.some({ match: { type: [editor.getType(KEYS.codeBlock)] } });
const BulletedListRules = { markdown: createRuleFactory({
	type: "blockStart",
	variant: "-",
	enabled: ({ editor }) => !isListInputBlocked$2(editor),
	trigger: " ",
	match: ({ variant }) => variant,
	apply: ({ editor }, match$1) => {
		editor.tf.delete({ at: match$1.range });
		toggleList(editor, { type: editor.getType(KEYS.ulClassic) });
		return true;
	}
}) };

//#endregion
//#region src/lib/OrderedListRules.ts
const isListInputBlocked$1 = (editor) => editor.api.some({ match: { type: [editor.getType(KEYS.codeBlock)] } });
const getOrderedListPattern = (variant) => /* @__PURE__ */ new RegExp(`^\\d+\\${variant}$`);
const OrderedListRules = { markdown: createRuleFactory({
	type: "blockStart",
	variant: ".",
	enabled: ({ editor }) => !isListInputBlocked$1(editor),
	trigger: " ",
	match: ({ variant }) => getOrderedListPattern(variant),
	apply: ({ editor }, match$1) => {
		editor.tf.delete({ at: match$1.range });
		toggleList(editor, { type: editor.getType(KEYS.olClassic) });
		return true;
	}
}) };

//#endregion
//#region src/lib/TaskListRules.ts
const isListInputBlocked = (editor) => editor.api.some({ match: { type: [editor.getType(KEYS.codeBlock)] } });
const TaskListRules = { markdown: createRuleFactory({
	type: "blockStart",
	checked: false,
	enabled: ({ editor }) => !isListInputBlocked(editor),
	trigger: " ",
	match: ({ checked }) => checked ? "[x]" : "[]",
	apply: ({ editor, checked }, match$1) => {
		editor.tf.delete({ at: match$1.range });
		toggleTaskList(editor, checked);
		return true;
	}
}) };

//#endregion
export { BaseBulletedListPlugin, BaseListItemContentPlugin, BaseListItemPlugin, BaseListPlugin, BaseNumberedListPlugin, BaseTaskListPlugin, BaseTodoListPlugin, BulletedListRules, OrderedListRules, TaskListRules, getDeepInlineChildren, getHighestEmptyList, getListItemEntry, getListRoot, getListTypes, getPropsIfTaskList, getPropsIfTaskListLiNode, getTodoListItemEntry, hasListChild, indentListItems, insertListItem, insertTodoListItem, isAcrossListItems, isListNested, isListRoot, moveListItemDown, moveListItemSublistItemsToListItemSublist, moveListItemUp, moveListItems, moveListItemsToList, moveListSiblingsAfterCursor, normalizeListItem, normalizeNestedList, removeFirstListItem, removeListItem, someList, toggleBulletedList, toggleList, toggleNumberedList, toggleTaskList, unindentListItems, unwrapList, withDeleteBackwardList, withDeleteForwardList, withDeleteFragmentList, withInsertBreakList, withInsertFragmentList, withList, withNormalizeList };