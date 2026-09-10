import { NodeApi, PathApi, type Operation } from "platejs";
import type { JdEditor } from "./profile.js";
/** Observe only actual native operations; never compare or mutate document trees. */
export function observeAffectedIds(editor: JdEditor): Set<string> {
  const ids = new Set<string>();
  const collect = (node: unknown, subtree = false) => {
    if (!node || typeof node !== "object") return;
    const n = node as { type?: unknown; id?: unknown; children?: unknown[] };
    if (typeof n.type === "string" && typeof n.id === "string") ids.add(n.id);
    if (subtree && n.children)
      for (const child of n.children) collect(child, true);
  };
  const at = (path: number[], subtree = false) =>
    collect(NodeApi.get(editor, path), subtree);
  const parents = (path: number[]) => {
    for (const parent of PathApi.ancestors(path)) at(parent);
  };
  const apply = editor.apply as (op: Operation) => void;
  const observed = (op: Operation) => {
    const start = editor.operations.length;
    if (
      op.type !== "set_selection" &&
      !(op.type === "move_node" && PathApi.equals(op.path, op.newPath))
    ) {
      parents(op.path);
      switch (op.type) {
        case "insert_node":
          break;
        case "remove_node":
          collect(op.node, true);
          break;
        case "move_node":
          at(op.path, true);
          parents(op.newPath);
          break;
        case "merge_node":
          at(op.path, true);
          {
            const previous = PathApi.previous(op.path);
            if (previous) at(previous);
          }
          break;
        case "split_node": {
          const node = NodeApi.get(editor, op.path);
          collect(node);
          if (node && "children" in node && Array.isArray(node.children))
            for (const child of node.children.slice(op.position))
              collect(child, true);
          break;
        }
        default:
          at(op.path);
      }
    }
    apply(op);
    // NodeId may replace incoming insert/split payloads. Read the real applied
    // operations, including recursively applied normalization, for generated IDs.
    for (const actual of editor.operations.slice(start)) {
      if (actual.type === "insert_node") collect(actual.node, true);
      else if (
        actual.type === "split_node" &&
        typeof actual.properties.id === "string"
      )
        ids.add(actual.properties.id);
      else if (
        actual.type === "set_node" &&
        typeof actual.newProperties.id === "string"
      )
        ids.add(actual.newProperties.id);
    }
  };
  editor.apply = observed;
  editor.tf.apply = observed;
  return ids;
}
