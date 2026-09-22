import { ElementApi, KEYS, NodeApi, PathApi, PointApi, RangeApi, TextApi, createEditor } from "platejs";
import isEqual from "lodash/isEqual.js";
import isPlainObject from "lodash/isPlainObject.js";
import { DiffMatchPatch } from "diff-match-patch-ts";
import uniqWith from "lodash/uniqWith.js";
import cloneDeep from "lodash/cloneDeep.js";

//#region src/internal/utils/is-equal.ts
const without = (x, { ignoreDeep = [], ignoreShallow = [] } = {}) => {
	if (Array.isArray(x)) return x.map((y) => without(y, {
		ignoreDeep,
		ignoreShallow
	}));
	if (!isPlainObject(x)) return x;
	const obj = x;
	const result = {};
	for (const [key, value] of Object.entries(obj)) {
		if (ignoreShallow.includes(key) || ignoreDeep.includes(key)) continue;
		result[key] = without(value, { ignoreDeep });
	}
	return result;
};
const isEqual$1 = (value, other, options) => isEqual(without(value, options), without(other, options));

//#endregion
//#region src/internal/transforms/transformDiffNodes.ts
/**
* Only the children have changed. Recursively call the top-level diff algorithm
* on the children.
*/
const childrenOnlyStrategy = (node, nextNode, options) => {
	if (node.children != null && nextNode.children != null && isEqual$1(node, nextNode, {
		ignoreDeep: options.ignoreProps,
		ignoreShallow: ["children"]
	})) {
		const children = computeDiff(node.children, nextNode.children, options);
		return [{
			...nextNode,
			children
		}];
	}
	return false;
};
const propsOnlyStrategy = (node, nextNode, { getUpdateProps }) => {
	const properties = {};
	const newProperties = {};
	for (const key in node) if (!isEqual$1(node[key], nextNode[key])) {
		if (key === "children" || key === "text") return false;
		properties[key] = node[key];
		newProperties[key] = nextNode[key];
	}
	for (const key in nextNode) if (node[key] === void 0) {
		if (key === "children" || key === "text") return false;
		newProperties[key] = nextNode[key];
	}
	return [{
		...nextNode,
		...getUpdateProps(node, properties, newProperties)
	}];
};
const strategies = [childrenOnlyStrategy, propsOnlyStrategy];
function transformDiffNodes(node, nextNode, options) {
	for (const strategy of strategies) {
		const ops = strategy(node, nextNode, options);
		if (ops) return ops;
	}
	return false;
}

//#endregion
//#region src/internal/utils/dmp.ts
/**
* This Apache-2.0 licensed file has been modified by Udecode and other
* contributors. See /packages/diff/LICENSE for more information.
*/
const dmp = new DiffMatchPatch();
dmp.Diff_Timeout = .2;

//#endregion
//#region src/internal/utils/get-properties.ts
function getProperties(goal, before) {
	const props = {};
	for (const x in goal) if (x !== "text") {
		if (before == null) {
			if (goal[x]) props[x] = goal[x];
		} else if (goal[x] !== before[x]) if (goal[x]) props[x] = goal[x];
		else props[x] = void 0;
	}
	if (before != null) {
		for (const x in before) if (x !== "text" && goal[x] == null) props[x] = void 0;
	}
	return props;
}

//#endregion
//#region src/internal/utils/inline-node-char-map.ts
var InlineNodeCharMap = class {
	_charGenerator;
	_charToNode = /* @__PURE__ */ new Map();
	constructor({ charGenerator }) {
		this._charGenerator = charGenerator;
	}
	insertBetweenPairs(arr, between) {
		return arr.flatMap((x, i) => {
			if (i === arr.length - 1) return x;
			return [x, between];
		});
	}
	replaceCharWithNode(haystack, needle, replacementNode) {
		return haystack.flatMap((haystackNode) => {
			if (!TextApi.isText(haystackNode)) return [haystackNode];
			const splitText = haystackNode.text.split(needle);
			if (splitText.length === 1) return [haystackNode];
			const replacementWithProps = {
				...replacementNode,
				...NodeApi.extractProps(haystackNode)
			};
			const nodesForTexts = splitText.map((text) => ({
				...haystackNode,
				text
			}));
			return this.insertBetweenPairs(nodesForTexts, replacementWithProps).filter((n) => !TextApi.isText(n) || n.text.length > 0);
		});
	}
	nodeToText(node) {
		if (TextApi.isText(node)) return node;
		const c = this._charGenerator.next().value;
		this._charToNode.set(c, node);
		return { text: c };
	}
	textToNode(initialTextNode) {
		let outputNodes = [initialTextNode];
		for (const [c, originalNode] of this._charToNode) outputNodes = this.replaceCharWithNode(outputNodes, c, originalNode);
		return outputNodes;
	}
};

//#endregion
//#region src/internal/utils/unused-char-generator.ts
function* unusedCharGenerator({ skipChars = "" } = {}) {
	const skipSet = new Set(skipChars);
	for (let code = "A".codePointAt(0);; code++) {
		const c = String.fromCodePoint(code);
		if (skipSet.has(c)) continue;
		yield c;
	}
}

//#endregion
//#region src/internal/utils/with-change-tracking.ts
const withChangeTracking = (editor, options) => {
	const e = editor;
	e.propsChanges = [];
	e.insertedTexts = [];
	e.removedTexts = [];
	e.recordingOperations = true;
	const { apply } = e;
	e.apply = (op) => applyWithChangeTracking(e, apply, op);
	e.tf.apply = e.apply;
	e.commitChangesToDiffs = () => commitChangesToDiffs(e, options);
	return e;
};
const applyWithChangeTracking = (editor, apply, op) => {
	if (!editor.recordingOperations) return apply(op);
	withoutRecordingOperations(editor, () => {
		switch (op.type) {
			case "insert_text":
				applyInsertText(editor, apply, op);
				break;
			case "merge_node":
				applyMergeNode(editor, apply, op);
				break;
			case "remove_text":
				applyRemoveText(editor, apply, op);
				break;
			case "set_node":
				applySetNode(editor, apply, op);
				break;
			case "split_node":
				applySplitNode(editor, apply, op);
				break;
			default: apply(op);
		}
	});
};
const applyInsertText = (editor, apply, op) => {
	const node = NodeApi.get(editor, op.path);
	apply(op);
	const range = {
		anchor: {
			offset: op.offset,
			path: op.path
		},
		focus: {
			offset: op.offset + op.text.length,
			path: op.path
		}
	};
	const rangeRef = editor.api.rangeRef(range);
	editor.insertedTexts.push({
		node: {
			...node,
			text: op.text
		},
		rangeRef
	});
};
const applyRemoveText = (editor, apply, op) => {
	const node = NodeApi.get(editor, op.path);
	apply(op);
	const point = {
		offset: op.offset,
		path: op.path
	};
	const pointRef = editor.api.pointRef(point, { affinity: "backward" });
	editor.removedTexts.push({
		node: {
			...node,
			text: op.text
		},
		pointRef
	});
};
const applyMergeNode = (editor, apply, op) => {
	const oldNode = NodeApi.get(editor, op.path);
	const properties = NodeApi.extractProps(oldNode);
	const prevNodePath = PathApi.previous(op.path);
	const prevNode = NodeApi.get(editor, prevNodePath);
	const newProperties = NodeApi.extractProps(prevNode);
	apply(op);
	const range = {
		anchor: {
			offset: prevNode.text.length,
			path: prevNodePath
		},
		focus: editor.api.end(prevNodePath)
	};
	const rangeRef = editor.api.rangeRef(range);
	editor.propsChanges.push({
		newProperties,
		properties,
		rangeRef
	});
};
const applySplitNode = (editor, apply, op) => {
	const oldNode = NodeApi.get(editor, op.path);
	const properties = NodeApi.extractProps(oldNode);
	const newProperties = op.properties;
	apply(op);
	const newNodePath = PathApi.next(op.path);
	const newNodeRange = editor.api.range(newNodePath);
	const rangeRef = editor.api.rangeRef(newNodeRange);
	editor.propsChanges.push({
		newProperties,
		properties,
		rangeRef
	});
};
const applySetNode = (editor, apply, op) => {
	apply(op);
	const range = editor.api.range(op.path);
	const rangeRef = editor.api.rangeRef(range);
	editor.propsChanges.push({
		newProperties: op.newProperties,
		properties: op.properties,
		rangeRef
	});
};
const commitChangesToDiffs = (editor, { getDeleteProps, getInsertProps, getUpdateProps }) => {
	withoutRecordingOperations(editor, () => {
		flattenPropsChanges(editor).reverse().forEach(({ newProperties, properties, range }) => {
			const node = NodeApi.get(editor, range.anchor.path);
			editor.tf.setNodes(getUpdateProps(node, properties, newProperties), {
				at: range,
				marks: true
			});
		});
		editor.removedTexts.forEach(({ node, pointRef }) => {
			const point = pointRef.current;
			if (point) editor.tf.insertNode({
				...node,
				...getDeleteProps(node)
			}, { at: point });
			pointRef.unref();
		});
		editor.insertedTexts.forEach(({ node, rangeRef }) => {
			const range = rangeRef.current;
			if (range) editor.tf.setNodes(getInsertProps(node), {
				at: range,
				marks: true
			});
			rangeRef.unref();
		});
	});
};
const flattenPropsChanges = (editor) => {
	const propChangeRangeRefs = editor.propsChanges.map(({ rangeRef }) => rangeRef);
	const insertedTextRangeRefs = editor.insertedTexts.map(({ rangeRef }) => rangeRef);
	const rangePoints = uniqWith([...propChangeRangeRefs, ...insertedTextRangeRefs].flatMap((rangeRef) => {
		const range = rangeRef.current;
		if (!range) return [];
		return [range.anchor, range.focus];
	}).sort(PointApi.compare), PointApi.equals);
	if (rangePoints.length < 2) return [];
	const flatUpdates = Array.from({ length: rangePoints.length - 1 }).fill(null).map((_, i) => ({
		anchor: rangePoints[i],
		focus: rangePoints[i + 1]
	})).map((flatRange) => {
		const getIntersectingChanges = (changes) => changes.filter(({ rangeRef }) => {
			const range = rangeRef.current;
			if (!range) return false;
			const intersection = RangeApi.intersection(range, flatRange);
			if (!intersection) return false;
			return RangeApi.isExpanded(intersection);
		});
		if (getIntersectingChanges(editor.insertedTexts).length > 0) return null;
		const intersectingUpdates = getIntersectingChanges(editor.propsChanges);
		if (intersectingUpdates.length === 0) return null;
		const initialProps = objectWithoutUndefined(intersectingUpdates[0].properties);
		const finalProps = objectWithoutUndefined(intersectingUpdates.at(-1).newProperties);
		if (isEqual(initialProps, finalProps)) return null;
		const properties = {};
		const newProperties = {};
		for (const key of Object.keys(finalProps)) if (!isEqual(initialProps[key], finalProps[key])) {
			properties[key] = initialProps[key];
			newProperties[key] = finalProps[key];
		}
		for (const key of Object.keys(initialProps)) if (finalProps[key] === void 0) {
			properties[key] = initialProps[key];
			newProperties[key] = void 0;
		}
		return {
			newProperties,
			properties,
			range: flatRange
		};
	});
	for (const rangeRef of propChangeRangeRefs) rangeRef.unref();
	return flatUpdates.filter(Boolean);
};
const objectWithoutUndefined = (obj) => {
	const newObj = {};
	Object.keys(obj).forEach((key) => {
		if (obj[key] !== void 0) newObj[key] = obj[key];
	});
	return newObj;
};
const withoutRecordingOperations = (editor, fn) => {
	editor.recordingOperations = false;
	fn();
	editor.recordingOperations = true;
};

//#endregion
//#region src/internal/transforms/transformDiffTexts.ts
/**
* This Apache-2.0 licensed file has been modified by Udecode and other
* contributors. See /packages/diff/LICENSE for more information.
*/
function transformDiffTexts(nodes, nextNodes, options) {
	if (nodes.length === 0) throw new Error("must have at least one nodes");
	if (nextNodes.length === 0) throw new Error("must have at least one nextNodes");
	if (nodes.length === 1 && nextNodes.length === 1 && !TextApi.isText(nodes[0]) && !TextApi.isText(nextNodes[0]) && options.isInline(nodes[0]) && options.isInline(nextNodes[0])) {
		const element = nodes[0];
		const nextElement = nextNodes[0];
		if (element.type === nextElement.type && element.children && nextElement.children) {
			const { children: _1, ...elementProps } = element;
			const { children: _2, ...nextElementProps } = nextElement;
			if (isEqual$1(elementProps, nextElementProps, { ignoreDeep: options.ignoreProps })) {
				const diffedChildren = computeDiff(element.children, nextElement.children, options);
				return [{
					...nextElement,
					children: diffedChildren
				}];
			}
		}
	}
	const { lineBreakChar } = options;
	const hasLineBreakChar = lineBreakChar !== void 0;
	const charGenerator = unusedCharGenerator({ skipChars: nodes.concat(nextNodes).filter(TextApi.isText).map((n) => n.text).join("") });
	/**
	* Chars to represent inserted and deleted line breaks in the diff. These must
	* have a length of 1 to keep the offsets consistent. `lineBreakChar` itself
	* may have any length.
	*/
	const insertedLineBreakProxyChar = hasLineBreakChar ? charGenerator.next().value : void 0;
	const deletedLineBreakProxyChar = hasLineBreakChar ? charGenerator.next().value : void 0;
	const inlineNodeCharMap = new InlineNodeCharMap({ charGenerator });
	const texts = nodes.map((n) => inlineNodeCharMap.nodeToText(n));
	const nextTexts = nextNodes.map((n) => inlineNodeCharMap.nodeToText(n));
	const nodesEditor = withChangeTracking(createEditor(), options);
	nodesEditor.children = [{
		children: texts,
		type: KEYS.p
	}];
	nodesEditor.tf.withoutNormalizing(() => {
		let node = texts[0];
		if (texts.length > 1) for (let i = 1; i < texts.length; i++) {
			nodesEditor.tf.apply({
				path: [0, 1],
				position: 0,
				properties: {},
				type: "merge_node"
			});
			node = {
				...node,
				text: node.text + texts[i].text
			};
		}
		for (const op of splitTextNodes(node, nextTexts, {
			deletedLineBreakChar: deletedLineBreakProxyChar,
			insertedLineBreakChar: insertedLineBreakProxyChar
		})) nodesEditor.tf.apply(op);
		nodesEditor.commitChangesToDiffs();
	});
	let diffTexts = nodesEditor.children[0].children;
	if (hasLineBreakChar) diffTexts = diffTexts.map((n) => ({
		...n,
		text: n.text.replaceAll(insertedLineBreakProxyChar, `${lineBreakChar}\n`).replaceAll(deletedLineBreakProxyChar, lineBreakChar)
	}));
	return diffTexts.flatMap((t) => inlineNodeCharMap.textToNode(t));
}
function slateTextDiff(a, b, { deletedLineBreakChar, insertedLineBreakChar }) {
	const diff = dmp.diff_main(a, b);
	dmp.diff_cleanupSemantic(diff);
	const operations = [];
	let offset = 0;
	let i = 0;
	while (i < diff.length) {
		const chunk = diff[i];
		const op = chunk[0];
		const text = chunk[1];
		switch (op) {
			case -1:
				operations.push({
					offset,
					text: deletedLineBreakChar === void 0 ? text : text.replaceAll("\n", deletedLineBreakChar),
					type: "remove_text"
				});
				break;
			case 0:
				offset += text.length;
				break;
			case 1:
				operations.push({
					offset,
					text: insertedLineBreakChar === void 0 ? text : text.replaceAll("\n", insertedLineBreakChar),
					type: "insert_text"
				});
				offset += text.length;
				break;
		}
		i += 1;
	}
	return operations;
}
function splitTextNodes(node, split, options) {
	if (split.length === 0) return [{
		node,
		path: [0, 0],
		type: "remove_node"
	}];
	let splitText = "";
	for (const { text } of split) splitText += text;
	const nodeText = node.text;
	const operations = [];
	if (splitText !== nodeText) for (const op of slateTextDiff(nodeText, splitText, options)) operations.push({
		path: [0, 0],
		...op
	});
	const newProperties = getProperties(split[0], node);
	if (getKeysLength(newProperties) > 0) operations.push({
		newProperties,
		path: [0, 0],
		properties: getProperties(node),
		type: "set_node"
	});
	let properties = getProperties(split[0]);
	let splitPath = [0, 0];
	for (let i = 0; i < split.length - 1; i++) {
		const part = split[i];
		const nextPart = split[i + 1];
		const newProps = getProperties(nextPart);
		Object.keys(properties).forEach((key) => {
			if (!Object.hasOwn(newProps, key)) newProps[key] = void 0;
		});
		operations.push({
			path: splitPath,
			position: part.text.length,
			properties: newProps,
			type: "split_node"
		});
		splitPath = PathApi.next(splitPath);
		properties = getProperties(nextPart);
	}
	return operations;
}
function getKeysLength(obj) {
	if (obj == null) return 0;
	return Object.keys(obj).length;
}

//#endregion
//#region src/internal/utils/diff-nodes.ts
/**
* This Apache-2.0 licensed file has been modified by Udecode and other
* contributors. See /packages/diff/LICENSE for more information.
*/
function diffNodes(originNodes, targetNodes, { elementsAreRelated, ignoreProps }) {
	const result = [];
	let relatedNode;
	const remainingTargetNodes = [...targetNodes];
	originNodes.forEach((originNode) => {
		let childrenUpdated = false;
		let nodeUpdated = false;
		relatedNode = remainingTargetNodes.find((targetNode) => {
			if (ElementApi.isElement(originNode) && ElementApi.isElement(targetNode)) {
				const relatedResult = elementsAreRelated?.(originNode, targetNode) ?? null;
				if (relatedResult !== null) return relatedResult;
			}
			childrenUpdated = isEqualNode(originNode, targetNode, ignoreProps);
			nodeUpdated = isEqualNodeChildren(originNode, targetNode);
			return nodeUpdated || childrenUpdated;
		});
		if (relatedNode) {
			remainingTargetNodes.splice(0, remainingTargetNodes.indexOf(relatedNode)).forEach((insertNode) => {
				result.push({
					insert: true,
					originNode: insertNode
				});
			});
			remainingTargetNodes.splice(0, 1);
		}
		result.push({
			childrenUpdated,
			delete: !relatedNode,
			nodeUpdated,
			originNode,
			relatedNode
		});
	});
	remainingTargetNodes.forEach((insertNode) => {
		result.push({
			insert: true,
			originNode: insertNode
		});
	});
	return result;
}
function isEqualNode(value, other, ignoreProps) {
	return ElementApi.isElement(value) && ElementApi.isElement(other) && value.children !== null && other.children !== null && isEqual$1(value, other, {
		ignoreDeep: ignoreProps,
		ignoreShallow: ["children"]
	});
}
function isEqualNodeChildren(value, other) {
	if (ElementApi.isElement(value) && ElementApi.isElement(other) && isEqual$1(value.children, other.children)) return true;
	return TextApi.isText(value) && TextApi.isText(other) && isEqual$1(value.text, other.text);
}

//#endregion
//#region src/internal/transforms/transformDiffDescendants.ts
/**
* This Apache-2.0 licensed file has been modified by Udecode and other
* contributors. See /packages/diff/LICENSE for more information.
*/
const OP_UNCHANGED = 0;
const OP_DELETE = -1;
const OP_INSERT = 1;
function transformDiffDescendants(diff, { stringCharMapping, ...options }) {
	const { getDeleteProps, getInsertProps, ignoreProps, isInline } = options;
	let i = 0;
	const children = [];
	let insertBuffer = [];
	let deleteBuffer = [];
	const flushBuffers = () => {
		children.push(...deleteBuffer, ...insertBuffer);
		insertBuffer = [];
		deleteBuffer = [];
	};
	const insertNode = (node) => insertBuffer.push({
		...node,
		...getInsertProps(node)
	});
	const deleteNode = (node) => deleteBuffer.push({
		...node,
		...getDeleteProps(node)
	});
	const passThroughNodes = (...nodes) => {
		flushBuffers();
		children.push(...nodes);
	};
	const isInlineList = (nodes) => nodes.every((node) => TextApi.isText(node) || isInline(node));
	while (i < diff.length) {
		const chunk = diff[i];
		const op = chunk[0];
		const val = chunk[1];
		const nodes = stringCharMapping.stringToNodes(val);
		switch (op) {
			case OP_UNCHANGED:
				passThroughNodes(...nodes);
				i += 1;
				continue;
			case OP_DELETE:
				if (i < diff.length - 1 && diff[i + 1][0] === OP_INSERT) {
					const nextVal = diff[i + 1][1];
					const nextNodes = stringCharMapping.stringToNodes(nextVal);
					/**
					* If the node lists are identical when ignored props are excluded,
					* just return nextNodes.
					*/
					if (isEqual$1(nodes, nextNodes, { ignoreDeep: ignoreProps })) {
						passThroughNodes(...nextNodes);
						i += 2;
						continue;
					}
					if (isInlineList(nodes) && isInlineList(nextNodes)) {
						passThroughNodes(...transformDiffTexts(nodes, nextNodes, options));
						i += 2;
						continue;
					}
					diffNodes(nodes, nextNodes, options).forEach((item) => {
						if (item.delete) deleteNode(item.originNode);
						if (item.insert) insertNode(item.originNode);
						if (item.relatedNode) {
							const diffNodesResult = transformDiffNodes(item.originNode, item.relatedNode, options);
							if (diffNodesResult) passThroughNodes(...diffNodesResult);
							else {
								deleteNode(item.originNode);
								insertNode(item.relatedNode);
							}
						}
					});
					i += 2;
					continue;
				}
				for (const node of nodes) deleteNode(node);
				i += 1;
				continue;
			case OP_INSERT:
				for (const node of nodes) insertNode(node);
				i += 1;
				continue;
		}
	}
	flushBuffers();
	return children;
}

//#endregion
//#region src/internal/utils/string-char-mapping.ts
var StringCharMapping = class {
	_charGenerator = unusedCharGenerator();
	_mappedNodes = [];
	charToNode(c) {
		const entry = this._mappedNodes.find(([_node, c2]) => c2 === c);
		if (!entry) throw new Error(`No node found for char ${c}`);
		return entry[0];
	}
	nodesToString(nodes) {
		return nodes.map(this.nodeToChar.bind(this)).join("");
	}
	nodeToChar(node) {
		for (const [n, c$1] of this._mappedNodes) if (isEqual(n, node)) return c$1;
		const c = this._charGenerator.next().value;
		this._mappedNodes.push([node, c]);
		return c;
	}
	stringToNodes(s) {
		return s.split("").map(this.charToNode.bind(this));
	}
};

//#endregion
//#region src/lib/computeDiff.ts
const computeDiff = (doc0, doc1, { elementsAreRelated, getDeleteProps = defaultGetDeleteProps, getInsertProps = defaultGetInsertProps, getUpdateProps = defaultGetUpdateProps, ignoreProps, isInline = () => false, ...options } = {}) => {
	const stringCharMapping = new StringCharMapping();
	const m0 = stringCharMapping.nodesToString(doc0);
	const m1 = stringCharMapping.nodesToString(doc1);
	return transformDiffDescendants(dmp.diff_main(m0, m1), {
		elementsAreRelated,
		getDeleteProps,
		getInsertProps,
		ignoreProps,
		isInline,
		stringCharMapping,
		getUpdateProps: (node, properties, newProperties) => {
			if (ignoreProps && Object.keys(newProperties).every((key) => ignoreProps.includes(key))) return {};
			return getUpdateProps(node, properties, newProperties);
		},
		...options
	});
};
const defaultGetInsertProps = () => ({
	diff: true,
	diffOperation: { type: "insert" }
});
const defaultGetDeleteProps = () => ({
	diff: true,
	diffOperation: { type: "delete" }
});
const defaultGetUpdateProps = (_node, properties, newProperties) => ({
	diff: true,
	diffOperation: {
		newProperties,
		properties,
		type: "update"
	}
});

//#endregion
//#region src/lib/withGetFragmentExcludeDiff.ts
const withGetFragmentExcludeDiff = ({ api: { getFragment } }) => ({ api: { getFragment() {
	const fragment = cloneDeep(getFragment());
	const removeDiff = (node) => {
		if ("diff" in node) node.diff = void 0;
		if ("diffOperation" in node) node.diffOperation = void 0;
		if ("children" in node) node.children.forEach(removeDiff);
	};
	fragment.forEach(removeDiff);
	return fragment;
} } });

//#endregion
export { computeDiff, defaultGetDeleteProps, defaultGetInsertProps, defaultGetUpdateProps, withGetFragmentExcludeDiff };