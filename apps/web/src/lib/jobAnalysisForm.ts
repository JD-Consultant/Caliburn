import type {
  Enabler,
  JdTaskView,
  JdTaskWrite,
} from "@caliburn/job-analysis-contract";

export interface TaskFormValue {
  statement: string;
  purposeResult: string;
  context: string;
  frequencyText: string;
  responsibilityRole: "" | "primary" | "shared" | "assist";
  enablers: Enabler[];
  dutyId: string | null;
  competencyLevel: number | null;
}

export function emptyTaskForm(): TaskFormValue {
  return {
    statement: "",
    purposeResult: "",
    context: "",
    frequencyText: "",
    responsibilityRole: "",
    enablers: [],
    dutyId: null,
    competencyLevel: null,
  };
}

export function fromTaskView(task: JdTaskView): TaskFormValue {
  return {
    statement: task.statement,
    purposeResult: task.purpose_result ?? "",
    context: task.context ?? "",
    frequencyText: task.frequency_text ?? "",
    responsibilityRole: task.responsibility_role ?? "",
    enablers: task.enablers.map((item) => ({ ...item })),
    dutyId: task.duty_id,
    competencyLevel: task.competency_level,
  };
}

function optionalText(value: string): string | null {
  return value.trim() || null;
}

export function toTaskWrite(value: TaskFormValue): JdTaskWrite {
  return {
    statement: value.statement.trim(),
    purpose_result: optionalText(value.purposeResult),
    context: optionalText(value.context),
    frequency_text: optionalText(value.frequencyText),
    responsibility_role: value.responsibilityRole || null,
    enablers: value.enablers
      .map((item) => ({ ...item, name: item.name.trim() }))
      .filter((item) => item.name.length > 0),
    duty_id: value.dutyId,
    competency_level: value.competencyLevel,
  };
}

export function isTaskFormDirty(
  baseline: TaskFormValue,
  current: TaskFormValue,
): boolean {
  return JSON.stringify(baseline) !== JSON.stringify(current);
}
