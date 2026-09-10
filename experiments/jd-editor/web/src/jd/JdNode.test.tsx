import React from "react";
import { it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { ReadOnlyValue, type DisplayValue } from "./JdNode";
it("linked definition source uses the same source callback", () => {
  const source = vi.fn();
  const value: DisplayValue = [
    {
      type: "jd_task",
      id: "task",
      knowledge_ids: ["knowledge"],
      children: [
        { type: "p", id: "title", children: [{ text: "工作" }] },
        {
          type: "jd_outcomes",
          id: "out",
          children: [{ type: "p", id: "out-p", children: [{ text: "" }] }],
        },
        {
          type: "jd_requirements",
          id: "req",
          children: [{ type: "p", id: "req-p", children: [{ text: "" }] }],
        },
      ],
    },
    {
      type: "jd_knowledge",
      id: "knowledge",
      source_refs: ["existing-owner-ref"],
      children: [
        { type: "p", id: "knowledge-p", children: [{ text: "相關知識" }] },
      ],
    },
  ];
  const { container } = render(<ReadOnlyValue value={value} source={source} />);
  fireEvent.click(container.querySelector(".relations .source")!);
  expect(source).toHaveBeenCalledWith("existing-owner-ref");
});
it("keeps row and list metadata readable without inserting invalid table/list children", () => {
  const value: DisplayValue = [
    {
      type: "table",
      id: "table",
      children: [
        {
          type: "tr",
          id: "row",
          size: 32,
          source_refs: ["row-source"],
          children: [
            {
              type: "td",
              id: "cell",
              children: [
                { type: "p", id: "cell-p", children: [{ text: "資料" }] },
              ],
            },
          ],
        },
      ],
    },
    {
      type: "ul",
      id: "list",
      source_refs: ["list-source"],
      children: [
        {
          type: "li",
          id: "li",
          children: [{ type: "lic", id: "lic", children: [{ text: "項目" }] }],
        },
      ],
    },
  ];
  const { container } = render(
    <ReadOnlyValue value={value} source={() => {}} />,
  );
  expect(container.textContent).toContain("第 1 列尺寸：32");
  expect(container.querySelectorAll("button.source")).toHaveLength(2);
  expect(container.querySelectorAll("tr > button, ul > button")).toHaveLength(
    0,
  );
});
