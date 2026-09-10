import { it, expect } from "vitest";
import { transform } from "../src/transform.js";
import { validateJdValue } from "../src/validate.js";
import { profile, p } from "./helpers.js";
const table = () => [
  {
    type: "table",
    id: "tb",
    children: [
      {
        type: "tr",
        id: "tr1",
        children: [
          {
            type: "td",
            id: "c1",
            colSpan: 2,
            rowSpan: 2,
            attributes: { colspan: "2", rowspan: "2" },
            children: [p("p1", "a")],
          },
          { type: "td", id: "c2", children: [p("p2", "b")] },
        ],
      },
      {
        type: "tr",
        id: "tr2",
        children: [{ type: "td", id: "c3", children: [p("p3", "c")] }],
      },
    ],
  },
];
it("numeric spans synchronize saved HTML dimensions within a full table", () => {
  const base = table();
  expect(validateJdValue({ profile, value: base as any }).ok).toBe(true);
  const r = transform({
    profile,
    base_value: base as any,
    commands: [
      { type: "set_properties", target_id: "c1", set: { colSpan: 1 } },
      { type: "set_properties", target_id: "c1", unset: ["rowSpan"] },
    ],
  });
  expect(r.ok).toBe(true);
  if (r.ok) {
    const cell: any = r.value[0].children[0].children[0];
    expect(cell.colSpan).toBe(1);
    expect(cell).not.toHaveProperty("rowSpan");
    expect(cell.attributes).toEqual({ colspan: "1" });
    const clear = transform({
      profile,
      base_value: r.value,
      commands: [
        { type: "set_properties", target_id: "c1", unset: ["colSpan"] },
      ],
    });
    expect(clear.ok).toBe(true);
    if (clear.ok)
      expect(
        (clear.value[0].children[0] as any).children[0],
      ).not.toHaveProperty("attributes");
  }
});
it("reject conflicting saved span and invalid target props", () => {
  const base = table();
  base[0].children[0].children[0].attributes!.colspan = "3";
  expect(validateJdValue({ profile, value: base as any }).ok).toBe(false);
  expect(
    transform({
      profile,
      base_value: [p("p")] as any,
      commands: [
        { type: "set_properties", target_id: "p", set: { colSpan: 2 } },
      ],
    }).ok,
  ).toBe(false);
});
