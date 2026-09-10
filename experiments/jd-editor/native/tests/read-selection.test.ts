import { it, expect } from "vitest";
import { readJdSelection } from "../src/read-selection.js";
import { profile, p } from "./helpers.js";
const range = {
  anchor: { path: [1, 0], offset: 1 },
  focus: { path: [1, 0], offset: 3 },
};
it("read_selection_is_read_only_and_exact", () => {
  const v = [p("a"), p("b")];
  expect(readJdSelection({ profile, value: v, range })).toEqual({
    ok: true,
    target_id: "b",
    range,
    fragment: [p("b", "複文")],
  });
  expect(v).toEqual([p("a"), p("b")]);
});
it.each(["cross", "bounds", "type", "normalize"])(
  "rejects %s selection",
  (kind) => {
    const value = [p("a"), p("b")];
    const r = structuredClone(range);
    if (kind === "cross") r.anchor.path = [0, 0];
    if (kind === "bounds") r.focus.offset = 99;
    if (kind === "type") (r.focus as any).offset = "2";
    if (kind === "normalize") value[1].children.push({ text: "a" });
    expect(readJdSelection({ profile, value, range: r }).ok).toBe(false);
  },
);
