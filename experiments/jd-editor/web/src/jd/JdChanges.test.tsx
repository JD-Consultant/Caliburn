import React from "react";
import { it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { JdChanges } from "./JdChanges";
import type { JdDocumentValue } from "@caliburn/jd-editor-contract";
import fixture from "../../../fixtures/r2-canonical.json";
import { allElements, nameOf } from "./JdNode";
it("shows exact before and after for same ID replacement and empty marks, without invented operations", () => {
  render(
    <JdChanges
      change={{
        status: "ok",
        mode: "revision_comparison",
        change_ref: null,
        origin: null,
        before_revision_ref: "r1",
        after_revision_ref: "r2",
        before_fragment: [
          {
            type: "p",
            id: "same",
            children: [{ text: "原本正文" }, { text: "", bold: true }],
          },
        ],
        after_fragment: [
          {
            type: "p",
            id: "same",
            children: [{ text: "修改正文" }, { text: "", italic: true }],
          },
        ],
        native_operations: null,
        source_refs: [],
        presentation_limitations: [],
        continuation_ref: null,
      }}
    />,
  );
  expect(screen.getAllByText("原本正文").length).toBeGreaterThan(0);
  expect(screen.getAllByText("修改正文").length).toBeGreaterThan(0);
  expect(screen.getByText(/部分格式或關係差異未高亮/)).toBeTruthy();
  expect(screen.getAllByText(/空白文字格式/).length).toBeGreaterThan(1);
});

it("resolves shared K content against each version and retains a removed user's old name", () => {
  const before = structuredClone(fixture) as JdDocumentValue;
  const after = structuredClone(before);
  const prior = allElements(before),
    next = allElements(after);
  const knowledge = next.find((n) => n.id === "f03-jd_knowledge-2")!;
  const oldName = nameOf(prior.find((n) => n.id === knowledge.id)!);
  knowledge.children = [
    { type: "p", id: "new-title", children: [{ text: "新版介面知識" }] },
  ];
  const removed = next.find((n) => n.id === "task-7")!;
  const removedName = nameOf(removed);
  removed.knowledge_ids = [];
  const { container } = render(
    <JdChanges
      change={{
        status: "ok",
        mode: "revision_comparison",
        change_ref: null,
        origin: null,
        before_revision_ref: "before",
        after_revision_ref: "after",
        before_fragment: before,
        after_fragment: after,
        native_operations: null,
        source_refs: [],
        presentation_limitations: [],
        continuation_ref: null,
      }}
    />,
  );
  const views = container.querySelectorAll(".changes > details > .jd-readonly");
  expect(views[0].textContent).toContain(oldName);
  expect(views[1].textContent).toContain("新版介面知識");
  const impact = [...container.querySelectorAll(".changes > aside")].find((n) =>
    n.textContent?.includes("新版介面知識"),
  )!;
  expect(impact.querySelectorAll("p")[0].textContent).toContain(removedName);
  expect(impact.querySelectorAll("p")[1].textContent).not.toContain(
    removedName,
  );
});
