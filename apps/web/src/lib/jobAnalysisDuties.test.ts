import type { DutyView, JdTaskView } from "@caliburn/job-analysis-contract";
import { describe, expect, it } from "vitest";

import {
  competencyLevelLabel,
  dutyLabelFor,
  groupTasksByDuty,
  UNASSIGNED_GROUP_LABEL,
} from "./jobAnalysisDuties";

function duty(dutyId: string, order: number, statement = "維運門市營運系統"): DutyView {
  return { duty_id: dutyId, statement, display_order: order };
}

function task(
  taskId: string,
  order: number,
  dutyId: string | null = null,
  competencyLevel: number | null = null,
): JdTaskView {
  return {
    task_id: taskId,
    statement: "每週彙整營運週報",
    purpose_result: null,
    context: null,
    frequency_text: null,
    responsibility_role: null,
    enablers: [],
    display_order: order,
    duty_id: dutyId,
    competency_level: competencyLevel,
  };
}

describe("groupTasksByDuty", () => {
  it("keeps the duty order and puts each task under its duty", () => {
    const duties = [duty("duty-1", 0, "維運門市系統"), duty("duty-2", 1, "處理帳號權限")];
    const tasks = [task("task-1", 0, "duty-2"), task("task-2", 1, "duty-1")];

    const groups = groupTasksByDuty(duties, tasks);

    expect(groups.map((group) => group.duty?.duty_id)).toEqual([
      "duty-1",
      "duty-2",
    ]);
    expect(groups[0].tasks.map((item) => item.task_id)).toEqual(["task-2"]);
    expect(groups[1].tasks.map((item) => item.task_id)).toEqual(["task-1"]);
  });

  it("shows an empty duty rather than hiding it", () => {
    // 空職責就是 readiness 的 `duty_without_task`——藏起來缺漏就看不見了
    const groups = groupTasksByDuty([duty("duty-1", 0)], []);

    expect(groups).toHaveLength(1);
    expect(groups[0].tasks).toEqual([]);
  });

  it("adds the unassigned section only when something is actually unassigned", () => {
    const duties = [duty("duty-1", 0)];

    const assigned = groupTasksByDuty(duties, [task("task-1", 0, "duty-1")]);
    const withGap = groupTasksByDuty(duties, [task("task-1", 0)]);

    expect(assigned.map((group) => group.duty?.duty_id)).toEqual(["duty-1"]);
    expect(withGap.at(-1)?.duty).toBeNull();
    expect(withGap.at(-1)?.tasks.map((item) => item.task_id)).toEqual(["task-1"]);
  });

  it("never loses or duplicates a task", () => {
    // 畫面少一條任務比多一條錯位的任務難發現得多,所以連指向不存在職責的
    // 任務（API 那端不可表示）也要出現在未指派區,不能被丟掉
    const duties = [duty("duty-1", 0), duty("duty-2", 1)];
    const tasks = [
      task("task-1", 0, "duty-1"),
      task("task-2", 1, null),
      task("task-3", 2, "duty-gone"),
      task("task-4", 3, "duty-2"),
    ];

    const groups = groupTasksByDuty(duties, tasks);
    const flattened = groups.flatMap((group) =>
      group.tasks.map((item) => item.task_id),
    );

    expect(flattened.slice().sort()).toEqual([
      "task-1",
      "task-2",
      "task-3",
      "task-4",
    ]);
    expect(new Set(flattened).size).toBe(flattened.length);
    expect(groups.at(-1)?.tasks.map((item) => item.task_id)).toEqual([
      "task-2",
      "task-3",
    ]);
  });

  it("returns nothing to render when the document is empty", () => {
    expect(groupTasksByDuty([], [])).toEqual([]);
  });

  it("never produces an export position code", () => {
    // `T1`／`T1.1` 是匯出版面位置碼,不是畫面上的 identity（ADR 0052 決定 10）
    const groups = groupTasksByDuty(
      [duty("duty-1", 0, "維運門市系統")],
      [task("task-1", 0, "duty-1")],
    );

    expect(JSON.stringify(groups)).not.toMatch(/"T\d/);
  });
});

describe("labels", () => {
  it("names the unassigned bucket and falls back to it for an unknown duty", () => {
    const duties = [duty("duty-1", 0, "維運門市系統")];

    expect(dutyLabelFor(duties, "duty-1")).toBe("維運門市系統");
    expect(dutyLabelFor(duties, null)).toBe(UNASSIGNED_GROUP_LABEL);
    expect(dutyLabelFor(duties, "duty-gone")).toBe(UNASSIGNED_GROUP_LABEL);
  });

  it("says a level is missing rather than showing a zero", () => {
    expect(competencyLevelLabel(null)).toBe("尚未填寫");
    expect(competencyLevelLabel(4)).toBe("第 4 級");
  });
});
