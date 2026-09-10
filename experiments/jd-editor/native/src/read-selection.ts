import { isDeepStrictEqual } from "node:util";
import { NodeApi, type TRange, type TElement } from "platejs";
import type {
  JdPlateReadSelectionRequest,
  JdPlateReadSelectionResult,
  SlateRange,
} from "@caliburn/jd-editor-contract";
import { createJdEditor, type JdEditor } from "./profile.js";
import { assertContract, failure, JdInputError } from "./schema.js";
export function resolveSelection(
  editor: JdEditor,
  range: SlateRange,
  targetId?: string,
): string {
  assertContract("SlateRange", range);
  let id: string | undefined;
  let blockPath: string | undefined;
  for (const point of [range.anchor, range.focus]) {
    const leaf = NodeApi.get(editor, point.path);
    if (
      !leaf ||
      typeof leaf.text !== "string" ||
      point.offset > leaf.text.length
    )
      throw new JdInputError(
        "invalid_selection",
        "Selection must address an existing text offset.",
      );
    const parentPath = point.path.slice(0, -1);
    const parent = NodeApi.get(editor, parentPath);
    if (
      !parent ||
      !["p", "h1", "h2", "h3", "lic"].includes(String(parent.type))
    )
      throw new JdInputError(
        "invalid_selection",
        "Selection must be in a supported text block.",
      );
    if (blockPath !== undefined && blockPath !== JSON.stringify(parentPath))
      throw new JdInputError(
        "invalid_selection",
        "Selection must stay within one text block.",
      );
    blockPath = JSON.stringify(parentPath);
    id = parent.id as string;
  }
  if (targetId !== undefined && targetId !== id)
    throw new JdInputError(
      "invalid_selection",
      "Selection does not match its resolved target.",
    );
  return id!;
}
export function readJdSelection(
  request: JdPlateReadSelectionRequest,
): JdPlateReadSelectionResult {
  try {
    assertContract("JdPlateReadSelectionRequest", request);
    const editor = createJdEditor(request.value);
    editor.tf.normalize({ force: true });
    if (!isDeepStrictEqual(editor.children, request.value))
      throw new JdInputError(
        "noncanonical_value",
        "Selection requires an unchanged canonical value.",
      );
    const target_id = resolveSelection(editor, request.range);
    const fragment = editor.api.fragment(request.range as TRange);
    const selected = [
      ...NodeApi.descendants({ children: fragment } as TElement),
    ].find(([node]) => node.id === target_id)?.[0];
    if (!selected)
      throw new JdInputError(
        "invalid_selection",
        "Native fragment did not contain its target block.",
      );
    const out = {
      ok: true as const,
      target_id,
      range: structuredClone(request.range),
      fragment: [selected],
    };
    assertContract("JdPlateReadSelectionResult", out);
    return out as JdPlateReadSelectionResult;
  } catch (e) {
    return failure(e);
  }
}
