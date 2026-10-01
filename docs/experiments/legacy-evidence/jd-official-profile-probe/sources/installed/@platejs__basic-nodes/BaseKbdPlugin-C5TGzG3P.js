import { ElementApi, KEYS, PathApi, createSlatePlugin, createTSlatePlugin, findHtmlParentElement, someHtmlElement } from "platejs";

//#region src/lib/BaseBlockquotePlugin.ts
const normalizeBlockquoteChildren = (editor, children = []) => {
	const paragraphType = editor.getType(KEYS.p);
	const elements = [];
	let inlineNodes = [];
	const flushInlineNodes = () => {
		if (inlineNodes.length === 0) return;
		elements.push({
			children: inlineNodes,
			type: paragraphType
		});
		inlineNodes = [];
	};
	children.forEach((child) => {
		if (ElementApi.isElement(child) && !editor.api.isInline(child) && editor.api.isBlock(child)) {
			flushInlineNodes();
			elements.push(child);
			return;
		}
		inlineNodes.push(child);
	});
	flushInlineNodes();
	if (elements.length > 0) return elements;
	return [{
		children: [{ text: "" }],
		type: paragraphType
	}];
};
const isLiftableBlockquoteChild = (editor, node$1, path, blockquoteType) => {
	const paragraphType = editor.getType(KEYS.p);
	if (node$1.type !== paragraphType || node$1[KEYS.listType]) return false;
	return !!editor.api.above({
		at: path,
		match: (entryNode, entryPath) => entryPath.length < path.length && entryNode.type === blockquoteType
	});
};
const shouldLiftOnDeleteStart = (editor, node$1, path, blockquoteType) => {
	if (!isLiftableBlockquoteChild(editor, node$1, path, blockquoteType)) return false;
	if (!(!!editor.selection && editor.api.isEmpty(editor.selection, { block: true }))) return true;
	const parent = editor.api.parent(path);
	if (!parent || parent[0].type !== blockquoteType) return true;
	return !PathApi.hasPrevious(path);
};
/** Enables support for block quotes, useful for quotations and passages. */
const BaseBlockquotePlugin = createSlatePlugin({
	key: KEYS.blockquote,
	node: { isElement: true },
	parsers: { html: { deserializer: { rules: [{ validNodeName: "BLOCKQUOTE" }] } } },
	render: { as: "blockquote" },
	rules: {
		break: { empty: "lift" },
		delete: { start: "lift" },
		match: ({ editor, node: node$1, path, rule }) => {
			if (!["break.empty", "delete.start"].includes(rule)) return false;
			if (!path) return false;
			const blockquoteType = editor.getType(KEYS.blockquote);
			if (rule === "delete.start") return shouldLiftOnDeleteStart(editor, node$1, path, blockquoteType);
			return isLiftableBlockquoteChild(editor, node$1, path, blockquoteType);
		}
	}
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleBlock(type, { wrap: true });
} })).overrideEditor(({ editor, tf: { normalizeNode, tab }, type }) => ({ transforms: {
	normalizeNode([node$1, path]) {
		if (ElementApi.isElement(node$1) && node$1.type === type) {
			const nextChildren = normalizeBlockquoteChildren(editor, node$1.children);
			if (nextChildren.length !== node$1.children.length || nextChildren.some((child, index) => child !== node$1.children[index])) {
				editor.tf.replaceNodes(nextChildren, {
					at: path,
					children: true
				});
				return;
			}
		}
		normalizeNode([node$1, path]);
	},
	tab(options) {
		if (options.reverse) {
			const liftableBlocks = editor.api.blocks({
				mode: "lowest",
				match: (node$1, path) => !node$1.indent && isLiftableBlockquoteChild(editor, node$1, path, type)
			});
			if (liftableBlocks.length > 0) {
				const blocks = [...liftableBlocks].sort((a, b) => b[1].length - a[1].length || b[1].join(".").localeCompare(a[1].join(".")));
				editor.tf.withoutNormalizing(() => {
					for (const [, path] of blocks) editor.tf.liftBlock({
						at: path,
						match: { type }
					});
				});
				return true;
			}
		}
		return tab(options);
	}
} }));

//#endregion
//#region src/lib/BaseHeadingPlugin.ts
const node = { isElement: true };
const rules = {
	break: { splitReset: true },
	delete: { start: "reset" },
	merge: { removeEmpty: true }
};
const BaseH1Plugin = createTSlatePlugin({
	key: "h1",
	node,
	parsers: { html: { deserializer: { rules: [{ validNodeName: "H1" }] } } },
	render: { as: "h1" },
	rules
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleBlock(type);
} }));
const BaseH2Plugin = createTSlatePlugin({
	key: "h2",
	node,
	parsers: { html: { deserializer: { rules: [{ validNodeName: "H2" }] } } },
	render: { as: "h2" },
	rules
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleBlock(type);
} }));
const BaseH3Plugin = createTSlatePlugin({
	key: "h3",
	node,
	parsers: { html: { deserializer: { rules: [{ validNodeName: "H3" }] } } },
	render: { as: "h3" },
	rules
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleBlock(type);
} }));
const BaseH4Plugin = createTSlatePlugin({
	key: "h4",
	node,
	parsers: { html: { deserializer: { rules: [{ validNodeName: "H4" }] } } },
	render: { as: "h4" },
	rules
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleBlock(type);
} }));
const BaseH5Plugin = createTSlatePlugin({
	key: "h5",
	node,
	parsers: { html: { deserializer: { rules: [{ validNodeName: "H5" }] } } },
	render: { as: "h5" },
	rules
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleBlock(type);
} }));
const BaseH6Plugin = createTSlatePlugin({
	key: "h6",
	node,
	parsers: { html: { deserializer: { rules: [{ validNodeName: "H6" }] } } },
	render: { as: "h6" },
	rules
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleBlock(type);
} }));
/** Enables support for headings with configurable levels (from 1 to 6). */
const BaseHeadingPlugin = createTSlatePlugin({
	key: "heading",
	options: { levels: [
		1,
		2,
		3,
		4,
		5,
		6
	] }
}).extend(({ plugin }) => {
	const { options: { levels } } = plugin;
	const headingPlugins = {
		1: BaseH1Plugin,
		2: BaseH2Plugin,
		3: BaseH3Plugin,
		4: BaseH4Plugin,
		5: BaseH5Plugin,
		6: BaseH6Plugin
	};
	return { plugins: (Array.isArray(levels) ? levels : Array.from({ length: levels || 6 }, (_, i) => i + 1)).map((level) => headingPlugins[level]) };
});

//#endregion
//#region src/lib/BaseHorizontalRulePlugin.ts
const BaseHorizontalRulePlugin = createSlatePlugin({
	key: KEYS.hr,
	node: {
		isElement: true,
		isVoid: true
	},
	parsers: { html: { deserializer: { rules: [{ validNodeName: "HR" }] } } },
	render: { as: "hr" }
});

//#endregion
//#region src/lib/BaseBoldPlugin.ts
/** Enables support for bold formatting */
const BaseBoldPlugin = createSlatePlugin({
	key: KEYS.bold,
	node: { isLeaf: true },
	parsers: { html: { deserializer: {
		rules: [{ validNodeName: ["STRONG", "B"] }, { validStyle: { fontWeight: [
			"600",
			"700",
			"bold"
		] } }],
		query: ({ element }) => !someHtmlElement(element, (node$1) => node$1.style.fontWeight === "normal")
	} } },
	render: { as: "strong" }
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleMark(type);
} }));

//#endregion
//#region src/lib/BaseCodePlugin.ts
/** Enables support for code formatting */
const BaseCodePlugin = createSlatePlugin({
	key: KEYS.code,
	node: { isLeaf: true },
	parsers: { html: { deserializer: {
		rules: [{ validNodeName: ["CODE"] }, { validStyle: { fontFamily: "Consolas" } }],
		query({ element }) {
			if (findHtmlParentElement(element, "P")?.style.fontFamily === "Consolas") return false;
			return !findHtmlParentElement(element, "PRE");
		}
	} } },
	render: { as: "code" },
	rules: { selection: { affinity: "hard" } }
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleMark(type);
} }));

//#endregion
//#region src/lib/BaseItalicPlugin.ts
/** Enables support for italic formatting. */
const BaseItalicPlugin = createSlatePlugin({
	key: KEYS.italic,
	node: { isLeaf: true },
	parsers: { html: { deserializer: {
		rules: [{ validNodeName: ["EM", "I"] }, { validStyle: { fontStyle: "italic" } }],
		query: ({ element }) => !someHtmlElement(element, (node$1) => node$1.style.fontStyle === "normal")
	} } },
	render: { as: "em" }
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleMark(type);
} }));

//#endregion
//#region src/lib/BaseStrikethroughPlugin.ts
/** Enables support for strikethrough formatting. */
const BaseStrikethroughPlugin = createSlatePlugin({
	key: KEYS.strikethrough,
	node: { isLeaf: true },
	parsers: { html: { deserializer: {
		rules: [{ validNodeName: [
			"S",
			"DEL",
			"STRIKE"
		] }, { validStyle: { textDecoration: "line-through" } }],
		query: ({ element }) => !someHtmlElement(element, (node$1) => node$1.style.textDecoration === "none")
	} } },
	render: { as: "s" },
	rules: { selection: { affinity: "directional" } }
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleMark(type);
} }));

//#endregion
//#region src/lib/BaseSubscriptPlugin.ts
/** Enables support for subscript formatting. */
const BaseSubscriptPlugin = createSlatePlugin({
	key: KEYS.sub,
	node: { isLeaf: true },
	parsers: { html: { deserializer: { rules: [{ validNodeName: ["SUB"] }, { validStyle: { verticalAlign: "sub" } }] } } },
	render: { as: "sub" },
	rules: { selection: { affinity: "directional" } }
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleMark(type, { remove: editor.getType(KEYS.sup) });
} }));

//#endregion
//#region src/lib/BaseSuperscriptPlugin.ts
/** Enables support for superscript formatting. */
const BaseSuperscriptPlugin = createSlatePlugin({
	key: KEYS.sup,
	node: { isLeaf: true },
	parsers: { html: { deserializer: { rules: [{ validNodeName: ["SUP"] }, { validStyle: { verticalAlign: "super" } }] } } },
	render: { as: "sup" },
	rules: { selection: { affinity: "directional" } }
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleMark(type, { remove: editor.getType(KEYS.sub) });
} }));

//#endregion
//#region src/lib/BaseUnderlinePlugin.ts
/** Enables support for underline formatting. */
const BaseUnderlinePlugin = createSlatePlugin({
	key: KEYS.underline,
	node: { isLeaf: true },
	parsers: { html: { deserializer: {
		rules: [{ validNodeName: ["U"] }, { validStyle: { textDecoration: ["underline"] } }],
		query: ({ element }) => !someHtmlElement(element, (node$1) => node$1.style.textDecoration === "none")
	} } },
	render: { as: "u" }
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleMark(type);
} }));

//#endregion
//#region src/lib/BaseBasicMarksPlugin.ts
const BaseBasicMarksPlugin = createSlatePlugin({ plugins: [
	BaseBoldPlugin,
	BaseCodePlugin,
	BaseItalicPlugin,
	BaseStrikethroughPlugin,
	BaseSubscriptPlugin,
	BaseSuperscriptPlugin,
	BaseUnderlinePlugin
] });

//#endregion
//#region src/lib/BaseHighlightPlugin.ts
/**
* Enables support for highlights, useful when reviewing content or highlighting
* it for future reference.
*/
const BaseHighlightPlugin = createSlatePlugin({
	key: KEYS.highlight,
	node: { isLeaf: true },
	parsers: { html: { deserializer: { rules: [{ validNodeName: ["MARK"] }] } } },
	render: { as: "mark" },
	rules: { selection: { affinity: "directional" } }
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleMark(type);
} }));

//#endregion
//#region src/lib/BaseKbdPlugin.ts
/** Enables support for code formatting */
const BaseKbdPlugin = createSlatePlugin({
	key: KEYS.kbd,
	node: { isLeaf: true },
	parsers: { html: { deserializer: { rules: [{ validNodeName: ["KBD"] }] } } },
	render: { as: "kbd" },
	rules: { selection: { affinity: "hard" } }
}).extendTransforms(({ editor, type }) => ({ toggle: () => {
	editor.tf.toggleMark(type);
} }));

//#endregion
export { BaseH6Plugin as _, BaseSuperscriptPlugin as a, BaseItalicPlugin as c, BaseHorizontalRulePlugin as d, BaseH1Plugin as f, BaseH5Plugin as g, BaseH4Plugin as h, BaseUnderlinePlugin as i, BaseCodePlugin as l, BaseH3Plugin as m, BaseHighlightPlugin as n, BaseSubscriptPlugin as o, BaseH2Plugin as p, BaseBasicMarksPlugin as r, BaseStrikethroughPlugin as s, BaseKbdPlugin as t, BaseBoldPlugin as u, BaseHeadingPlugin as v, BaseBlockquotePlugin as y };