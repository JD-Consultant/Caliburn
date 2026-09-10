import { it, expect } from "vitest";
import { transform } from "../src/transform.js";
import { createJdEditor } from "../src/profile.js";
import {
  profile,
  fixture,
  expectedMove,
  p,
  clone,
  byId,
  elements,
} from "./helpers.js";
const run = (base_value: any[], commands: any[]) =>
  transform({ profile, base_value, commands });
it("complete Task8 move fixed oracle", () => {
  const r = run(fixture, [
    {
      type: "move_content",
      target_id: "task-8",
      destination_id: "duty-1",
      placement: "append_child",
    },
  ]);
  expect(r.ok).toBe(true);
  if (r.ok) expect(r.value).toEqual(expectedMove);
});
it("all seven native branches", () => {
  const base = [p("a", "a"), p("b", "b")];
  for (const [cmd, expected] of [
    [
      {
        type: "replace_block_content",
        target_id: "a",
        content: [{ text: "x" }],
      },
      [p("a", "x"), p("b", "b")],
    ],
    [
      {
        type: "replace_selection",
        target_id: "a",
        range: {
          anchor: { path: [0, 0], offset: 0 },
          focus: { path: [0, 0], offset: 1 },
        },
        content: [{ text: "z" }],
      },
      [p("a", "z"), p("b", "b")],
    ],
    [
      {
        type: "set_properties",
        target_id: "a",
        set: { source_refs: ["issued:test"] },
      },
      [{ ...p("a", "a"), source_refs: ["issued:test"] }, p("b", "b")],
    ],
    [{ type: "remove_content", target_id: "a" }, [p("b", "b")]],
    [
      {
        type: "move_content",
        target_id: "a",
        destination_id: "b",
        placement: "after",
      },
      [p("b", "b"), p("a", "a")],
    ],
  ] as any) {
    const r = run(base, [cmd]);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.value).toEqual(expected);
      expect(r.native_operations.length).toBeGreaterThan(0);
    }
  }
  const r = run(base, [
    {
      type: "insert_content",
      target_id: "a",
      placement: "after",
      content: [{ type: "p", children: [{ text: "new" }] }],
    },
  ]);
  expect(r.ok).toBe(true);
  if (r.ok) {
    expect(r.value.map((n) => n.children)).toEqual([
      p("a", "a").children,
      p("n", "new").children,
      p("b", "b").children,
    ]);
    expect(new Set(elements(r.value).map((n) => n.id)).size).toBe(3);
  }
  const duty = byId(fixture, "duty-1");
  const u = run(fixture, [{ type: "unwrap_group", target_id: "duty-1" }]);
  expect(u.ok).toBe(true);
  if (u.ok) {
    const e = clone(fixture);
    const work = byId(e, "section-work");
    work.children.splice(
      work.children.findIndex((n: any) => n.id === "duty-1"),
      1,
      ...duty.children,
    );
    expect(u.value).toEqual(e);
  }
});
it("batch_failure_discards_candidate", () => {
  const before = clone(fixture);
  const r = run(fixture, [
    {
      type: "replace_block_content",
      target_id: "r2-1",
      content: [{ text: "changed" }],
    },
    { type: "remove_content", target_id: "missing" },
  ]);
  expect(r.ok).toBe(false);
  expect(r).not.toHaveProperty("value");
  expect(fixture).toEqual(before);
});
it("selection_is_resolved_by_app", () => {
  const value = [p("a"), p("b")];
  const command = {
    type: "replace_selection",
    target_id: "b",
    range: {
      anchor: { path: [1, 0], offset: 0 },
      focus: { path: [1, 0], offset: 4 },
    },
    content: [{ text: "新" }],
  };
  const r = run(value, [command]);
  expect(r.ok).toBe(true);
  if (r.ok) expect(r.value).toEqual([p("a"), p("b", "新")]);
  expect(run(value, [{ ...command, target_id: "a" }]).ok).toBe(false);
  expect(run(value, [{ ...command, range: undefined }]).ok).toBe(false);
});
it("native_operations_remain_json_safe", () => {
  const base = [p("a", "字", { bold: true })];
  const editor = createJdEditor(base);
  const operations: any[] = [];
  editor.onChange = () => {
    operations.push(...clone(editor.operations));
  };
  editor.tf.unsetNodes("bold", { at: [0, 0] });
  editor.onChange();
  const ops = JSON.parse(JSON.stringify(operations));
  expect(
    ops.some((o: any) => o.type === "set_node" && !("bold" in o.newProperties)),
  ).toBe(true);
  const fresh = createJdEditor(base);
  fresh.tf.withoutNormalizing(() => {
    for (const op of ops) fresh.apply(op);
  });
  expect(fresh.children).toEqual([p("a", "字")]);
});
it("semantic deletion and unwrap enforce final relations", () => {
  expect(
    run(fixture, [{ type: "remove_content", target_id: "section-knowledge" }])
      .ok,
  ).toBe(false);
  expect(run(fixture, [{ type: "unwrap_group", target_id: "task-1" }]).ok).toBe(
    false,
  );
  const r = run(fixture, [
    { type: "unwrap_group", target_id: "f03-task-1-outcomes" },
    { type: "unwrap_group", target_id: "f03-task-1-requirements" },
    { type: "unwrap_group", target_id: "task-1" },
  ]);
  expect(r.ok).toBe(true);
  const commands = elements(fixture)
    .filter((n) => n.type === "jd_task")
    .map((n) => ({
      type: "set_properties",
      target_id: n.id,
      unset: ["knowledge_ids"],
    }));
  expect(
    run(fixture, [
      ...commands,
      { type: "remove_content", target_id: "section-knowledge" },
    ]).ok,
  ).toBe(true);
});
it("single_intent_properties", () => {
  expect(
    run(fixture, [
      {
        type: "set_properties",
        target_id: "task-1",
        set: { knowledge_ids: [] },
        unset: ["knowledge_ids"],
      },
    ]).ok,
  ).toBe(false);
  expect(
    run(fixture, [
      {
        type: "set_properties",
        target_id: "task-1",
        set: { attributes: { colspan: "2" } },
      },
    ]).ok,
  ).toBe(false);
});
