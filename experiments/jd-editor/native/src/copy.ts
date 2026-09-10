import { NodeApi, type TElement, type SlateEditor } from "platejs";
import { assertJdValue, JdInputError } from "./schema.js";
/** Local same-document UI copy helper, not a model command or Node wire entry. */
export function copyJdElements(
  editor: SlateEditor,
  sourceIds: string[],
  at: number[],
): void {
  assertJdValue(editor.children);
  const sources = sourceIds.map((id) => {
    const matches = [
      ...editor.api.nodes({
        at: [],
        match: (n: { id?: unknown }) => n.id === id,
      }),
    ];
    if (matches.length !== 1)
      throw new JdInputError("target_missing", `Copy target ${id} is missing.`);
    return matches[0][0] as TElement;
  });
  const oldIds: string[] = [];
  const copy = structuredClone(sources);
  const strip = (nodes: TElement[]) => {
    for (const n of nodes) {
      oldIds.push(n.id as string);
      delete n.id;
      for (const child of n.children)
        if ("children" in child) strip([child as TElement]);
    }
  };
  strip(copy);
  editor.tf.withoutNormalizing(() => {
    editor.tf.insertNodes(copy, { at });
    const copied: TElement[] = [];
    for (let i = 0; i < copy.length; i++)
      copied.push(
        NodeApi.get(editor, [...at.slice(0, -1), at.at(-1)! + i]) as TElement,
      );
    const entries: Array<[TElement, number[]]> = [];
    const gather = (nodes: TElement[], parent: number[], start = 0) =>
      nodes.forEach((n, i) => {
        const path = [...parent, start + i];
        entries.push([n, path]);
        n.children.forEach((child, j) => {
          if ("children" in child) gather([child as TElement], path, j);
        });
      });
    gather(copied, at.slice(0, -1), at.at(-1)!);
    const ids = new Map(
      oldIds.map((id, i) => [id, entries[i][0].id as string]),
    );
    for (const [node, path] of entries)
      if (node.type === "jd_task") {
        const set: Record<string, string[]> = {};
        for (const field of ["knowledge_ids", "skill_ids"])
          if (Array.isArray(node[field]))
            set[field] = (node[field] as string[]).map(
              (id) => ids.get(id) ?? id,
            );
        if (Object.keys(set).length) editor.tf.setNodes(set, { at: path });
      }
  });
  assertJdValue(editor.children);
}
