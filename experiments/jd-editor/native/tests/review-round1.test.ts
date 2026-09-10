import { it, expect } from "vitest";
import { transform } from "../src/transform.js";
import { validateJdValue, result } from "../src/validate.js";
import { createJdEditor, capture } from "../src/profile.js";
import { profile, p, clone } from "./helpers.js";
const base = [p("a", "a", { bold: true }), p("b", "b"), p("c", "c")];
function check(value: any[], commands: any[], expected: any[]) {
  const baseline = clone(value);
  const r = transform({ profile, base_value: value as any, commands });
  expect(r.ok).toBe(true);
  if (!r.ok) throw Error(r.error.message);
  expect(r.value).toEqual(expected);
  const e = createJdEditor(value as any);
  e.tf.withoutNormalizing(() => {
    for (const op of JSON.parse(JSON.stringify(r.native_operations)))
      e.apply(op);
  });
  expect(e.children).toEqual(expected);
  expect(value).toEqual(baseline);
  return r;
}
it.each([
  ["a", "b", "before", ["a", "b", "c"]],
  ["a", "c", "before", ["b", "a", "c"]],
  ["a", "b", "after", ["b", "a", "c"]],
  ["c", "a", "after", ["a", "c", "b"]],
  ["c", "a", "before", ["c", "a", "b"]],
  ["b", "a", "after", ["a", "b", "c"]],
  ["a", "c", "after", ["b", "c", "a"]],
])("R1 %s %s %s", (target, dest, placement, ids) => {
  const r = check(
    base,
    [
      {
        type: "move_content",
        target_id: target,
        destination_id: dest,
        placement,
      },
    ],
    (ids as string[]).map((id) => base.find((n) => n.id === id)),
  );
  if ((ids as string[]).join() === "a,b,c") {
    expect(r.changed).toBe(false);
    expect(r.affected_element_ids).toEqual([]);
  }
});
it.each(["before", "after", "prepend_child", "append_child"])(
  "R1 self %s is rejected",
  (placement) => {
    expect(
      transform({
        profile,
        base_value: base as any,
        commands: [
          {
            type: "move_content",
            target_id: "b",
            destination_id: "b",
            placement,
          },
        ],
      }).ok,
    ).toBe(false);
  },
);
const section = (id: string, children: any[]) => ({
  type: "jd_section",
  id,
  section_kind: "other",
  children,
});
it.each([
  ["a", "prepend_child", ["a", "b", "c"]],
  ["c", "prepend_child", ["c", "a", "b"]],
  ["a", "append_child", ["b", "c", "a"]],
  ["c", "append_child", ["a", "b", "c"]],
])("R1 same-parent child placement %s %s", (target, placement, ids) => {
  check(
    [section("s", base)],
    [
      {
        type: "move_content",
        target_id: target,
        destination_id: "s",
        placement,
      },
    ],
    [
      section(
        "s",
        (ids as string[]).map((id) => base.find((n) => n.id === id)),
      ),
    ],
  );
});
it.each(["before", "after"])("R1 cross-parent %s", (placement) => {
  const left = section("left", [base[0], base[1]]),
    right = section("right", [base[2], p("d", "d")]);
  check(
    [left, right],
    [{ type: "move_content", target_id: "a", destination_id: "c", placement }],
    [
      section("left", [base[1]]),
      section(
        "right",
        placement === "before"
          ? [base[0], base[2], p("d", "d")]
          : [base[2], base[0], p("d", "d")],
      ),
    ],
  );
});
it("R1 root removal shifts destination parent using native move semantics", () => {
  check(
    [base[0], section("s", [base[1], base[2]])],
    [
      {
        type: "move_content",
        target_id: "a",
        destination_id: "s",
        placement: "append_child",
      },
    ],
    [section("s", [base[1], base[2], base[0]])],
  );
});
it("R2 changed text excludes untouched siblings", () => {
  const r = check(
    base,
    [
      {
        type: "replace_block_content",
        target_id: "a",
        content: [{ text: "changed" }],
      },
    ],
    [p("a", "changed"), base[1], base[2]],
  );
  expect(r.affected_element_ids).toEqual(["a"]);
});
it("R2 property changes exclude untouched siblings", () => {
  const r = check(
    base,
    [
      {
        type: "set_properties",
        target_id: "b",
        set: { source_refs: ["issued:test"] },
      },
    ],
    [base[0], { ...base[1], source_refs: ["issued:test"] }, base[2]],
  );
  expect(r.affected_element_ids).toEqual(["b"]);
});
it("R2 native mark unset captures containing block only", () => {
  const e = createJdEditor(base as any),
    c = capture(e);
  e.tf.unsetNodes("bold", { at: [0, 0] });
  c.flush();
  const r = result(e, base as any, c.operations, c.affectedIds);
  expect(r.affected_element_ids).toEqual(["a"]);
});
it("R2 insert/remove/move contain only actual content and necessary parents", () => {
  const v = [section("s", base), p("unrelated", "untouched")];
  const insert = transform({
    profile,
    base_value: v as any,
    commands: [
      {
        type: "insert_content",
        target_id: "b",
        placement: "after",
        content: [{ type: "p", children: [{ text: "new" }] }],
      },
    ],
  });
  expect(insert.ok).toBe(true);
  if (insert.ok) {
    const newId = (insert.value[0].children[2] as any).id;
    expect(new Set(insert.affected_element_ids)).toEqual(new Set(["s", newId]));
  }
  const del = check(
    v,
    [{ type: "remove_content", target_id: "a" }],
    [section("s", [base[1], base[2]]), v[1]],
  );
  expect(new Set(del.affected_element_ids)).toEqual(new Set(["s", "a"]));
  const move = check(
    v,
    [
      {
        type: "move_content",
        target_id: "a",
        destination_id: "c",
        placement: "after",
      },
    ],
    [section("s", [base[1], base[2], base[0]]), v[1]],
  );
  expect(new Set(move.affected_element_ids)).toEqual(new Set(["s", "a"]));
});
it("R2 normalization uses actual node operations and net-zero returns empty ids", () => {
  const value = [
    { type: "p", id: "a", children: [{ text: "a" }, { text: "b" }] },
    p("b", "b"),
  ];
  const r = validateJdValue({ profile, value: value as any });
  expect(r.ok).toBe(true);
  if (r.ok) {
    expect(r.affected_element_ids).toEqual(["a"]);
    expect(r.native_operations.length).toBeGreaterThan(0);
  }
  const zero = check(
    base,
    [
      {
        type: "replace_block_content",
        target_id: "b",
        content: [{ text: "temp" }],
      },
      {
        type: "replace_block_content",
        target_id: "b",
        content: [{ text: "b" }],
      },
    ],
    base,
  );
  expect(zero.changed).toBe(false);
  expect(zero.affected_element_ids).toEqual([]);
  expect(zero.native_operations.length).toBeGreaterThan(0);
});

it("R2 native split records generated element ID and leaves other blocks out", () => {
  const value = [p("a", "abc"), p("b", "untouched")];
  const e = createJdEditor(value as any),
    c = capture(e);
  e.tf.splitNodes({ at: { path: [0, 0], offset: 1 } });
  c.flush();
  const r = result(e, value as any, c.operations, c.affectedIds);
  expect(r.value).toHaveLength(3);
  const created = r.value[1].id;
  expect(created).not.toBe("a");
  expect(new Set(r.affected_element_ids)).toEqual(new Set(["a", created]));
  expect(r.value[2]).toEqual(value[1]);
  const replay = createJdEditor(value as any);
  replay.tf.withoutNormalizing(() => {
    for (const op of JSON.parse(JSON.stringify(r.native_operations)))
      replay.apply(op);
  });
  expect(replay.children).toEqual(r.value);
});
it("R2 actual cross-parent move includes both containers but not their siblings", () => {
  const v = [
    section("left", [base[0], base[1]]),
    section("right", [base[2], p("d", "d")]),
    p("outside", "untouched"),
  ];
  const r = check(
    v,
    [
      {
        type: "move_content",
        target_id: "a",
        destination_id: "c",
        placement: "after",
      },
    ],
    [
      section("left", [base[1]]),
      section("right", [base[2], base[0], p("d", "d")]),
      v[2],
    ],
  );
  expect(new Set(r.affected_element_ids)).toEqual(
    new Set(["a", "left", "right"]),
  );
});
