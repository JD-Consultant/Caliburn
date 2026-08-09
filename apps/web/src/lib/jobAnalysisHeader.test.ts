import type {
  DocumentReadinessView,
  JdHeaderView,
} from "@caliburn/job-analysis-contract";
import { describe, expect, it } from "vitest";

import {
  emptyJdHeaderForm,
  fromJdHeaderView,
  isJdHeaderFormDirty,
  readinessIssueLabel,
  readinessSummary,
  shouldAdoptJdHeaderRefetch,
  toJdHeaderWrite,
} from "./jobAnalysisHeader";

const FILLED_HEADER: JdHeaderView = {
  competency_name: "資訊安全維運人員",
  occupation_category_name: "資訊技術",
  occupation_name: "資訊安全分析師",
  occupation_code: "2529",
  industry_name: "電腦程式設計、諮詢及相關服務業",
  industry_code: "6201",
  work_description: "維運企業資訊安全設備並處理資安事件。",
  competency_level: 4,
  notes: "本文件為客製職務說明書。",
};

describe("JD header form mapping", () => {
  it("round-trips every employee-editable field and converts the level", () => {
    expect(toJdHeaderWrite(fromJdHeaderView(FILLED_HEADER))).toEqual(
      FILLED_HEADER,
    );
  });

  it("trims text and maps blank fields and level to null", () => {
    const form = {
      ...emptyJdHeaderForm(),
      competencyName: " 門市營運專員 ",
      workDescription: "  ",
      competencyLevel: "" as const,
    };

    expect(toJdHeaderWrite(form)).toMatchObject({
      competency_name: "門市營運專員",
      work_description: null,
      competency_level: null,
      notes: null,
    });
  });

  it("detects meaningful unsaved changes but ignores cosmetic whitespace", () => {
    const baseline = fromJdHeaderView(FILLED_HEADER);

    expect(
      isJdHeaderFormDirty(baseline, {
        ...baseline,
        competencyName: "資深資訊安全維運人員",
      }),
    ).toBe(true);
    expect(
      isJdHeaderFormDirty(baseline, {
        ...baseline,
        competencyName: `${baseline.competencyName} `,
      }),
    ).toBe(false);
    expect(isJdHeaderFormDirty(baseline, { ...baseline })).toBe(false);
  });

  it("treats an out-of-range stored level as blank instead of guessing", () => {
    const form = fromJdHeaderView({
      ...FILLED_HEADER,
      competency_level: 9 as JdHeaderView["competency_level"],
    });

    expect(form.competencyLevel).toBe("");
  });

  it("adopts a refetch only for an already-editing clean form", () => {
    const refetched = { ...FILLED_HEADER, competency_name: "更新後名稱" };

    expect(
      shouldAdoptJdHeaderRefetch(false, false, FILLED_HEADER, refetched),
    ).toBe(false);
    expect(
      shouldAdoptJdHeaderRefetch(true, true, FILLED_HEADER, refetched),
    ).toBe(false);
    expect(
      shouldAdoptJdHeaderRefetch(true, false, FILLED_HEADER, refetched),
    ).toBe(true);
    expect(
      shouldAdoptJdHeaderRefetch(true, false, refetched, refetched),
    ).toBe(false);
  });
});

describe("readiness presentation", () => {
  it("stays silent when the server reports no issues", () => {
    const readiness: DocumentReadinessView = { issues: [] };

    expect(readinessSummary(readiness)).toBeNull();
  });

  it("uses the server issue count without claiming completion", () => {
    const readiness: DocumentReadinessView = {
      issues: [
        { code: "competency_name_missing" },
        { code: "work_description_missing" },
      ],
    };

    expect(readinessSummary(readiness)).toBe("iCAP 版型欄位尚有 2 項未填");
    for (const banned of ["不完整", "不合格", "未通過", "完成"]) {
      expect(readinessSummary(readiness)).not.toContain(banned);
    }
  });

  it("maps every generated issue code to its employee-facing field label", () => {
    expect(
      [
        "competency_name_missing",
        "work_description_missing",
        "competency_level_missing",
        "task_duty_missing",
        "task_competency_level_missing",
        "duty_without_task",
        "opks_task_link_missing",
      ].map((code) =>
        readinessIssueLabel(code as DocumentReadinessView["issues"][number]["code"]),
      ),
    ).toEqual([
      "職能基準名稱",
      "工作描述",
      "基準級別",
      "Task 主要職責分組",
      "Task 職能級別",
      "沒有工作的主要職責",
      "未連結到工作的知識／技能",
    ]);
  });
});
