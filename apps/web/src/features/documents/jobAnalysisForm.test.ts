import { describe, expect, it } from "vitest";

import {
  emptyTaskForm,
  fromTaskView,
  isTaskFormDirty,
  moveTaskWithinDuty,
  toTaskWrite,
  type TaskFormValue,
} from "./jobAnalysisForm";

describe("Current JD Task form mapping", () => {
  it("allows a Task with only a meaningful statement", () => {
    const form = { ...emptyTaskForm(), statement: " 每週彙整營運週報 " };

    expect(toTaskWrite(form)).toEqual({
      statement: "每週彙整營運週報",
      purpose_result: null,
      context: null,
      frequency_text: null,
      responsibility_role: null,
      duty_id: null,
      competency_level: null,
      enablers: [],
    });
  });

  it("serializes an unassigned Task without inventing a Duty or level", () => {
    const form: TaskFormValue = {
      ...emptyTaskForm(),
      statement: "盤點耗材",
      dutyId: "",
      competencyLevel: "",
    };

    expect(toTaskWrite(form)).toMatchObject({
      duty_id: null,
      competency_level: null,
    });
  });

  it("round-trips every employee-editable field", () => {
    const form = fromTaskView({
      task_id: "task-1",
      statement: "彙整營運週報",
      purpose_result: "讓主管掌握狀況",
      context: "每週結束時",
      frequency_text: "每週一次",
      responsibility_role: "shared",
      duty_id: null,
      competency_level: null,
      enablers: [
        { kind: "tool_system", name: "Excel" },
        { kind: "method", name: "交叉檢查" },
      ],
      display_order: 0,
    });

    expect(toTaskWrite(form)).toEqual({
      statement: "彙整營運週報",
      purpose_result: "讓主管掌握狀況",
      context: "每週結束時",
      frequency_text: "每週一次",
      responsibility_role: "shared",
      duty_id: null,
      competency_level: null,
      enablers: [
        { kind: "tool_system", name: "Excel" },
        { kind: "method", name: "交叉檢查" },
      ],
    });
  });

  it("drops empty enabler rows and detects unsaved changes", () => {
    const initial = emptyTaskForm();
    const edited = {
      ...initial,
      statement: "盤點耗材",
      enablers: [{ kind: "other" as const, name: "   " }],
    };

    expect(toTaskWrite(edited).enablers).toEqual([]);
    expect(isTaskFormDirty(initial, edited)).toBe(true);
    expect(isTaskFormDirty(edited, { ...edited })).toBe(false);
  });

  it("moves within the visible Duty group while preserving interleaved Tasks", () => {
    const tasks = [
      {
        task_id: "t1",
        duty_id: "d1",
      },
      {
        task_id: "t2",
        duty_id: "d2",
      },
      {
        task_id: "t3",
        duty_id: "d1",
      },
    ];

    expect(moveTaskWithinDuty(tasks, "t3", "d1", -1)).toEqual([
      "t3",
      "t2",
      "t1",
    ]);
  });
});
