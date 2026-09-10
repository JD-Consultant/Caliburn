import { describe, it, expect } from "vitest";
import { createJdEditor } from "../src/profile.js";
import { validateJdValue } from "../src/validate.js";
import { fixture, profile, clone, p, elements, byId } from "./helpers.js";
describe("profile", () => {
  it("profile_roundtrip_full_r2_v2", () => {
    const e = createJdEditor(fixture);
    expect(e.children).toEqual(fixture);
    expect(
      createJdEditor(JSON.parse(JSON.stringify(e.children))).children,
    ).toEqual(fixture);
    const ns = elements(e.children);
    expect(ns).toHaveLength(190);
    for (const [t, c] of Object.entries({
      table: 1,
      jd_task: 8,
      jd_outcomes: 8,
      jd_requirements: 8,
      jd_knowledge: 5,
      jd_skill: 5,
    }))
      expect(ns.filter((n) => n.type === t)).toHaveLength(c);
  });
  it.each([
    "duplicate",
    "missing",
    "score",
    "diff",
    "suggestion",
    "nesting",
    "null",
    "undefined",
    "relation",
    "wrong-kind",
    "missing-group",
    "duplicate-link",
  ])("reject_invalid_clean_value: %s", (kind) => {
    const v = clone(fixture);
    const task = byId(v, "task-1");
    if (kind === "duplicate") v[0].id = v[1].id;
    if (kind === "missing") delete v[0].id;
    if (kind === "score") v[0].children[0].score = 1;
    if (kind === "diff" || kind === "suggestion") v[0][kind] = {};
    if (kind === "nesting") task.children.push(clone(task));
    if (kind === "null") v[0].children[0].bold = null;
    if (kind === "undefined") v[0].children[0].bold = undefined;
    if (kind === "relation") task.knowledge_ids = ["absent"];
    if (kind === "wrong-kind") task.knowledge_ids = ["f03-jd_skill-1"];
    if (kind === "missing-group")
      task.children = task.children.filter(
        (n: any) => n.type !== "jd_outcomes",
      );
    if (kind === "duplicate-link")
      task.knowledge_ids = ["f03-jd_knowledge-1", "f03-jd_knowledge-1"];
    const before = clone(v);
    expect(validateJdValue({ profile, value: v }).ok).toBe(false);
    expect(v).toEqual(before);
  });
  it("accepts empty marked leaf and unknown groups", () => {
    expect(
      validateJdValue({ profile, value: [p("empty", "", { bold: true })] }).ok,
    ).toBe(true);
    const v = [
      {
        type: "jd_section",
        id: "w",
        section_kind: "work",
        children: [
          {
            type: "jd_task",
            id: "t",
            children: [
              p("b", ""),
              { type: "jd_outcomes", id: "o", children: [p("op", "")] },
              { type: "jd_requirements", id: "r", children: [p("rp", "")] },
            ],
          },
        ],
      },
    ];
    expect(validateJdValue({ profile, value: v }).ok).toBe(true);
  });
  it("validate_value_is_not_a_fake_edit", () => {
    const v = [
      { type: "p", id: "p", children: [{ text: "a" }, { text: "b" }] },
    ];
    const r = validateJdValue({ profile, value: v });
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.value).toEqual([p("p", "ab")]);
      expect(r.native_operations.length).toBeGreaterThan(0);
    }
    expect(v[0].children).toHaveLength(2);
  });
});
