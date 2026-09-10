import {
  createSlateEditor,
  createSlatePlugin,
  type Value,
  type Operation,
} from "platejs";
import {
  BaseHeadingPlugin,
  BaseBlockquotePlugin,
  BaseHorizontalRulePlugin,
  BaseBoldPlugin,
  BaseItalicPlugin,
  BaseUnderlinePlugin,
  BaseStrikethroughPlugin,
} from "@platejs/basic-nodes";
import { BaseListPlugin } from "@platejs/list-classic";
import { BaseTablePlugin } from "@platejs/table";
import type { JdDocumentValue } from "@caliburn/jd-editor-contract";
import { assertJdValue } from "./schema.js";
import { observeAffectedIds } from "./affected.js";
export const semanticTypes = [
  "jd_section",
  "jd_duty",
  "jd_task",
  "jd_outcomes",
  "jd_requirements",
  "jd_knowledge",
  "jd_skill",
] as const;
export const nodeId = { reuseId: true, initialValueIds: "always" as const };
export const jdPlugins = [
  BaseHeadingPlugin.configure({ options: { levels: [1, 2, 3] } }),
  BaseBlockquotePlugin,
  BaseHorizontalRulePlugin,
  BaseBoldPlugin,
  BaseItalicPlugin,
  BaseUnderlinePlugin,
  BaseStrikethroughPlugin,
  BaseListPlugin,
  BaseTablePlugin,
  ...semanticTypes.map((key) =>
    createSlatePlugin({ key, node: { isElement: true } }),
  ),
];
export function createJdEditor(value: JdDocumentValue) {
  assertJdValue(value);
  return createSlateEditor({
    plugins: jdPlugins,
    nodeId,
    value: structuredClone(value) as Value,
  });
}
export type JdEditor = ReturnType<typeof createJdEditor>;
/** Capture the real operation list synchronously before Slate's deferred flush. */
export function capture(editor: JdEditor) {
  const operations: Operation[] = [];
  const affectedIds = observeAffectedIds(editor);
  let count = 0;
  const onChange = editor.api.onChange;
  editor.api.onChange = (...args: Parameters<typeof onChange>) => {
    operations.push(...structuredClone(editor.operations.slice(count)));
    count = editor.operations.length;
    onChange(...args);
  };
  return { operations, affectedIds, flush: () => editor.api.onChange() };
}
