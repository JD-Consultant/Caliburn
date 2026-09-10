import { it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { transform } from "../src/transform.js";
import { validateJdValue } from "../src/validate.js";
import { createJdEditor } from "../src/profile.js";
import { fixture, profile, p, elements } from "./helpers.js";
it("native transformed operation JSON exactly replays complete Task8 move", () => {
  const r = transform({
    profile,
    base_value: fixture,
    commands: [
      {
        type: "move_content",
        target_id: "task-8",
        destination_id: "duty-1",
        placement: "append_child",
      },
    ],
  });
  expect(r.ok).toBe(true);
  if (r.ok) {
    const reopened = createJdEditor(fixture);
    reopened.tf.withoutNormalizing(() => {
      for (const op of JSON.parse(JSON.stringify(r.native_operations)))
        reopened.apply(op);
    });
    expect(reopened.children).toEqual(r.value);
  }
});
it("fixture source issuer covers every preserved source handle", () => {
  const issued = JSON.parse(
    readFileSync(
      new URL("../../fixtures/source-map.json", import.meta.url),
      "utf8",
    ),
  );
  const sourceNodes = elements(fixture).filter((n) => n.source_refs);
  expect(sourceNodes).toHaveLength(8);
  for (const node of sourceNodes)
    for (const ref of node.source_refs)
      expect(issued[ref]).toMatchObject({
        issued_handle: ref,
        document: "test-r2",
      });
});
it.each([null, undefined, NaN, Infinity, () => {}, new Date(), new Map()])(
  "rejects non-clean leaf property %s",
  (value) => {
    const v = [p("p")];
    (v[0].children[0] as any).bold = value;
    expect(validateJdValue({ profile, value: v as any }).ok).toBe(false);
  },
);
it("v1 profile and same-batch missing group cannot publish", () => {
  expect(
    validateJdValue({
      profile: {
        format_version: 1,
        engine_profile: "jd-plate-clean-v1",
      } as any,
      value: fixture,
    }).ok,
  ).toBe(false);
  expect(
    transform({
      profile,
      base_value: fixture,
      commands: [{ type: "remove_content", target_id: "f03-task-1-outcomes" }],
    }).ok,
  ).toBe(false);
});
