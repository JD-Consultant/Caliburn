import { it, expect } from "vitest";
import { copyJdElements } from "../src/copy.js";
import { createJdEditor } from "../src/profile.js";
import { validateJdValue } from "../src/validate.js";
import { profile, fixture, byId, elements } from "./helpers.js";
it("native copy remaps only endpoints inside copied fragment", () => {
  const editor = createJdEditor(fixture);
  copyJdElements(
    editor,
    ["section-work", "section-knowledge"],
    [editor.children.length],
  );
  const copyWork = editor.children.at(-2) as any;
  const copyK = editor.children.at(-1) as any;
  const copyTasks = elements([copyWork]).filter((n) => n.type === "jd_task");
  const copiedItems = elements([copyK]).filter(
    (n) => n.type === "jd_knowledge",
  );
  expect(copyTasks).toHaveLength(8);
  expect(copiedItems).toHaveLength(5);
  const originals = elements(fixture);
  const copied = elements([copyWork, copyK]);
  expect(copied.every((n) => !originals.some((o) => o.id === n.id))).toBe(true);
  for (let i = 0; i < copyTasks.length; i++) {
    const original = byId(fixture, `task-${i + 1}`);
    expect(copyTasks[i].skill_ids).toEqual(original.skill_ids);
    expect(copyTasks[i].knowledge_ids).toEqual(
      original.knowledge_ids?.map(
        (id: string) =>
          copiedItems[
            elements(fixture)
              .filter((n) => n.type === "jd_knowledge")
              .findIndex((n) => n.id === id)
          ].id,
      ),
    );
  }
  expect(editor.children.slice(0, fixture.length)).toEqual(fixture);
  expect(validateJdValue({ profile, value: editor.children as any }).ok).toBe(
    true,
  );
});
