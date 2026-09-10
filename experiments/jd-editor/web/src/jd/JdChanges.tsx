"use client";
import React, { useMemo } from "react";
import { computeDiff } from "@platejs/diff";
import type { Descendant } from "platejs";
import type { JdChangeReadSuccess } from "@caliburn/jd-editor-contract";
import {
  ReadOnlyValue,
  allElements,
  nameOf,
  type DisplayValue,
} from "./JdNode";
export function JdChanges({
  change,
  source,
}: {
  change: JdChangeReadSuccess;
  source?: (ref: string) => void;
}) {
  const before = change.before_fragment as DisplayValue,
    after = change.after_fragment as DisplayValue;
  const diff = useMemo(
    () =>
      computeDiff(
        before as Descendant[],
        after as Descendant[],
      ) as DisplayValue,
    [before, after],
  );
  const original = allElements(before),
    current = allElements(after);
  const shared = [
    ...new Set(
      [...original, ...current]
        .filter((n) => ["jd_knowledge", "jd_skill"].includes(n.type))
        .map((n) => n.id),
    ),
  ];
  return (
    <section className="changes" aria-label="確切改動">
      <h3>這次改動</h3>
      <p>
        {change.origin === "ai"
          ? "顧問修改"
          : change.origin === "manual"
            ? "人工修改"
            : "版本比較"}
        ；已保存不代表工作事實已核准。
      </p>
      {!change.native_operations && (
        <p>部分格式或關係差異未高亮，可查看兩版完整內容。</p>
      )}
      <details open>
        <summary>修改前・確切內容</summary>
        <ReadOnlyValue value={before} source={source} />
      </details>
      <details open>
        <summary>修改後・確切內容</summary>
        <ReadOnlyValue value={after} source={source} />
      </details>
      <details>
        <summary>文字與結構高亮</summary>
        <ReadOnlyValue value={diff} source={source} />
      </details>
      {shared.map((id) => {
        const old = original.find((n) => n.id === id),
          now = current.find((n) => n.id === id);
        if (JSON.stringify(old) === JSON.stringify(now)) return null;
        const field =
          (now ?? old)?.type === "jd_knowledge" ? "knowledge_ids" : "skill_ids";
        return (
          <aside key={id}>
            <strong>
              共享項目：{now ? nameOf(now) : old ? nameOf(old) : ""}
            </strong>
            <p>
              原本使用：
              {original
                .filter(
                  (n) => n.type === "jd_task" && (n[field] ?? []).includes(id),
                )
                .map(nameOf)
                .join("、") || "無引用"}
            </p>
            <p>
              目前使用：
              {current
                .filter(
                  (n) => n.type === "jd_task" && (n[field] ?? []).includes(id),
                )
                .map(nameOf)
                .join("、") || "無引用"}
            </p>
          </aside>
        );
      })}
    </section>
  );
}
