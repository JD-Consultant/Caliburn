import { ElementApi, KEYS, NodeApi, PathApi, RangeApi, bindFirst, createSlatePlugin, createTSlatePlugin, deleteMerge, match } from "platejs";

//#region src/lib/queries/isListNested.ts
/** Is the list nested, i.e. its parent is a list item. */
const isListNested = (editor, listPath) => {
	return (editor.api.parent(listPath)?.[0])?.type === editor.getType(KEYS.li);
};

//#endregion
//#region src/lib/queries/getListTypes.ts
const getListTypes = (editor) => [
	editor.getType(KEYS.olClassic),
	editor.getType(KEYS.ulClassic),
	editor.getType(KEYS.taskList)
];

//#endregion
//#region src/lib/queries/getHighestEmptyList.ts
/**
* Find the highest end list that can be deleted. Its path should be different
* to diffListPath. If the highest end list 2+ items, return liPath. Get the
* parent list until:
*
* - The list has less than 2 items.
* - Its path is not equals to diffListPath.
*/
const getHighestEmptyList = (editor, { diffListPath, liPath }) => {
	const list = editor.api.above({
		at: liPath,
		match: { type: getListTypes(editor) }
	});
	if (!list) return;
	const [listNode, listPath] = list;
	if (!diffListPath || !PathApi.equals(listPath, diffListPath)) {
		if (listNode.children.length < 2) {
			const liParent = editor.api.above({
				at: listPath,
				match: { type: editor.getType(KEYS.li) }
			});
			if (liParent) return getHighestEmptyList(editor, {
				diffListPath,
				liPath: liParent[1]
			}) || listPath;
		}
		return liPath;
	}
};

//#endregion
//#region src/lib/queries/getListItemEntry.ts
/**
* Returns the nearest li and ul / ol wrapping node entries for a given path
* (default = selection)
*/
const getListItemEntry = (editor, { at = editor.selection } = {}) => {
	const liType = editor.getType(KEYS.li);
	let _at;
	if (RangeApi.isRange(at) && !RangeApi.isCollapsed(at)) _at = at.focus.path;
	else if (RangeApi.isRange(at)) _at = at.anchor.path;
	else _at = at;
	if (_at) {
		if (NodeApi.get(editor, _at)) {
			const listItem = editor.api.above({
				at: _at,
				match: { type: liType }
			});
			if (listItem) return {
				list: editor.api.parent(listItem[1]),
				listItem
			};
		}
	}
};

//#endregion
//#region src/lib/queries/getListRoot.ts
/** Searches upward for the root list element */
const getListRoot = (editor, at = editor.selection) => {
	if (!at) return;
	const parentList = editor.api.above({
		at,
		match: { type: getListTypes(editor) }
	});
	if (parentList) {
		const [, parentListPath] = parentList;
		return getListRoot(editor, parentListPath) ?? parentList;
	}
};

//#endregion
//#region src/lib/queries/getTaskListProps.ts
const getPropsIfTaskListLiNode = (editor, { inherit = false, liNode: node }) => editor.getType(KEYS.li) === node.type && "checked" in node ? { checked: inherit ? node.checked : false } : void 0;
const getPropsIfTaskList = (editor, type, partial = {}) => editor.getType(KEYS.taskList) === type ? {
	checked: false,
	...partial
} : void 0;

//#endregion
//#region src/lib/queries/getTodoListItemEntry.ts
/**
* Returns the nearest li and ul / ol wrapping node entries for a given path
* (default = selection)
*/
const getTodoListItemEntry = (editor, { at = editor.selection } = {}) => {
	const todoType = editor.getType(KEYS.listTodoClassic);
	let _at;
	if (RangeApi.isRange(at) && !RangeApi.isCollapsed(at)) _at = at.focus.path;
	else if (RangeApi.isRange(at)) _at = at.anchor.path;
	else _at = at;
	if (_at) {
		if (NodeApi.get(editor, _at)) {
			const listItem = editor.api.above({
				at: _at,
				match: { type: todoType }
			});
			if (listItem) return {
				list: editor.api.parent(listItem[1]),
				listItem
			};
		}
	}
};

//#endregion
//#region src/lib/queries/hasListChild.ts
/** Is there a list child in the node. */
const hasListChild = (editor, node) => node.children.some((n) => match(n, [], { type: getListTypes(editor) }));

//#endregion
//#region src/lib/queries/isAcrossListItems.ts
/** Is selection across blocks with list items */
const isAcrossListItems = (editor, at = editor.selection) => {
	if (!at || RangeApi.isCollapsed(at)) return false;
	if (!editor.api.isAt({
		at,
		blocks: true
	})) return false;
	return editor.api.some({
		at,
		match: { type: editor.getType(KEYS.li) }
	});
};

//#endregion
//#region src/lib/queries/isListRoot.ts
const isListRoot = (editor, node) => ElementApi.isElement(node) && getListTypes(editor).includes(node.type);

//#endregion
//#region src/lib/transforms/moveListItemDown.ts
const moveListItemDown = (editor, { list, listItem }) => {
	let moved = false;
	const [listNode] = list;
	const [, listItemPath] = listItem;
	const previousListItemPath = PathApi.previous(listItemPath);
	if (!previousListItemPath) return;
	const previousSiblingItem = editor.api.node(previousListItemPath);
	if (previousSiblingItem) {
		const [previousNode, previousPath] = previousSiblingItem;
		const sublist = previousNode.children.find((n) => match(n, [], { type: getListTypes(editor) }));
		const newPath = previousPath.concat(sublist ? [1, sublist.children.length] : [1]);
		editor.tf.withoutNormalizing(() => {
			if (!sublist) editor.tf.wrapNodes({
				children: [],
				type: listNode.type
			}, { at: listItemPath });
			editor.tf.moveNodes({
				at: listItemPath,
				to: newPath
			});
			moved = true;
		});
	}
	return moved;
};

//#endregion
//#region src/lib/transforms/moveListItemsToList.ts
/**
* Move the list items of the sublist of `fromListItem` to `toList` (if
* `fromListItem` is defined). Move the list items of `fromList` to `toList` (if
* `fromList` is defined).
*/
const moveListItemsToList = (editor, { deleteFromList = true, fromList, fromListItem, fromStartIndex, to: _to, toList, toListIndex = null }) => {
	let fromListPath;
	let moved = false;
	editor.tf.withoutNormalizing(() => {
		if (fromListItem) {
			const fromListItemSublist = editor.api.descendant({
				at: fromListItem[1],
				match: { type: getListTypes(editor) }
			});
			if (!fromListItemSublist) return;
			fromListPath = fromListItemSublist?.[1];
		} else if (fromList) fromListPath = fromList[1];
		else return;
		let to = null;
		if (_to) to = _to;
		if (toList) if (toListIndex === null) {
			const lastChildPath = NodeApi.lastChild(editor, toList[1])?.[1];
			to = lastChildPath ? PathApi.next(lastChildPath) : toList[1].concat([0]);
		} else to = toList[1].concat([toListIndex]);
		if (!to) return;
		moved = editor.tf.moveNodes({
			at: fromListPath,
			children: true,
			fromIndex: fromStartIndex,
			to
		});
		if (deleteFromList) editor.tf.delete({ at: fromListPath });
	});
	return moved;
};

//#endregion
//#region src/lib/transforms/unwrapList.ts
const unwrapList = (editor, { at } = {}) => {
	const ancestorListTypeCheck = () => {
		if (editor.api.above({
			at,
			match: { type: getListTypes(editor) }
		})) return true;
		if (!at && editor.selection) {
			const commonNode = NodeApi.common(editor, editor.selection.anchor.path, editor.selection.focus.path);
			if (ElementApi.isElement(commonNode[0]) && getListTypes(editor).includes(commonNode[0].type)) return true;
		}
		return false;
	};
	editor.tf.withoutNormalizing(() => {
		do {
			editor.tf.unwrapNodes({
				at,
				match: { type: editor.getType(KEYS.li) },
				split: true
			});
			editor.tf.unwrapNodes({
				at,
				match: { type: getListTypes(editor) },
				split: true
			});
		} while (ancestorListTypeCheck());
	});
};

//#endregion
//#region src/lib/transforms/moveListItemUp.ts
/** Move a list item up. */
const moveListItemUp = (editor, { list, listItem }) => {
	const move = () => {
		const [listNode, listPath] = list;
		const [liNode, liPath] = listItem;
		const liParent = editor.api.above({
			at: listPath,
			match: { type: editor.getType(KEYS.li) }
		});
		if (!liParent) {
			let toListPath$1;
			try {
				toListPath$1 = PathApi.next(listPath);
			} catch (_error) {
				return;
			}
			const condA = hasListChild(editor, liNode);
			const condB = !NodeApi.isLastChild(editor, liPath);
			if (condA || condB) editor.tf.insertNodes({
				children: [],
				type: listNode.type
			}, { at: toListPath$1 });
			if (condA) {
				const toListNode = NodeApi.get(editor, toListPath$1);
				if (!toListNode) return;
				moveListItemsToList(editor, {
					fromListItem: listItem,
					toList: [toListNode, toListPath$1]
				});
			}
			if (condB) {
				const toListNode = NodeApi.get(editor, toListPath$1);
				if (!toListNode) return;
				moveListItemsToList(editor, {
					deleteFromList: false,
					fromList: list,
					fromStartIndex: liPath.at(-1) + 1,
					toList: [toListNode, toListPath$1]
				});
			}
			unwrapList(editor, { at: liPath.concat(0) });
			return true;
		}
		const [, liParentPath] = liParent;
		const toListPath = liPath.concat([1]);
		if (!NodeApi.isLastChild(editor, liPath)) {
			if (!hasListChild(editor, liNode)) editor.tf.insertNodes({
				children: [],
				type: listNode.type
			}, { at: toListPath });
			const toListNode = NodeApi.get(editor, toListPath);
			if (!toListNode) return;
			moveListItemsToList(editor, {
				deleteFromList: false,
				fromListItem: liParent,
				fromStartIndex: liPath.at(-1) + 1,
				toList: [toListNode, toListPath]
			});
		}
		const movedUpLiPath = PathApi.next(liParentPath);
		editor.tf.moveNodes({
			at: liPath,
			to: movedUpLiPath
		});
		return true;
	};
	let moved = false;
	editor.tf.withoutNormalizing(() => {
		moved = move();
	});
	return moved;
};

//#endregion
//#region src/lib/transforms/removeFirstListItem.ts
/** If list is not nested and if li is not the first child, move li up. */
const removeFirstListItem = (editor, { list, listItem }) => {
	const [, listPath] = list;
	if (!isListNested(editor, listPath)) {
		moveListItemUp(editor, {
			list,
			listItem
		});
		return true;
	}
	return false;
};

//#endregion
//#region src/lib/transforms/moveListItems.ts
const moveListItems = (editor, { at = editor.selection ?? void 0, enableResetOnShiftTab, increase = true } = {}) => {
	const _nodes = editor.api.nodes({
		at,
		match: { type: editor.getType(KEYS.lic) }
	});
	const lics = Array.from(_nodes);
	if (lics.length === 0) return;
	const highestLicPaths = [];
	const highestLicPathRefs = [];
	lics.forEach((lic) => {
		const licPath = lic[1];
		const liPath = PathApi.parent(licPath);
		if (!highestLicPaths.some((path) => {
			const highestLiPath = PathApi.parent(path);
			return PathApi.isAncestor(highestLiPath, liPath);
		})) {
			highestLicPaths.push(licPath);
			highestLicPathRefs.push(editor.api.pathRef(licPath));
		}
	});
	const licPathRefsToMove = increase ? highestLicPathRefs : highestLicPathRefs.reverse();
	return editor.tf.withoutNormalizing(() => {
		let moved = false;
		licPathRefsToMove.forEach((licPathRef) => {
			const licPath = licPathRef.unref();
			if (!licPath) return;
			const listItem = editor.api.parent(licPath);
			if (!listItem) return;
			const parentList = editor.api.parent(listItem[1]);
			if (!parentList) return;
			let _moved;
			if (increase) _moved = moveListItemDown(editor, {
				list: parentList,
				listItem
			});
			else if (isListNested(editor, parentList[1])) _moved = moveListItemUp(editor, {
				list: parentList,
				listItem
			});
			else if (enableResetOnShiftTab) _moved = removeFirstListItem(editor, {
				list: parentList,
				listItem
			});
			moved = _moved || moved;
		});
		return moved;
	});
};

//#endregion
//#region src/lib/transforms/insertListItem.ts
/** Insert list item if selection in li>p. TODO: test */
const insertListItem = (editor, options = {}) => {
	const liType = editor.getType(KEYS.li);
	const licType = editor.getType(KEYS.lic);
	if (!editor.selection) return false;
	const licEntry = editor.api.above({ match: { type: licType } });
	if (!licEntry) return false;
	const [, paragraphPath] = licEntry;
	const listItemEntry = editor.api.parent(paragraphPath);
	if (!listItemEntry) return false;
	const [listItemNode, listItemPath] = listItemEntry;
	if (listItemNode.type !== liType) return false;
	const optionalTasklistProps = "checked" in listItemNode ? { checked: false } : void 0;
	let success = false;
	editor.tf.withoutNormalizing(() => {
		if (!editor.api.isCollapsed()) editor.tf.delete();
		const isStart = editor.api.isStart(editor.selection.focus, paragraphPath);
		const isEnd = editor.api.isEmpty(editor.selection, { after: true });
		const nextParagraphPath = PathApi.next(paragraphPath);
		const nextListItemPath = PathApi.next(listItemPath);
		/** If start, insert a list item before */
		if (isStart) {
			if (optionalTasklistProps && options.inheritCheckStateOnLineStartBreak) optionalTasklistProps.checked = listItemNode.checked;
			editor.tf.insertNodes({
				children: [{
					children: [{ text: "" }],
					type: licType
				}],
				...optionalTasklistProps,
				type: liType
			}, { at: listItemPath });
			success = true;
			return;
		}
		/**
		* If not end, split nodes, wrap a list item on the new paragraph and move
		* it to the next list item
		*/
		if (isEnd) {
			/** If end, insert a list item after and select it */
			const marks = editor.api.marks() || {};
			if (optionalTasklistProps && options.inheritCheckStateOnLineEndBreak) optionalTasklistProps.checked = listItemNode.checked;
			editor.tf.insertNodes({
				children: [{
					children: [{
						text: "",
						...marks
					}],
					type: licType
				}],
				...optionalTasklistProps,
				type: liType
			}, { at: nextListItemPath });
			editor.tf.select(nextListItemPath);
		} else editor.tf.withoutNormalizing(() => {
			editor.tf.splitNodes();
			editor.tf.wrapNodes({
				children: [],
				...optionalTasklistProps,
				type: liType
			}, { at: nextParagraphPath });
			editor.tf.moveNodes({
				at: nextParagraphPath,
				to: nextListItemPath
			});
			editor.tf.select(nextListItemPath);
			editor.tf.collapse({ edge: "start" });
		});
		/** If there is a list in the list item, move it to the next list item */
		if (listItemNode.children.length > 1) editor.tf.moveNodes({
			at: nextParagraphPath,
			to: nextListItemPath.concat(1)
		});
		success = true;
	});
	return success;
};

//#endregion
//#region src/lib/BaseTodoListPlugin.ts
const BaseTodoListPlugin = createSlatePlugin({
	key: KEYS.listTodoClassic,
	node: { isElement: true },
	options: {
		inheritCheckStateOnLineEndBreak: false,
		inheritCheckStateOnLineStartBreak: false
	}
}).overrideEditor(({ editor, tf: { insertBreak } }) => ({ transforms: { insertBreak() {
	const insertBreakTodoList = () => {
		if (!editor.selection) return;
		if (getTodoListItemEntry(editor)) {
			if (insertTodoListItem(editor)) return true;
		}
	};
	if (insertBreakTodoList()) return;
	insertBreak();
} } })).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleBlock(type);
} }));

//#endregion
//#region src/lib/transforms/insertTodoListItem.ts
/** Insert todo list item if selection in li>p. TODO: test */
const insertTodoListItem = (editor) => {
	const { inheritCheckStateOnLineEndBreak, inheritCheckStateOnLineStartBreak } = editor.getOptions(BaseTodoListPlugin);
	const todoType = editor.getType(KEYS.listTodoClassic);
	if (!editor.selection) return false;
	const todoEntry = editor.api.above({ match: { type: todoType } });
	if (!todoEntry) return false;
	const [todo, paragraphPath] = todoEntry;
	let success = false;
	editor.tf.withoutNormalizing(() => {
		if (!editor.api.isCollapsed()) editor.tf.delete();
		const isStart = editor.api.isStart(editor.selection.focus, paragraphPath);
		const isEnd = editor.api.isEmpty(editor.selection, { after: true });
		const nextParagraphPath = PathApi.next(paragraphPath);
		/** If start, insert a list item before */
		if (isStart) {
			editor.tf.insertNodes({
				checked: inheritCheckStateOnLineStartBreak ? todo.checked : false,
				children: [{ text: "" }],
				type: todoType
			}, { at: paragraphPath });
			success = true;
			return;
		}
		/** If not end, split the nodes */
		if (isEnd) {
			/** If end, insert a list item after and select it */
			const marks = editor.api.marks() || {};
			editor.tf.insertNodes({
				checked: inheritCheckStateOnLineEndBreak ? todo.checked : false,
				children: [{
					text: "",
					...marks
				}],
				type: todoType
			}, { at: nextParagraphPath });
			editor.tf.select(nextParagraphPath);
		} else editor.tf.withoutNormalizing(() => {
			editor.tf.splitNodes();
		});
		success = true;
	});
	return success;
};

//#endregion
//#region src/lib/transforms/moveListItemSublistItemsToListItemSublist.ts
/**
* Move fromListItem sublist list items to the end of `toListItem` sublist. If
* there is no `toListItem` sublist, insert one.
*/
const moveListItemSublistItemsToListItemSublist = (editor, { fromListItem, start, toListItem }) => {
	const [, fromListItemPath] = fromListItem;
	const [, toListItemPath] = toListItem;
	let moved = false;
	editor.tf.withoutNormalizing(() => {
		const fromListItemSublist = editor.api.descendant({
			at: fromListItemPath,
			match: { type: getListTypes(editor) }
		});
		if (!fromListItemSublist) return;
		const [, fromListItemSublistPath] = fromListItemSublist;
		const toListItemSublist = editor.api.descendant({
			at: toListItemPath,
			match: { type: getListTypes(editor) }
		});
		let to;
		if (!toListItemSublist) {
			const fromList = editor.api.parent(fromListItemPath);
			if (!fromList) return;
			const [fromListNode] = fromList;
			const fromListType = fromListNode.type;
			const toListItemSublistPath = toListItemPath.concat([1]);
			editor.tf.insertNodes({
				children: [],
				type: fromListType
			}, { at: toListItemSublistPath });
			to = toListItemSublistPath.concat([0]);
		} else if (start) {
			const [, toListItemSublistPath] = toListItemSublist;
			to = toListItemSublistPath.concat([0]);
		} else to = PathApi.next(NodeApi.lastChild(editor, toListItemSublist[1])[1]);
		moved = editor.tf.moveNodes({
			at: fromListItemSublistPath,
			children: true,
			to
		});
		editor.tf.delete({ at: fromListItemSublistPath });
	});
	return moved;
};

//#endregion
//#region src/lib/transforms/removeListItem.ts
/** Remove list item and move its sublist to list if any. */
const removeListItem = (editor, { list, listItem, reverse = true }) => {
	const [liNode, liPath] = listItem;
	if (editor.api.isExpanded() || !hasListChild(editor, liNode)) return false;
	const previousLiPath = PathApi.previous(liPath);
	let success = false;
	editor.tf.withoutNormalizing(() => {
		/**
		* If there is a previous li, we need to move sub-lis to the previous li. As
		* we need to delete first, we will:
		*
		* 1. Insert a temporary li: tempLi
		* 2. Move sub-lis to tempLi
		* 3. Delete
		* 4. Move sub-lis from tempLi to the previous li.
		* 5. Remove tempLi
		*/
		if (previousLiPath) {
			const previousLi = editor.api.node(previousLiPath);
			if (!previousLi) return;
			let tempLiPath = PathApi.next(liPath);
			editor.tf.insertNodes({
				children: [{
					children: [{ text: "" }],
					type: editor.getType(KEYS.lic)
				}],
				...getPropsIfTaskListLiNode(editor, {
					inherit: true,
					liNode: previousLi[0]
				}),
				type: editor.getType(KEYS.li)
			}, { at: tempLiPath });
			const tempLi = editor.api.node(tempLiPath);
			if (!tempLi) return;
			const tempLiPathRef = editor.api.pathRef(tempLi[1]);
			moveListItemSublistItemsToListItemSublist(editor, {
				fromListItem: listItem,
				toListItem: tempLi
			});
			deleteMerge(editor, { reverse });
			tempLiPath = tempLiPathRef.unref();
			moveListItemSublistItemsToListItemSublist(editor, {
				fromListItem: [tempLi[0], tempLiPath],
				toListItem: previousLi
			});
			editor.tf.removeNodes({ at: tempLiPath });
			success = true;
			return;
		}
		moveListItemsToList(editor, {
			fromListItem: listItem,
			toList: list,
			toListIndex: 1
		});
	});
	return success;
};

//#endregion
//#region src/lib/transforms/toggleList.ts
const _toggleList = (editor, { checked = false, type }) => editor.tf.withoutNormalizing(() => {
	if (!editor.selection) return;
	const { validLiChildrenTypes } = editor.getOptions(BaseListPlugin);
	if (editor.api.isCollapsed() || !editor.api.isAt({ blocks: true })) {
		const res = getListItemEntry(editor);
		if (res) {
			const { list } = res;
			if (list[0].type === type) unwrapList(editor);
			else editor.tf.setNodes({ type }, {
				at: editor.selection,
				mode: "lowest",
				match: (n) => ElementApi.isElement(n) && getListTypes(editor).includes(n.type)
			});
		} else {
			const list = {
				children: [],
				type
			};
			editor.tf.wrapNodes(list);
			const _nodes = editor.api.nodes({ match: { type: editor.getType(KEYS.p) } });
			const nodes = Array.from(_nodes);
			if (!editor.api.block({ match: { type: validLiChildrenTypes } })) editor.tf.setNodes({ type: editor.getType(KEYS.lic) });
			const listItem = {
				children: [],
				...getPropsIfTaskList(editor, type, { checked }),
				type: editor.getType(KEYS.li)
			};
			for (const [, path] of nodes) editor.tf.wrapNodes(listItem, { at: path });
		}
	} else {
		const [startPoint, endPoint] = RangeApi.edges(editor.selection);
		const commonEntry = NodeApi.common(editor, startPoint.path, endPoint.path);
		if (getListTypes(editor).includes(commonEntry[0].type) || commonEntry[0].type === editor.getType(KEYS.li)) if (commonEntry[0].type === type) unwrapList(editor);
		else {
			const startList = editor.api.node({
				at: RangeApi.start(editor.selection),
				match: { type: getListTypes(editor) },
				mode: "lowest"
			});
			const endList = editor.api.node({
				at: RangeApi.end(editor.selection),
				match: { type: getListTypes(editor) },
				mode: "lowest"
			});
			const rangeLength = Math.min(startList[1].length, endList[1].length);
			editor.tf.setNodes({ type }, {
				at: editor.selection,
				mode: "all",
				match: (n, path) => ElementApi.isElement(n) && getListTypes(editor).includes(n.type) && path.length >= rangeLength
			});
		}
		else {
			const rootPathLength = commonEntry[1].length;
			const _nodes = editor.api.nodes({ mode: "all" });
			Array.from(_nodes).filter(([, path]) => path.length === rootPathLength + 1).forEach((n) => {
				if (getListTypes(editor).includes(n[0].type)) editor.tf.setNodes({ type }, {
					at: n[1],
					mode: "all",
					match: (_n) => ElementApi.isElement(_n) && getListTypes(editor).includes(_n.type)
				});
				else {
					if (!validLiChildrenTypes?.includes(n[0].type)) editor.tf.setNodes({ type: editor.getType(KEYS.lic) }, { at: n[1] });
					const listItem = {
						children: [],
						...getPropsIfTaskList(editor, type, { checked }),
						type: editor.getType(KEYS.li)
					};
					editor.tf.wrapNodes(listItem, { at: n[1] });
					const list = {
						children: [],
						type
					};
					editor.tf.wrapNodes(list, { at: n[1] });
				}
			});
		}
	}
});
const toggleList = (editor, { type }) => _toggleList(editor, { type });
const toggleBulletedList = (editor) => toggleList(editor, { type: editor.getType(KEYS.ulClassic) });
const toggleTaskList = (editor, defaultChecked = false) => _toggleList(editor, {
	checked: defaultChecked,
	type: editor.getType(KEYS.taskList)
});
const toggleNumberedList = (editor) => toggleList(editor, { type: editor.getType(KEYS.olClassic) });

//#endregion
//#region src/lib/withDeleteBackwardList.ts
const withDeleteBackwardList = ({ editor, tf: { deleteBackward } }) => ({ transforms: { deleteBackward(unit) {
	const deleteBackwardList = () => {
		const res = getListItemEntry(editor, {});
		let moved = false;
		if (res) {
			const { list, listItem } = res;
			if (editor.api.isAt({
				start: true,
				match: (node) => node.type === editor.getType(KEYS.li)
			})) editor.tf.withoutNormalizing(() => {
				moved = removeFirstListItem(editor, {
					list,
					listItem
				});
				if (moved) return true;
				moved = removeListItem(editor, {
					list,
					listItem
				});
				if (moved) return true;
				if (!PathApi.hasPrevious(listItem[1]) && !isListNested(editor, list[1])) {
					editor.tf.resetBlock({ at: listItem[1] });
					moved = true;
					return;
				}
				const pointBeforeListItem = editor.api.before(editor.selection.focus);
				let currentLic;
				let hasMultipleChildren = false;
				if (pointBeforeListItem && isAcrossListItems(editor, {
					anchor: editor.selection.anchor,
					focus: pointBeforeListItem
				})) {
					const licType = editor.getType(KEYS.lic);
					currentLic = [...editor.api.nodes({
						at: listItem[1],
						mode: "lowest",
						match: (node) => node.type === licType
					})][0];
					hasMultipleChildren = currentLic[0].children.length > 1;
				}
				deleteMerge(editor, {
					reverse: true,
					unit
				});
				moved = true;
				if (!currentLic || !hasMultipleChildren) return;
				const leftoverListItem = editor.api.node(PathApi.parent(currentLic[1]));
				if (leftoverListItem && leftoverListItem[0].children.length === 0) editor.tf.removeNodes({ at: leftoverListItem[1] });
			});
		}
		return moved;
	};
	if (deleteBackwardList()) return;
	deleteBackward(unit);
} } });

//#endregion
//#region src/lib/withDeleteForwardList.ts
const selectionIsNotInAListHandler = (editor) => {
	const pointAfterSelection = editor.api.after(editor.selection.focus);
	if (pointAfterSelection) {
		const nextSiblingListRes = getListItemEntry(editor, { at: pointAfterSelection });
		if (nextSiblingListRes) {
			const { listItem } = nextSiblingListRes;
			const parentBlockEntity = editor.api.block({ at: editor.selection.anchor });
			if (!editor.api.string(parentBlockEntity[1])) {
				editor.tf.removeNodes();
				return true;
			}
			if (hasListChild(editor, listItem[0])) moveListItemUp(editor, getListItemEntry(editor, { at: [
				...listItem[1],
				1,
				0,
				0
			] }));
		}
	}
	return false;
};
const selectionIsInAListHandler = (editor, res, defaultDelete, unit = "character") => {
	const { listItem } = res;
	if (!hasListChild(editor, listItem[0])) {
		const liType = editor.getType(KEYS.li);
		const _nodes = editor.api.nodes({
			at: listItem[1],
			mode: "lowest",
			match: (node, path) => {
				if (path.length === 0) return false;
				const isNodeLi = node.type === liType;
				const isSiblingOfNodeLi = NodeApi.get(editor, PathApi.next(path))?.type === liType;
				return isNodeLi && isSiblingOfNodeLi;
			}
		});
		const liWithSiblings = Array.from(_nodes, (entry) => entry[1])[0];
		if (!liWithSiblings) {
			const pointAfterListItem$1 = editor.api.after(listItem[1]);
			if (pointAfterListItem$1) {
				const nextSiblingListRes = getListItemEntry(editor, { at: pointAfterListItem$1 });
				if (nextSiblingListRes) {
					const listRoot = getListRoot(editor, listItem[1]);
					moveListItemsToList(editor, {
						deleteFromList: true,
						fromList: nextSiblingListRes.list,
						toList: listRoot
					});
					return true;
				}
			}
			return false;
		}
		const siblingListItem = editor.api.node(PathApi.next(liWithSiblings));
		if (!siblingListItem) return false;
		const siblingList = editor.api.parent(siblingListItem[1]);
		if (siblingList && removeListItem(editor, {
			list: siblingList,
			listItem: siblingListItem,
			reverse: false
		})) return true;
		const pointAfterListItem = editor.api.after(editor.selection.focus);
		if (!pointAfterListItem || !isAcrossListItems(editor, {
			anchor: editor.selection.anchor,
			focus: pointAfterListItem
		})) return false;
		const licType = editor.getType(KEYS.lic);
		const nextSelectableLic = [...editor.api.nodes({
			at: pointAfterListItem.path,
			mode: "lowest",
			match: (node) => node.type === licType
		})][0];
		if (nextSelectableLic[0].children.length < 2) return false;
		defaultDelete(unit);
		const leftoverListItem = editor.api.node(PathApi.parent(nextSelectableLic[1]));
		if (leftoverListItem && leftoverListItem[0].children.length === 0) editor.tf.removeNodes({ at: leftoverListItem[1] });
		return true;
	}
	const nestedList = editor.api.node(PathApi.next([...listItem[1], 0]));
	if (!nestedList) return false;
	const nestedListItem = Array.from(NodeApi.children(editor, nestedList[1]))[0];
	if (removeFirstListItem(editor, {
		list: nestedList,
		listItem: nestedListItem
	})) return true;
	if (removeListItem(editor, {
		list: nestedList,
		listItem: nestedListItem
	})) return true;
	return false;
};
const withDeleteForwardList = ({ editor, tf: { deleteForward } }) => ({ transforms: { deleteForward(unit) {
	const deleteForwardList = () => {
		let skipDefaultDelete = false;
		if (!editor?.selection) return skipDefaultDelete;
		if (!editor.api.isAt({ end: true })) return skipDefaultDelete;
		editor.tf.withoutNormalizing(() => {
			const res = getListItemEntry(editor, {});
			if (!res) {
				skipDefaultDelete = selectionIsNotInAListHandler(editor);
				return;
			}
			skipDefaultDelete = selectionIsInAListHandler(editor, res, deleteForward, unit);
		});
		return skipDefaultDelete;
	};
	if (deleteForwardList()) return;
	deleteForward(unit);
} } });

//#endregion
//#region src/lib/withDeleteFragmentList.ts
const getLiStart = (editor) => {
	const start = editor.api.start(editor.selection);
	return editor.api.above({
		at: start,
		match: { type: editor.getType(KEYS.li) }
	});
};
const withDeleteFragmentList = ({ editor, tf: { deleteFragment } }) => ({ transforms: { deleteFragment(direction) {
	const deleteFragmentList = () => {
		let deleted = false;
		editor.tf.withoutNormalizing(() => {
			if (!isAcrossListItems(editor)) return;
			/**
			* Check if the end li can be deleted (if it has no sublist). Store
			* the path ref to delete it after deleteMerge.
			*/
			const end = editor.api.end(editor.selection);
			const liEnd = editor.api.above({
				at: end,
				match: { type: editor.getType(KEYS.li) }
			});
			const liEndPathRef = liEnd && !hasListChild(editor, liEnd[0]) ? editor.api.pathRef(liEnd[1]) : void 0;
			if (!getLiStart(editor) || !liEnd) {
				deleted = false;
				return;
			}
			/** Delete fragment and move end block children to start block */
			deleteMerge(editor);
			const liStart = getLiStart(editor);
			if (liEndPathRef) {
				const liEndPath = liEndPathRef.unref();
				const deletePath = getHighestEmptyList(editor, {
					diffListPath: (liStart && editor.api.parent(liStart[1]))?.[1],
					liPath: liEndPath
				});
				if (deletePath) editor.tf.removeNodes({ at: deletePath });
				deleted = true;
			}
		});
		return deleted;
	};
	if (deleteFragmentList()) return;
	deleteFragment(direction);
} } });

//#endregion
//#region src/lib/withInsertBreakList.ts
const withInsertBreakList = ({ editor, getOptions, tf: { insertBreak } }) => ({ transforms: { insertBreak() {
	const insertBreakList = () => {
		if (!editor.selection) return;
		const res = getListItemEntry(editor, {});
		let moved;
		if (res) {
			const { list, listItem } = res;
			if (editor.api.isEmpty(editor.selection, { block: true })) {
				moved = moveListItemUp(editor, {
					list,
					listItem
				});
				if (moved) return true;
			}
		}
		const block = editor.api.block({ match: { type: editor.getType(KEYS.li) } });
		if (block && editor.api.isEmpty(editor.selection, { block: true })) {
			if (editor.tf.resetBlock({ at: block[1] })) return true;
		}
		/** If selection is in li > p, insert li. */
		if (!moved) {
			if (insertListItem(editor, getOptions())) return true;
		}
	};
	if (insertBreakList()) return;
	insertBreak();
} } });

//#endregion
//#region src/lib/withInsertFragmentList.ts
const withInsertFragmentList = ({ editor, tf: { insertFragment } }) => {
	const listItemType = editor.getType(KEYS.li);
	const listItemContentType = editor.getType(KEYS.lic);
	const getFirstAncestorOfType = (root, entry, type) => {
		let ancestor = PathApi.parent(entry[1]);
		while (NodeApi.get(root, ancestor).type !== type) ancestor = PathApi.parent(ancestor);
		return [NodeApi.get(root, ancestor), ancestor];
	};
	const findListItemsWithContent = (first) => {
		let prev = null;
		let node = first;
		while (isListRoot(editor, node) || node.type === listItemType && node.children[0].type !== listItemContentType) {
			prev = node;
			[node] = node.children;
		}
		return prev ? prev.children : [node];
	};
	/**
	* Removes the "empty" leading lis. Empty in this context means lis only with
	* other lis as children.
	*
	* @returns If argument is not a list root, returns it, otherwise returns ul[]
	*   or li[].
	*/
	const trimList = (listRoot) => {
		if (!isListRoot(editor, listRoot)) return [listRoot];
		const _texts = NodeApi.texts(listRoot);
		const textEntries = Array.from(_texts);
		const commonAncestorEntry = textEntries.reduce((commonAncestor, textEntry) => PathApi.isAncestor(commonAncestor[1], textEntry[1]) ? commonAncestor : NodeApi.common(listRoot, textEntry[1], commonAncestor[1]), getFirstAncestorOfType(listRoot, textEntries[0], listItemType));
		const [first, ...rest] = isListRoot(editor, commonAncestorEntry[0]) ? commonAncestorEntry[0].children : [commonAncestorEntry[0]];
		return [...findListItemsWithContent(first), ...rest];
	};
	const wrapNodeIntoListItem = (node, props) => node.type === listItemType ? node : {
		children: [node],
		...props,
		type: listItemType
	};
	/**
	* Checks if the fragment only consists of a single LIC in which case it is
	* considered the user's intention was to copy a text, not a list
	*/
	const isSingleLic = (fragment) => {
		return fragment.length === 1 && isListRoot(editor, fragment[0]) && [...NodeApi.nodes({ children: fragment })].filter((entry) => ElementApi.isElement(entry[0])).filter(([node]) => node.type === listItemContentType).length === 1;
	};
	const getTextAndListItemNodes = (fragment, liEntry, licEntry) => {
		const [, liPath] = liEntry;
		const [licNode, licPath] = licEntry;
		const isEmptyNode = !NodeApi.string(licNode);
		const [first, ...rest] = fragment.flatMap(trimList).map((v) => wrapNodeIntoListItem(v, getPropsIfTaskListLiNode(editor, {
			inherit: true,
			liNode: liEntry[0]
		})));
		let textNode;
		let listItemNodes;
		if (isListRoot(editor, fragment[0])) if (isSingleLic(fragment)) {
			textNode = first;
			listItemNodes = rest;
		} else if (isEmptyNode) {
			const [, ...currentSublists] = NodeApi.get(editor, liPath).children;
			const [newLic, ...newSublists] = first.children;
			editor.tf.insertNodes(newLic, {
				at: PathApi.next(licPath),
				select: true
			});
			editor.tf.removeNodes({ at: licPath });
			if (newSublists?.length) if (currentSublists?.length) {
				const path = [
					...liPath,
					1,
					0
				];
				editor.tf.insertNodes(newSublists[0].children, {
					at: path,
					select: true
				});
			} else editor.tf.insertNodes(newSublists, {
				at: PathApi.next(licPath),
				select: true
			});
			textNode = { text: "" };
			listItemNodes = rest;
		} else {
			textNode = { text: "" };
			listItemNodes = [first, ...rest];
		}
		else {
			textNode = first;
			listItemNodes = rest;
		}
		return {
			listItemNodes,
			textNode
		};
	};
	return { transforms: { insertFragment(fragment) {
		let liEntry = editor.api.node({
			match: { type: listItemType },
			mode: "lowest"
		});
		if (!liEntry) return insertFragment(isListRoot(editor, fragment[0]) ? [{ text: "" }, ...fragment] : fragment);
		insertFragment([{ text: "" }]);
		liEntry = editor.api.node({
			match: { type: listItemType },
			mode: "lowest"
		});
		if (!liEntry) return insertFragment(isListRoot(editor, fragment[0]) ? [{ text: "" }, ...fragment] : fragment);
		const licEntry = editor.api.node({
			match: { type: listItemContentType },
			mode: "lowest"
		});
		if (!licEntry) return insertFragment(isListRoot(editor, fragment[0]) ? [{ text: "" }, ...fragment] : fragment);
		const { listItemNodes, textNode } = getTextAndListItemNodes(fragment, liEntry, licEntry);
		insertFragment([textNode]);
		const [, liPath] = liEntry;
		return editor.tf.insertNodes(listItemNodes, {
			at: PathApi.next(liPath),
			select: true
		});
	} } };
};

//#endregion
//#region src/lib/normalizers/normalizeListItem.ts
/**
* Recursively get all the:
*
* - Block children
* - Inline children except those at excludeDepth
*/
const getDeepInlineChildren = (editor, { children }) => {
	const inlineChildren = [];
	for (const child of children) if (editor.api.isBlock(child[0])) inlineChildren.push(...getDeepInlineChildren(editor, { children: Array.from(NodeApi.children(editor, child[1])) }));
	else inlineChildren.push(child);
	return inlineChildren;
};
/**
* If the list item has no child: insert an empty list item container. Else:
* move the children that are not valid to the list item container.
*/
const normalizeListItem = (editor, { listItem, validLiChildrenTypes = [] }) => {
	let changed = false;
	const allValidLiChildrenTypes = new Set([
		editor.getType(KEYS.lic),
		editor.getType(KEYS.olClassic),
		editor.getType(KEYS.taskList),
		editor.getType(KEYS.ulClassic),
		...validLiChildrenTypes
	]);
	const [, liPath] = listItem;
	const liChildren = Array.from(NodeApi.children(editor, listItem[1]));
	const invalidLiChildrenPathRefs = liChildren.filter(([child]) => !allValidLiChildrenTypes.has(child.type)).map(([, childPath]) => editor.api.pathRef(childPath));
	const firstLiChild = liChildren[0];
	const [firstLiChildNode, firstLiChildPath] = firstLiChild ?? [];
	if (!firstLiChild || !editor.api.isBlock(firstLiChildNode)) {
		editor.tf.insertNodes(editor.api.create.block({ type: editor.getType(KEYS.lic) }), { at: liPath.concat([0]) });
		return true;
	}
	if (editor.api.isBlock(firstLiChildNode) && !match(firstLiChildNode, [], { type: editor.getType(KEYS.lic) })) {
		if (match(firstLiChildNode, [], { type: getListTypes(editor) })) {
			const parent = editor.api.parent(listItem[1]);
			const sublist = firstLiChild;
			Array.from(NodeApi.children(editor, firstLiChild[1])).reverse().forEach((c) => {
				moveListItemUp(editor, {
					list: sublist,
					listItem: c
				});
			});
			editor.tf.removeNodes({ at: [...parent[1], 0] });
			return true;
		}
		if (validLiChildrenTypes.includes(firstLiChildNode.type)) return true;
		editor.tf.setNodes({ type: editor.getType(KEYS.lic) }, { at: firstLiChildPath });
		changed = true;
	}
	const licChildren = Array.from(NodeApi.children(editor, firstLiChild[1]));
	if (licChildren.length > 0) {
		const blockPathRefs = [];
		const inlineChildren = [];
		for (const licChild of licChildren) {
			if (!editor.api.isBlock(licChild[0])) break;
			blockPathRefs.push(editor.api.pathRef(licChild[1]));
			inlineChildren.push(...getDeepInlineChildren(editor, { children: Array.from(NodeApi.children(editor, licChild[1])) }));
		}
		const to = PathApi.next(licChildren.at(-1)[1]);
		inlineChildren.reverse().forEach(([, path]) => {
			editor.tf.moveNodes({
				at: path,
				to
			});
		});
		blockPathRefs.forEach((pathRef) => {
			const path = pathRef.unref();
			if (path) editor.tf.removeNodes({ at: path });
		});
		if (blockPathRefs.length > 0) changed = true;
	}
	if (changed) return true;
	invalidLiChildrenPathRefs.reverse().forEach((ref) => {
		const path = ref.unref();
		if (path) editor.tf.moveNodes({
			at: path,
			to: firstLiChildPath.concat([0])
		});
	});
	return invalidLiChildrenPathRefs.length > 0;
};

//#endregion
//#region src/lib/normalizers/normalizeNestedList.ts
const normalizeNestedList = (editor, { nestedListItem }) => {
	const [, path] = nestedListItem;
	const parentNode = editor.api.parent(path);
	if (!(parentNode && match(parentNode[0], [], { type: getListTypes(editor) }))) return false;
	const previousListItemPath = PathApi.previous(path);
	if (!previousListItemPath) return false;
	const previousSiblingItem = editor.api.node(previousListItemPath);
	if (previousSiblingItem) {
		const [, previousPath] = previousSiblingItem;
		const newPath = previousPath.concat([1]);
		editor.tf.moveNodes({
			at: path,
			to: newPath
		});
		return true;
	}
};

//#endregion
//#region src/lib/withNormalizeList.ts
/** Normalize list node to force the ul>li>p+ul structure. */
const withNormalizeList = ({ editor, getOptions, tf: { normalizeNode } }) => ({ transforms: { normalizeNode([node, path]) {
	const liType = editor.getType(KEYS.li);
	const licType = editor.getType(KEYS.lic);
	const defaultType = editor.getType(KEYS.p);
	if (!ElementApi.isElement(node)) return normalizeNode([node, path]);
	if (isListRoot(editor, node)) {
		const nonLiChild = Array.from(NodeApi.children(editor, path)).find(([child]) => child.type !== liType);
		if (nonLiChild) return editor.tf.wrapNodes({
			children: [],
			type: liType
		}, { at: nonLiChild[1] });
		if (node.type === editor.getType(KEYS.taskList)) {
			const nonTaskListItems = Array.from(NodeApi.children(editor, path)).filter(([child]) => child.type === liType && !("checked" in child));
			if (nonTaskListItems.length > 0) return editor.tf.withoutNormalizing(() => nonTaskListItems.forEach(([, itemPath]) => {
				editor.tf.setNodes({ checked: false }, { at: itemPath });
			}));
		} else {
			const taskListItems = Array.from(NodeApi.children(editor, path)).filter(([child]) => child.type === liType && "checked" in child);
			if (taskListItems.length > 0) return editor.tf.withoutNormalizing(() => taskListItems.forEach(([, itemPath]) => {
				editor.tf.unsetNodes("checked", { at: itemPath });
			}));
		}
	}
	if (match(node, [], { type: getListTypes(editor) })) {
		if (node.children.length === 0 || !node.children.some((item) => item.type === liType)) return editor.tf.removeNodes({ at: path });
		const nextPath = PathApi.next(path);
		const nextNode = NodeApi.get(editor, nextPath);
		if (nextNode?.type === node.type) moveListItemsToList(editor, {
			deleteFromList: true,
			fromList: [nextNode, nextPath],
			toList: [node, path]
		});
		const prevPath = PathApi.previous(path);
		const prevNode = NodeApi.get(editor, prevPath);
		if (prevNode?.type === node.type) {
			editor.tf.normalizeNode([prevNode, prevPath]);
			return;
		}
		if (normalizeNestedList(editor, { nestedListItem: [node, path] })) return;
	}
	if (node.type === editor.getType(KEYS.li) && normalizeListItem(editor, {
		listItem: [node, path],
		validLiChildrenTypes: getOptions().validLiChildrenTypes
	})) return;
	if (node.type === licType && licType !== defaultType && editor.api.parent(path)?.[0].type !== liType) {
		editor.tf.setNodes({ type: defaultType }, { at: path });
		return;
	}
	normalizeNode([node, path]);
} } });

//#endregion
//#region src/lib/withList.ts
const withList = (ctx) => {
	const { editor, getOptions, tf: { resetBlock, tab } } = ctx;
	return { transforms: {
		resetBlock: (options) => {
			if (editor.api.block({
				at: options?.at,
				match: { type: editor.getType(KEYS.li) }
			})) {
				unwrapList(editor);
				return;
			}
			return resetBlock(options);
		},
		tab: (options) => {
			const apply = () => {
				let workRange = editor.selection;
				if (editor.selection) {
					const { selection } = editor;
					if (!editor.api.isCollapsed()) {
						const { anchor, focus } = RangeApi.isBackward(selection) ? {
							anchor: { ...selection.focus },
							focus: { ...selection.anchor }
						} : {
							anchor: { ...selection.anchor },
							focus: { ...selection.focus }
						};
						const unhangRange = editor.api.unhangRange({
							anchor,
							focus
						});
						if (unhangRange) {
							workRange = unhangRange;
							editor.tf.select(unhangRange);
						}
					}
					const listSelected = editor.api.some({ match: { type: editor.getType(KEYS.li) } });
					if (workRange && listSelected) {
						moveListItems(editor, {
							at: workRange,
							enableResetOnShiftTab: getOptions().enableResetOnShiftTab,
							increase: !options.reverse
						});
						return true;
					}
				}
			};
			if (apply()) return true;
			return tab(options);
		},
		...withInsertBreakList(ctx).transforms,
		...withDeleteBackwardList(ctx).transforms,
		...withDeleteForwardList(ctx).transforms,
		...withDeleteFragmentList(ctx).transforms,
		...withInsertFragmentList(ctx).transforms,
		...withNormalizeList(ctx).transforms
	} };
};

//#endregion
//#region src/lib/BaseListPlugin.ts
const BaseBulletedListPlugin = createSlatePlugin({
	key: KEYS.ulClassic,
	node: {
		isContainer: true,
		isElement: true
	},
	parsers: { html: { deserializer: { rules: [{ validNodeName: "UL" }] } } },
	render: { as: "ul" }
}).extendTransforms(({ editor }) => ({ toggle: () => {
	toggleBulletedList(editor);
} }));
const BaseNumberedListPlugin = createSlatePlugin({
	key: KEYS.olClassic,
	node: {
		isContainer: true,
		isElement: true
	},
	parsers: { html: { deserializer: { rules: [{ validNodeName: "OL" }] } } },
	render: { as: "ol" }
}).extendTransforms(({ editor }) => ({ toggle: () => {
	toggleNumberedList(editor);
} }));
const BaseTaskListPlugin = createSlatePlugin({
	key: KEYS.taskList,
	node: {
		isContainer: true,
		isElement: true
	},
	options: {
		inheritCheckStateOnLineEndBreak: false,
		inheritCheckStateOnLineStartBreak: false
	},
	render: { as: "ul" }
}).extendTransforms(({ editor }) => ({ toggle: () => {
	toggleTaskList(editor);
} }));
const BaseListItemPlugin = createSlatePlugin({
	key: KEYS.li,
	inject: { plugins: { [KEYS.html]: { parser: { preInsert: ({ editor, type }) => editor.api.some({ match: { type } }) } } } },
	node: {
		isContainer: true,
		isElement: true,
		isStrictSiblings: true
	},
	parsers: { html: { deserializer: { rules: [{ validNodeName: "LI" }] } } },
	render: { as: "li" }
});
const BaseListItemContentPlugin = createSlatePlugin({
	key: KEYS.lic,
	node: { isElement: true }
});
/** Enables support for bulleted, numbered and to-do lists. */
const BaseListPlugin = createTSlatePlugin({
	key: KEYS.listClassic,
	plugins: [
		BaseBulletedListPlugin,
		BaseNumberedListPlugin,
		BaseTaskListPlugin,
		BaseListItemPlugin,
		BaseListItemContentPlugin
	]
}).overrideEditor(withList).extendEditorTransforms(({ editor }) => ({ toggle: {
	bulletedList: bindFirst(toggleBulletedList, editor),
	list: bindFirst(toggleList, editor),
	numberedList: bindFirst(toggleNumberedList, editor),
	taskList: bindFirst(toggleTaskList, editor)
} }));

//#endregion
export { moveListItemsToList as A, getHighestEmptyList as B, insertTodoListItem as C, removeFirstListItem as D, moveListItems as E, getTodoListItemEntry as F, isListNested as H, getPropsIfTaskList as I, getPropsIfTaskListLiNode as L, isListRoot as M, isAcrossListItems as N, moveListItemUp as O, hasListChild as P, getListRoot as R, moveListItemSublistItemsToListItemSublist as S, insertListItem as T, getListTypes as V, toggleBulletedList as _, BaseNumberedListPlugin as a, toggleTaskList as b, withNormalizeList as c, normalizeListItem as d, withInsertFragmentList as f, withDeleteBackwardList as g, withDeleteForwardList as h, BaseListPlugin as i, moveListItemDown as j, unwrapList as k, normalizeNestedList as l, withDeleteFragmentList as m, BaseListItemContentPlugin as n, BaseTaskListPlugin as o, withInsertBreakList as p, BaseListItemPlugin as r, withList as s, BaseBulletedListPlugin as t, getDeepInlineChildren as u, toggleList as v, BaseTodoListPlugin as w, removeListItem as x, toggleNumberedList as y, getListItemEntry as z };