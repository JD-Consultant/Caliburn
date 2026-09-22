import React, { createContext, useContext } from "react";
import type { JdSavedElement, JdText } from "@caliburn/jd-editor-contract";
import { JdLeaf } from "./JdLeaf";
export type DisplayNode = JdSavedElement & { diffOperation?: { type: string } };
export type DisplayValue = (JdText | DisplayNode)[];
export const DocumentView = createContext<{
  value: DisplayValue;
  link?: (
    id: string,
    field: "knowledge_ids" | "skill_ids",
    ids: string[],
  ) => void;
  source?: (ref: string) => void;
}>({ value: [] });
export function allElements(value: DisplayValue): DisplayNode[] {
  return value.flatMap((n) =>
    "type" in n
      ? [n as DisplayNode, ...allElements((n as DisplayNode).children)]
      : [],
  );
}
export function textOf(node: JdText | JdSavedElement): string {
  return "text" in node
    ? String(node.text)
    : node.children.map(textOf).join("");
}
export function nameOf(node: JdSavedElement) {
  const unnamed = node.type === "jd_knowledge" ? "未命名知識"
    : node.type === "jd_skill" ? "未命名技能" : "未命名項目";
  return node.children.length
    ? textOf(node.children[0]) || unnamed
    : unnamed;
}
const sections: Record<string, string> = {
  identity: "基本資料",
  work: "主要職責與工作任務",
  conditions: "工作條件與責任範圍",
  basic_info: "基本資料",
  purpose: "職務目的",
  responsibilities: "工作職責",
  knowledge: "相關知識",
  skills: "相關技能",
  other: "其他",
  working_conditions: "工作條件",
};
const fields: Record<string, string> = {
  colSizes: "欄寬",
  marginLeft: "左邊距",
  size: "尺寸",
  colSpan: "跨欄",
  rowSpan: "跨列",
  background: "背景",
  borders: "框線",
  attributes: "表格屬性",
  top: "上",
  bottom: "下",
  left: "左",
  right: "右",
  color: "顏色",
  width: "寬度",
  style: "樣式",
  scope: "表頭範圍",
};
function description(value: unknown): string {
  if (Array.isArray(value)) return value.map(description).join("、");
  if (value && typeof value === "object")
    return Object.entries(value)
      .map(([k, v]) => (fields[k] ?? k) + " " + description(v))
      .join("；");
  return String(value);
}
export function JdNode({
  element,
  children,
  attributes = {},
}: {
  element: DisplayNode;
  children: React.ReactNode;
  attributes?: React.HTMLAttributes<HTMLElement>;
}) {
  const view = useContext(DocumentView),
    node = element;
  const nodes = allElements(view.value);
  const tasks = nodes.filter((n) => n.type === "jd_task");
  const diff = node.diffOperation ? "diff-" + node.diffOperation.type : "";
  const common = {
    ...attributes,
    "data-jd-id": node.id,
    className: ["jd-node", node.type, diff].join(" "),
  };
  const meta = (
    <>
      {node.section_kind && (
        <small contentEditable={false}>
          章節用途：{sections[node.section_kind] ?? node.section_kind}
        </small>
      )}
      {[
        "colSizes",
        "marginLeft",
        "size",
        "colSpan",
        "rowSpan",
        "background",
        "borders",
        "attributes",
      ]
        .filter((k) => k in node)
        .map((k) => (
          <small contentEditable={false} key={k}>
            {fields[k]}：{description(node[k])}{" "}
          </small>
        ))}
      {node.source_refs?.map((ref, i) => (
        <button
          contentEditable={false}
          type="button"
          className="source"
          key={ref}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => view.source?.(ref)}
        >
          依據 {i + 1}
        </button>
      ))}
    </>
  );
  if (node.type === "table")
    return (
      <table
        {...common}
        style={{ marginLeft: node.marginLeft, width: node.size }}
      >
        <caption>
          {meta}
          {node.children.map((child, index) =>
            "type" in child && child.type === "tr" ? (
              <React.Fragment key={child.id}>
                {child.size !== undefined && (
                  <small contentEditable={false}>
                    第 {index + 1} 列尺寸：{child.size}
                  </small>
                )}
                {child.source_refs?.map((ref, i) => (
                  <button
                    key={ref}
                    type="button"
                    className="source"
                    contentEditable={false}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => view.source?.(ref)}
                  >
                    第 {index + 1} 列依據 {i + 1}
                  </button>
                ))}
              </React.Fragment>
            ) : null,
          )}
        </caption>
        {node.colSizes && (
          <colgroup>
            {node.colSizes.map((w, i) => (
              <col key={i} style={{ width: w }} />
            ))}
          </colgroup>
        )}
        <tbody>{children}</tbody>
      </table>
    );
  if (node.type === "tr") return <tr {...common}>{children}</tr>;
  if (node.type === "td" || node.type === "th") {
    const Tag = node.type;
    return (
      <Tag
        {...common}
        colSpan={node.colSpan}
        rowSpan={node.rowSpan}
        style={{ background: node.background }}
      >
        {meta}
        {children}
      </Tag>
    );
  }
  if (node.type === "ul" || node.type === "ol") {
    const Tag = node.type;
    return (
      <div {...common}>
        {meta}
        <Tag>{children}</Tag>
      </div>
    );
  }
  if (node.type === "li")
    return (
      <li {...common}>
        {meta}
        {children}
      </li>
    );
  if (node.type === "hr")
    return (
      <div {...common}>
        {meta}
        <hr />
        {children}
      </div>
    );
  if (["h1", "h2", "h3", "p", "blockquote"].includes(node.type)) {
    const Tag = node.type as "p";
    return (
      <Tag {...common}>
        {meta}
        {children}
      </Tag>
    );
  }
  const relationships =
    node.type === "jd_task" ? (
      <div contentEditable={false} className="relations">
        {(["knowledge_ids", "skill_ids"] as const).map((field) => {
          const items = nodes.filter(
            (n) =>
              n.type ===
              (field === "knowledge_ids" ? "jd_knowledge" : "jd_skill"),
          );
          return (
            <div key={field}>
              <strong>
                {field === "knowledge_ids" ? "相關知識" : "相關技能"}
              </strong>
              {(node[field] ?? []).map((id) => {
                const item = items.find((n) => n.id === id);
                return (
                  <details key={id}>
                    <summary>
                      {item ? nameOf(item) : "引用項目無法讀取"}
                    </summary>
                    {item && (
                      <ReadOnlyValue
                        value={[item]}
                        contextValue={view.value}
                        source={view.source}
                      />
                    )}
                  </details>
                );
              })}
              {view.link && (
                <details>
                  <summary>調整引用</summary>
                  {items.map((item) => (
                    <label key={item.id}>
                      <input
                        type="checkbox"
                        checked={(node[field] ?? []).includes(item.id)}
                        onChange={(e) => {
                          const ids = node[field] ?? [];
                          view.link?.(
                            node.id,
                            field,
                            e.target.checked
                              ? [...ids, item.id]
                              : ids.filter((id) => id !== item.id),
                          );
                        }}
                      />
                      {nameOf(item)}
                    </label>
                  ))}
                </details>
              )}
            </div>
          );
        })}
      </div>
    ) : null;
  const incoming =
    node.type === "jd_knowledge" || node.type === "jd_skill"
      ? tasks.filter((t) =>
          (
            t[node.type === "jd_knowledge" ? "knowledge_ids" : "skill_ids"] ??
            []
          ).includes(node.id),
        )
      : [];
  return (
    <div {...common}>
      {meta}
      {node.type === "jd_outcomes" && (
        <h4 contentEditable={false}>工作成果／產出</h4>
      )}
      {node.type === "jd_requirements" && (
        <h4 contentEditable={false}>工作執行要求</h4>
      )}
      {children}
      {relationships}
      {["jd_knowledge", "jd_skill"].includes(node.type) && (
        <aside contentEditable={false}>
          共用於 {incoming.length} 項工作：
          {incoming.map(nameOf).join("、") || "尚未引用"}
        </aside>
      )}
    </div>
  );
}
export function ReadOnlyValue({
  value,
  contextValue = value,
  source,
}: {
  value: DisplayValue;
  contextValue?: DisplayValue;
  source?: (ref: string) => void;
}) {
  function render(nodes: DisplayValue): React.ReactNode {
    return nodes.map((node, index) =>
      "type" in node ? (
        <JdNode key={index} element={node as DisplayNode}>
          {render((node as DisplayNode).children)}
        </JdNode>
      ) : (
        <JdLeaf key={index} leaf={node as JdText}>
          {(node as JdText).text}
        </JdLeaf>
      ),
    );
  }
  return (
    <DocumentView.Provider value={{ value: contextValue, source }}>
      <div className="jd-readonly">{render(value)}</div>
    </DocumentView.Provider>
  );
}
