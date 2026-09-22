import * as platejs100 from "platejs";
import { PluginConfig } from "platejs";

//#region src/lib/BaseBasicBlocksPlugin.d.ts
declare const BaseBasicBlocksPlugin: platejs100.SlatePlugin<platejs100.PluginConfig<any, {}, {}, {}, {}>>;
//#endregion
//#region src/lib/BaseBasicMarksPlugin.d.ts
declare const BaseBasicMarksPlugin: platejs100.SlatePlugin<platejs100.PluginConfig<any, {}, {}, {}, {}>>;
//#endregion
//#region src/lib/BaseBlockquotePlugin.d.ts
/** Enables support for block quotes, useful for quotations and passages. */
declare const BaseBlockquotePlugin: platejs100.SlatePlugin<platejs100.PluginConfig<"blockquote", {}, {}, Record<"blockquote", {
  toggle: () => void;
}>, {}>>;
//#endregion
//#region src/lib/BaseBoldPlugin.d.ts
/** Enables support for bold formatting */
declare const BaseBoldPlugin: platejs100.SlatePlugin<platejs100.PluginConfig<"bold", {}, {}, Record<"bold", {
  toggle: () => void;
}>, {}>>;
//#endregion
//#region src/lib/BaseCodePlugin.d.ts
/** Enables support for code formatting */
declare const BaseCodePlugin: platejs100.SlatePlugin<platejs100.PluginConfig<"code", {}, {}, Record<"code", {
  toggle: () => void;
}>, {}>>;
//#endregion
//#region src/lib/BaseHeadingPlugin.d.ts
type HeadingConfig = PluginConfig<'heading', {
  /** Heading levels supported from 1 to `levels` */
  levels?: HeadingLevel | HeadingLevel[];
}>;
type HeadingLevel = 1 | 2 | 3 | 4 | 5 | 6;
declare const BaseH1Plugin: platejs100.SlatePlugin<PluginConfig<any, {}, {}, Record<any, {
  toggle: () => void;
}>, {}>>;
declare const BaseH2Plugin: platejs100.SlatePlugin<PluginConfig<any, {}, {}, Record<any, {
  toggle: () => void;
}>, {}>>;
declare const BaseH3Plugin: platejs100.SlatePlugin<PluginConfig<any, {}, {}, Record<any, {
  toggle: () => void;
}>, {}>>;
declare const BaseH4Plugin: platejs100.SlatePlugin<PluginConfig<any, {}, {}, Record<any, {
  toggle: () => void;
}>, {}>>;
declare const BaseH5Plugin: platejs100.SlatePlugin<PluginConfig<any, {}, {}, Record<any, {
  toggle: () => void;
}>, {}>>;
declare const BaseH6Plugin: platejs100.SlatePlugin<PluginConfig<any, {}, {}, Record<any, {
  toggle: () => void;
}>, {}>>;
/** Enables support for headings with configurable levels (from 1 to 6). */
declare const BaseHeadingPlugin: platejs100.SlatePlugin<PluginConfig<"heading", {
  /** Heading levels supported from 1 to `levels` */
  levels?: HeadingLevel | HeadingLevel[];
}, {}, {}, {}>>;
//#endregion
//#region src/lib/BaseHighlightPlugin.d.ts
/**
 * Enables support for highlights, useful when reviewing content or highlighting
 * it for future reference.
 */
declare const BaseHighlightPlugin: platejs100.SlatePlugin<platejs100.PluginConfig<"highlight", {}, {}, Record<"highlight", {
  toggle: () => void;
}>, {}>>;
//#endregion
//#region src/lib/BaseHorizontalRulePlugin.d.ts
declare const BaseHorizontalRulePlugin: platejs100.SlatePlugin<platejs100.PluginConfig<"hr", {}, {}, {}, {}>>;
//#endregion
//#region src/lib/BaseItalicPlugin.d.ts
/** Enables support for italic formatting. */
declare const BaseItalicPlugin: platejs100.SlatePlugin<platejs100.PluginConfig<"italic", {}, {}, Record<"italic", {
  toggle: () => void;
}>, {}>>;
//#endregion
//#region src/lib/BaseKbdPlugin.d.ts
/** Enables support for code formatting */
declare const BaseKbdPlugin: platejs100.SlatePlugin<platejs100.PluginConfig<"kbd", {}, {}, Record<"kbd", {
  toggle: () => void;
}>, {}>>;
//#endregion
//#region src/lib/BaseStrikethroughPlugin.d.ts
/** Enables support for strikethrough formatting. */
declare const BaseStrikethroughPlugin: platejs100.SlatePlugin<platejs100.PluginConfig<"strikethrough", {}, {}, Record<"strikethrough", {
  toggle: () => void;
}>, {}>>;
//#endregion
//#region src/lib/BaseSubscriptPlugin.d.ts
/** Enables support for subscript formatting. */
declare const BaseSubscriptPlugin: platejs100.SlatePlugin<platejs100.PluginConfig<"subscript", {}, {}, Record<"subscript", {
  toggle: () => void;
}>, {}>>;
//#endregion
//#region src/lib/BaseSuperscriptPlugin.d.ts
/** Enables support for superscript formatting. */
declare const BaseSuperscriptPlugin: platejs100.SlatePlugin<platejs100.PluginConfig<"superscript", {}, {}, Record<"superscript", {
  toggle: () => void;
}>, {}>>;
//#endregion
//#region src/lib/BaseUnderlinePlugin.d.ts
/** Enables support for underline formatting. */
declare const BaseUnderlinePlugin: platejs100.SlatePlugin<platejs100.PluginConfig<"underline", {}, {}, Record<"underline", {
  toggle: () => void;
}>, {}>>;
//#endregion
//#region src/lib/BasicBlockRules.d.ts
declare const HeadingRules: {
  markdown: (options?: {
    enabled?: ((context: platejs100.SelectionInputRuleContext<platejs100.SlateEditor> | platejs100.InsertTextInputRuleContext<platejs100.SlateEditor> | platejs100.InsertBreakInputRuleContext<platejs100.SlateEditor> | platejs100.InsertDataInputRuleContext<platejs100.SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs100.AnyInputRule<unknown>;
};
declare const BlockquoteRules: {
  markdown: (options?: {
    marker?: string | undefined;
    enabled?: ((context: platejs100.SelectionInputRuleContext<platejs100.SlateEditor> | platejs100.InsertTextInputRuleContext<platejs100.SlateEditor> | platejs100.InsertBreakInputRuleContext<platejs100.SlateEditor> | platejs100.InsertDataInputRuleContext<platejs100.SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs100.AnyInputRule<unknown>;
};
declare const HorizontalRuleRules: {
  markdown: (options?: {
    variant?: "_" | "-" | undefined;
    enabled?: ((context: platejs100.SelectionInputRuleContext<platejs100.SlateEditor> | platejs100.InsertTextInputRuleContext<platejs100.SlateEditor> | platejs100.InsertBreakInputRuleContext<platejs100.SlateEditor> | platejs100.InsertDataInputRuleContext<platejs100.SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs100.AnyInputRule<unknown>;
};
//#endregion
//#region src/lib/BasicMarkRules.d.ts
type MarkComboVariant = 'boldItalic' | 'boldUnderline' | 'boldItalicUnderline' | 'italicUnderline';
declare const BoldRules: {
  markdown: (options?: {
    variant?: "_" | "*" | undefined;
    enabled?: ((context: platejs100.SelectionInputRuleContext<platejs100.SlateEditor> | platejs100.InsertTextInputRuleContext<platejs100.SlateEditor> | platejs100.InsertBreakInputRuleContext<platejs100.SlateEditor> | platejs100.InsertDataInputRuleContext<platejs100.SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs100.AnyInputRule<unknown>;
};
declare const ItalicRules: {
  markdown: (options?: {
    variant?: "_" | "*" | undefined;
    enabled?: ((context: platejs100.SelectionInputRuleContext<platejs100.SlateEditor> | platejs100.InsertTextInputRuleContext<platejs100.SlateEditor> | platejs100.InsertBreakInputRuleContext<platejs100.SlateEditor> | platejs100.InsertDataInputRuleContext<platejs100.SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs100.AnyInputRule<unknown>;
};
declare const UnderlineRules: {
  markdown: (options?: {
    enabled?: ((context: platejs100.SelectionInputRuleContext<platejs100.SlateEditor> | platejs100.InsertTextInputRuleContext<platejs100.SlateEditor> | platejs100.InsertBreakInputRuleContext<platejs100.SlateEditor> | platejs100.InsertDataInputRuleContext<platejs100.SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs100.AnyInputRule<unknown>;
};
declare const MarkComboRules: {
  markdown: (options: {
    variant: MarkComboVariant;
    enabled?: ((context: platejs100.SelectionInputRuleContext<platejs100.SlateEditor> | platejs100.InsertTextInputRuleContext<platejs100.SlateEditor> | platejs100.InsertBreakInputRuleContext<platejs100.SlateEditor> | platejs100.InsertDataInputRuleContext<platejs100.SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  }) => platejs100.AnyInputRule<unknown>;
};
declare const CodeRules: {
  markdown: (options?: {
    enabled?: ((context: platejs100.SelectionInputRuleContext<platejs100.SlateEditor> | platejs100.InsertTextInputRuleContext<platejs100.SlateEditor> | platejs100.InsertBreakInputRuleContext<platejs100.SlateEditor> | platejs100.InsertDataInputRuleContext<platejs100.SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs100.AnyInputRule<unknown>;
};
declare const StrikethroughRules: {
  markdown: (options?: {
    enabled?: ((context: platejs100.SelectionInputRuleContext<platejs100.SlateEditor> | platejs100.InsertTextInputRuleContext<platejs100.SlateEditor> | platejs100.InsertBreakInputRuleContext<platejs100.SlateEditor> | platejs100.InsertDataInputRuleContext<platejs100.SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs100.AnyInputRule<unknown>;
};
declare const SubscriptRules: {
  markdown: (options?: {
    enabled?: ((context: platejs100.SelectionInputRuleContext<platejs100.SlateEditor> | platejs100.InsertTextInputRuleContext<platejs100.SlateEditor> | platejs100.InsertBreakInputRuleContext<platejs100.SlateEditor> | platejs100.InsertDataInputRuleContext<platejs100.SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs100.AnyInputRule<unknown>;
};
declare const SuperscriptRules: {
  markdown: (options?: {
    enabled?: ((context: platejs100.SelectionInputRuleContext<platejs100.SlateEditor> | platejs100.InsertTextInputRuleContext<platejs100.SlateEditor> | platejs100.InsertBreakInputRuleContext<platejs100.SlateEditor> | platejs100.InsertDataInputRuleContext<platejs100.SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs100.AnyInputRule<unknown>;
};
declare const HighlightRules: {
  markdown: (options?: {
    variant?: "==" | "≡" | undefined;
    enabled?: ((context: platejs100.SelectionInputRuleContext<platejs100.SlateEditor> | platejs100.InsertTextInputRuleContext<platejs100.SlateEditor> | platejs100.InsertBreakInputRuleContext<platejs100.SlateEditor> | platejs100.InsertDataInputRuleContext<platejs100.SlateEditor>) => boolean) | undefined;
    priority?: number | undefined;
  } | undefined) => platejs100.AnyInputRule<unknown>;
};
//#endregion
export { BaseCodePlugin as A, BaseH3Plugin as C, BaseHeadingPlugin as D, BaseH6Plugin as E, BaseBlockquotePlugin as M, BaseBasicMarksPlugin as N, HeadingConfig as O, BaseBasicBlocksPlugin as P, BaseH2Plugin as S, BaseH5Plugin as T, BaseKbdPlugin as _, MarkComboRules as a, BaseHighlightPlugin as b, SuperscriptRules as c, HeadingRules as d, HorizontalRuleRules as f, BaseStrikethroughPlugin as g, BaseSubscriptPlugin as h, ItalicRules as i, BaseBoldPlugin as j, HeadingLevel as k, UnderlineRules as l, BaseSuperscriptPlugin as m, CodeRules as n, StrikethroughRules as o, BaseUnderlinePlugin as p, HighlightRules as r, SubscriptRules as s, BoldRules as t, BlockquoteRules as u, BaseItalicPlugin as v, BaseH4Plugin as w, BaseH1Plugin as x, BaseHorizontalRulePlugin as y };