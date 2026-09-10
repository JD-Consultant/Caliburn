import React from "react";
import { it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { JdEditor } from "./JdEditor";
import fixture from "../../../fixtures/r2-canonical.json";
import type { JdDocumentValue } from "@caliburn/jd-editor-contract";
it("renders full active v2 in exactly one editable document", () => {
  const { container } = render(
    <JdEditor
      value={fixture as JdDocumentValue}
      locked={false}
      onEdit={() => {}}
      onReady={() => {}}
    />,
  );
  expect(container.querySelectorAll("[contenteditable=true]").length).toBe(1);
  expect(
    container.querySelectorAll("[data-jd-id][class*=jd_task]").length,
  ).toBe(8);
  expect(container.querySelectorAll("table").length).toBe(1);
  expect(screen.getAllByText("工作成果／產出").length).toBe(8);
  expect(screen.getAllByText("工作執行要求").length).toBe(8);
});

it("shows empty-leaf formats inside the actual editor", () => {
  const { container } = render(
    <JdEditor
      value={[
        {
          type: "p",
          id: "empty",
          children: [
            {
              text: "",
              bold: true,
              italic: true,
              underline: true,
              strikethrough: true,
            },
          ],
        },
      ]}
      locked={false}
      onEdit={() => {}}
      onReady={() => {}}
    />,
  );
  expect(container.textContent).toContain(
    "空白文字格式：粗體、斜體、底線、刪除線",
  );
});
