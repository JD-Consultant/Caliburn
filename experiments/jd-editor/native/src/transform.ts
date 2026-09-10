import { PathApi, type TElement, type TRange } from "platejs";
import type {
  JdPlateTransformRequest,
  JdPlateTransformResult,
  JdResolvedEditCommand,
} from "@caliburn/jd-editor-contract";
import { createJdEditor, capture, type JdEditor } from "./profile.js";
import { assertContract, failure, JdInputError } from "./schema.js";
import { resolveSelection } from "./read-selection.js";
import { result } from "./validate.js";
import { mapCommand, type ResolvedCommand } from "./command-mapper.js";
function locate(editor: JdEditor, id: string): [TElement, number[]] {
  const found = [
    ...editor.api.nodes({
      at: [],
      match: (n: { id?: unknown }) => n.id === id,
    }),
  ];
  if (found.length !== 1)
    throw new JdInputError(
      "target_missing",
      `Resolved target ${id} is missing.`,
    );
  return found[0] as [TElement, number[]];
}
function destination(editor: JdEditor, id: string, placement: string) {
  const [node, path] = locate(editor, id);
  if (placement === "before") return path;
  if (placement === "after") return PathApi.next(path);
  if (placement === "prepend_child") return [...path, 0];
  return [...path, node.children.length];
}
function applyCommand(editor: JdEditor, command: ResolvedCommand) {
  const [node, path] = locate(editor, command.target_id);
  switch (command.type) {
    case "insert_content":
      editor.tf.insertNodes(structuredClone(command.content) as TElement[], {
        at: destination(editor, command.target_id, command.placement),
      });
      break;
    case "remove_content":
      editor.tf.removeNodes({ at: path });
      break;
    case "move_content": {
      let to = destination(editor, command.destination_id, command.placement);
      if (
        command.target_id === command.destination_id ||
        PathApi.isAncestor(path, to)
      )
        throw new JdInputError(
          "invalid_input",
          "Cannot move content into itself.",
        );
      // Native move_node uses a final sibling index, while parent paths are
      // transformed by Slate itself. Adjust only the same-parent insertion gap.
      if (PathApi.isSibling(path, to) && PathApi.isBefore(path, to))
        to = PathApi.previous(to)!;
      if (!PathApi.equals(path, to)) editor.tf.moveNodes({ at: path, to });
      break;
    }
    case "unwrap_group":
      if (
        ![
          "jd_section",
          "jd_duty",
          "jd_task",
          "jd_outcomes",
          "jd_requirements",
          "jd_knowledge",
          "jd_skill",
          "blockquote",
        ].includes(node.type)
      )
        throw new JdInputError(
          "invalid_input",
          "Target is not a supported group.",
        );
      editor.tf.unwrapNodes({ at: path });
      break;
    case "replace_block_content": {
      if (!["p", "h1", "h2", "h3", "lic"].includes(node.type))
        throw new JdInputError(
          "invalid_input",
          "Target must be a supported text block.",
        );
      for (let i = node.children.length - 1; i >= 0; i--)
        editor.tf.removeNodes({ at: [...path, i] });
      editor.tf.insertNodes(structuredClone(command.content), {
        at: [...path, 0],
      });
      break;
    }
    case "replace_selection": {
      resolveSelection(editor, command.range, command.target_id);
      editor.tf.select(command.range as TRange);
      editor.tf.delete({ at: command.range as TRange });
      if (command.content.length)
        editor.tf.insertNodes(structuredClone(command.content), {
          at: editor.selection!,
        });
      break;
    }
    case "set_properties": {
      const set = structuredClone(command.set ?? {}) as Record<string, unknown>;
      const unset = [...(command.unset ?? [])];
      const attrs = { ...((node.attributes ?? {}) as Record<string, string>) };
      let touched = false;
      for (const [key, html] of [
        ["colSpan", "colspan"],
        ["rowSpan", "rowspan"],
      ]) {
        if (key in set && html in attrs) {
          attrs[html] = String(set[key]);
          touched = true;
        }
        if (unset.includes(key as (typeof unset)[number]) && html in attrs) {
          delete attrs[html];
          touched = true;
        }
      }
      if (Object.keys(set).length) editor.tf.setNodes(set, { at: path });
      if (unset.length) editor.tf.unsetNodes(unset, { at: path });
      if (touched) {
        if (Object.keys(attrs).length)
          editor.tf.setNodes({ attributes: attrs }, { at: path });
        else editor.tf.unsetNodes("attributes", { at: path });
      }
      break;
    }
  }
}
export function transform(
  request: JdPlateTransformRequest,
): JdPlateTransformResult {
  let index: number | null = null;
  try {
    assertContract("JdPlateTransformRequest", request);
    const editor = createJdEditor(request.base_value);
    const c = capture(editor);
    editor.tf.withoutNormalizing(() => {
      for (const [i, command] of request.commands.entries()) {
        index = i;
        applyCommand(editor, mapCommand(command));
      }
    });
    editor.tf.normalize({ force: true });
    c.flush();
    return result(editor, request.base_value, c.operations, c.affectedIds);
  } catch (e) {
    return failure(e, index);
  }
}
