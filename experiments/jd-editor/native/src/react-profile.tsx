import { createPlateEditor, createPlatePlugin } from "platejs/react";
import {
  HeadingPlugin,
  BlockquotePlugin,
  HorizontalRulePlugin,
  BoldPlugin,
  ItalicPlugin,
  UnderlinePlugin,
  StrikethroughPlugin,
} from "@platejs/basic-nodes/react";
import { ListPlugin } from "@platejs/list-classic/react";
import { TablePlugin } from "@platejs/table/react";
import type { JdDocumentValue } from "@caliburn/jd-editor-contract";
import { semanticTypes, nodeId } from "./profile.js";
import { assertJdValue } from "./schema.js";
export const jdReactPlugins = [
  HeadingPlugin.configure({ options: { levels: [1, 2, 3] } }),
  BlockquotePlugin,
  HorizontalRulePlugin,
  BoldPlugin,
  ItalicPlugin,
  UnderlinePlugin,
  StrikethroughPlugin,
  ListPlugin,
  TablePlugin,
  ...semanticTypes.map((key) =>
    createPlatePlugin({ key, node: { isElement: true } }),
  ),
];
export function createJdReactEditor(value: JdDocumentValue) {
  assertJdValue(value);
  return createPlateEditor({
    plugins: jdReactPlugins,
    nodeId,
    value: structuredClone(value),
  });
}
