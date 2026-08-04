import { describe, expect, it } from "vitest";

import {
  emptyTaskForm,
  fromTaskView,
  isTaskFormDirty,
  toTaskWrite,
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
      enablers: [],
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
      enablers: [
        { kind: "tool_system", name: "Excel" },
        { kind: "method", name: "交叉檢查" },
      ],
      display_order: 0,
      duty_id: "duty-1",
      competency_level: 4,
    });

    expect(toTaskWrite(form)).toEqual({
      statement: "彙整營運週報",
      purpose_result: "讓主管掌握狀況",
      context: "每週結束時",
      frequency_text: "每週一次",
      responsibility_role: "shared",
      enablers: [
        { kind: "tool_system", name: "Excel" },
        { kind: "method", name: "交叉檢查" },
      ],
      // T6 才有下拉，但往返現在就必須成立：少送一欄就等於送 null，
      // 員工每改一次文字都會把職責歸屬與級別洗掉。
      duty_id: "duty-1",
      competency_level: 4,
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
});
