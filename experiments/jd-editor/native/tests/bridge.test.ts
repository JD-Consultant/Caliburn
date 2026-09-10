import { it, expect } from "vitest";
import { spawnSync } from "node:child_process";
import { readJdSelection } from "../src/read-selection.js";
import { fixture, profile, byId } from "./helpers.js";
function pathOf(
  nodes: any[],
  id: string,
  parent: number[] = [],
): number[] | undefined {
  for (const [i, n] of nodes.entries()) {
    const path = [...parent, i];
    if (n.id === id) return path;
    if (n.children) {
      const found = pathOf(n.children, id, path);
      if (found) return found;
    }
  }
}
it("canonical nested Task selection uses real fragment", () => {
  const path = pathOf(fixture, "r2-81")!;
  const range = {
    anchor: { path: [...path, 0], offset: 0 },
    focus: { path: [...path, 0], offset: 2 },
  };
  const r = readJdSelection({ profile, value: fixture, range });
  expect(r.ok).toBe(true);
  if (r.ok) {
    expect(r.target_id).toBe("r2-81");
    expect(JSON.stringify(r.fragment)).toContain("8.");
  }
});
it("fixed bridge returns one validated JSON result in a fresh process", () => {
  for (const [entry, input] of [
    ["validate-value", { profile, value: fixture }],
    [
      "read-selection",
      {
        profile,
        value: [{ type: "p", id: "p", children: [{ text: "文字" }] }],
        range: {
          anchor: { path: [0, 0], offset: 0 },
          focus: { path: [0, 0], offset: 1 },
        },
      },
    ],
    [
      "transform",
      {
        profile,
        base_value: fixture,
        commands: [
          {
            type: "replace_block_content",
            target_id: "r2-1",
            content: [{ text: "new" }],
          },
        ],
      },
    ],
  ] as const) {
    const r = spawnSync(process.execPath, ["dist/bridge.js", entry], {
      input: JSON.stringify(input),
      encoding: "utf8",
    });
    expect(r.status).toBe(0);
    expect(r.stderr).toBe("");
    expect(JSON.parse(r.stdout).ok).toBe(true);
  }
  const bad = spawnSync(
    process.execPath,
    ["dist/bridge.js", "validate-value"],
    { input: "not json", encoding: "utf8" },
  );
  expect(JSON.parse(bad.stdout)).toMatchObject({
    ok: false,
    error: { code: "invalid_input" },
  });
});
