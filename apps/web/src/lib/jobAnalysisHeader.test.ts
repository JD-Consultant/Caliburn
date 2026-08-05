import { describe, expect, it } from "vitest";

import {
  emptyJdHeaderForm,
  fromJdHeaderView,
  isJdHeaderFormDirty,
  readinessIssueLabel,
  readinessSummary,
  toJdHeaderWrite,
} from "./jobAnalysisHeader";

const FILLED = {
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
  it("sends null rather than empty strings for untouched fields", () => {
    expect(toJdHeaderWrite(emptyJdHeaderForm())).toEqual({
      competency_name: null,
      occupation_category_name: null,
      occupation_name: null,
      occupation_code: null,
      industry_name: null,
      industry_code: null,
      work_description: null,
      competency_level: null,
      notes: null,
    });
  });

  it("trims whitespace-only input down to null", () => {
    const form = { ...emptyJdHeaderForm(), competencyName: "   " };

    expect(toJdHeaderWrite(form).competency_name).toBeNull();
  });

  it("round-trips every employee-editable field", () => {
    expect(toJdHeaderWrite(fromJdHeaderView(FILLED))).toEqual(FILLED);
  });

  it("keeps the competency level clearable", () => {
    const cleared = { ...fromJdHeaderView(FILLED), competencyLevel: "" as const };

    expect(toJdHeaderWrite(cleared).competency_level).toBeNull();
  });

  it("treats an out-of-range stored level as unset instead of guessing", () => {
    const form = fromJdHeaderView({ ...FILLED, competency_level: 9 });

    expect(form.competencyLevel).toBe("");
  });

  it("detects unsaved changes and ignores cosmetic whitespace", () => {
    const baseline = fromJdHeaderView(FILLED);
    const edited = { ...baseline, competencyName: "資深資訊安全維運人員" };
    const padded = { ...baseline, competencyName: `${FILLED.competency_name} ` };

    expect(isJdHeaderFormDirty(baseline, edited)).toBe(true);
    expect(isJdHeaderFormDirty(baseline, padded)).toBe(false);
  });
});

describe("readiness presentation", () => {
  it("stays silent when nothing is missing", () => {
    expect(readinessSummary({ issues: [] })).toBeNull();
  });

  it("counts the missing fields without claiming the JD is complete", () => {
    const summary = readinessSummary({
      issues: [
        { code: "competency_name_missing", field: "competency_name" },
        { code: "work_description_missing", field: "work_description" },
      ],
    });

    expect(summary).toBe("iCAP 版型欄位尚有 2 項未填");
    // ADR 0052 決定 7：不得使用這些措辭
    for (const banned of ["不完整", "不合格", "未通過", "完成"]) {
      expect(summary).not.toContain(banned);
    }
  });

  it("labels each issue with the official field name", () => {
    expect(readinessIssueLabel("competency_level_missing")).toBe("基準級別");
    expect(readinessIssueLabel("work_description_missing")).toBe("工作描述");
  });

  it("labels the structural gaps too, and distinguishes the two level codes", () => {
    expect(readinessIssueLabel("task_duty_missing")).toBe("工作任務的所屬主要職責");
    expect(readinessIssueLabel("task_competency_level_missing")).toBe(
      "工作任務的職能級別",
    );
    expect(readinessIssueLabel("duty_without_task")).toBe("主要職責底下的工作任務");
    // header 的基準級別與 Task 的職能級別是兩件事，標籤不得相同
    expect(readinessIssueLabel("competency_level_missing")).not.toBe(
      readinessIssueLabel("task_competency_level_missing"),
    );
  });
});
