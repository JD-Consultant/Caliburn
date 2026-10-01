import { _ as BaseH6Plugin, a as BaseSuperscriptPlugin, c as BaseItalicPlugin, d as BaseHorizontalRulePlugin, f as BaseH1Plugin, g as BaseH5Plugin, h as BaseH4Plugin, i as BaseUnderlinePlugin, l as BaseCodePlugin, m as BaseH3Plugin, n as BaseHighlightPlugin, o as BaseSubscriptPlugin, p as BaseH2Plugin, r as BaseBasicMarksPlugin, s as BaseStrikethroughPlugin, t as BaseKbdPlugin, u as BaseBoldPlugin, v as BaseHeadingPlugin, y as BaseBlockquotePlugin } from "./BaseKbdPlugin-C5TGzG3P.js";
import { KEYS, createRuleFactory, createSlatePlugin } from "platejs";

//#region src/lib/BaseBasicBlocksPlugin.ts
const BaseBasicBlocksPlugin = createSlatePlugin({ plugins: [
	BaseBlockquotePlugin,
	BaseHeadingPlugin,
	BaseHorizontalRulePlugin
] });

//#endregion
//#region src/lib/BasicBlockRules.ts
const HEADING_KEY_RE = /^h([1-6])$/;
const THEMATIC_BREAK_DASH_RE = /^(--|—)$/;
const getHeadingMarkdownPrefix = (pluginKey) => {
	const match = HEADING_KEY_RE.exec(pluginKey);
	if (!match) return;
	return "#".repeat(Number(match[1]));
};
const HeadingRules = { markdown: createRuleFactory({
	type: "blockStart",
	trigger: " ",
	match: ({ pluginKey }) => getHeadingMarkdownPrefix(pluginKey)
}) };
const BlockquoteRules = { markdown: createRuleFactory({
	type: "blockStart",
	marker: ">",
	trigger: " ",
	enabled: ({ editor }) => !editor.api.some({ match: { type: [editor.getType(KEYS.codeBlock)] } }),
	match: ({ marker }) => marker,
	apply: ({ editor }, match) => {
		editor.tf.delete({ at: match.range });
		editor.tf.wrapNodes({
			children: [],
			type: editor.getType(KEYS.blockquote)
		}, { match: (node) => editor.api.isBlock(node) });
		return true;
	}
}) };
const HorizontalRuleRules = { markdown: createRuleFactory({
	type: "blockStart",
	variant: "-",
	match: ({ variant }) => variant === "_" ? "___" : THEMATIC_BREAK_DASH_RE,
	trigger: ({ variant }) => variant === "_" ? " " : "-",
	apply: ({ editor, variant }) => {
		if (variant === "_") editor.tf.deleteBackward("character");
		editor.tf.setNodes({ type: KEYS.hr });
		editor.tf.insertNodes({
			children: [{ text: "" }],
			type: KEYS.p
		});
		return true;
	}
}) };

//#endregion
//#region src/lib/BasicMarkRules.ts
const MARK_COMBO_CONFIG = {
	boldItalic: {
		end: "*",
		marks: [KEYS.bold, KEYS.italic],
		start: "**",
		trigger: "*"
	},
	boldItalicUnderline: {
		end: "***",
		marks: [
			KEYS.underline,
			KEYS.bold,
			KEYS.italic
		],
		start: "___",
		trigger: "*"
	},
	boldUnderline: {
		end: "**",
		marks: [KEYS.underline, KEYS.bold],
		start: "__",
		trigger: "*"
	},
	italicUnderline: {
		end: "*",
		marks: [KEYS.underline, KEYS.italic],
		start: "__",
		trigger: "*"
	}
};
const BoldRules = { markdown: createRuleFactory({
	type: "mark",
	variant: "*",
	end: ({ variant }) => variant,
	start: ({ variant }) => variant.repeat(2),
	trigger: ({ variant }) => variant
}) };
const ItalicRules = { markdown: createRuleFactory({
	type: "mark",
	variant: "*",
	start: ({ variant }) => variant,
	trigger: ({ variant }) => variant
}) };
const UnderlineRules = { markdown: createRuleFactory({
	type: "mark",
	end: "_",
	start: "__",
	trigger: "_"
}) };
const MarkComboRules = { markdown: createRuleFactory({
	type: "mark",
	end: ({ variant }) => MARK_COMBO_CONFIG[variant].end,
	marks: ({ variant }) => MARK_COMBO_CONFIG[variant].marks,
	start: ({ variant }) => MARK_COMBO_CONFIG[variant].start,
	trigger: ({ variant }) => MARK_COMBO_CONFIG[variant].trigger
}) };
const CodeRules = { markdown: createRuleFactory({
	type: "mark",
	start: "`",
	trigger: "`"
}) };
const StrikethroughRules = { markdown: createRuleFactory({
	type: "mark",
	end: "~",
	start: "~~",
	trigger: "~"
}) };
const SubscriptRules = { markdown: createRuleFactory({
	type: "mark",
	start: "~",
	trigger: "~"
}) };
const SuperscriptRules = { markdown: createRuleFactory({
	type: "mark",
	start: "^",
	trigger: "^"
}) };
const HighlightRules = { markdown: createRuleFactory({
	type: "mark",
	variant: "==",
	end: ({ variant }) => variant === "≡" ? void 0 : "=",
	start: ({ variant }) => variant === "≡" ? "≡" : "==",
	trigger: ({ variant }) => variant === "≡" ? "≡" : "="
}) };

//#endregion
export { BaseBasicBlocksPlugin, BaseBasicMarksPlugin, BaseBlockquotePlugin, BaseBoldPlugin, BaseCodePlugin, BaseH1Plugin, BaseH2Plugin, BaseH3Plugin, BaseH4Plugin, BaseH5Plugin, BaseH6Plugin, BaseHeadingPlugin, BaseHighlightPlugin, BaseHorizontalRulePlugin, BaseItalicPlugin, BaseKbdPlugin, BaseStrikethroughPlugin, BaseSubscriptPlugin, BaseSuperscriptPlugin, BaseUnderlinePlugin, BlockquoteRules, BoldRules, CodeRules, HeadingRules, HighlightRules, HorizontalRuleRules, ItalicRules, MarkComboRules, StrikethroughRules, SubscriptRules, SuperscriptRules, UnderlineRules };