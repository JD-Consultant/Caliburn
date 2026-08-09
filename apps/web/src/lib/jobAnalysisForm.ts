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
  dutyId: string;
  competencyLevel: "" | "1" | "2" | "3" | "4" | "5" | "6";
  enablers: Enabler[];
}

export function emptyTaskForm(): TaskFormValue {
  return {
    statement: "",
    purposeResult: "",
    context: "",
    frequencyText: "",
    responsibilityRole: "",
    dutyId: "",
    competencyLevel: "",
    enablers: [],
  };
}

export function fromTaskView(task: JdTaskView): TaskFormValue {
  return {
    statement: task.statement,
    purposeResult: task.purpose_result ?? "",
    context: task.context ?? "",
    frequencyText: task.frequency_text ?? "",
    responsibilityRole: task.responsibility_role ?? "",
    dutyId: task.duty_id ?? "",
    competencyLevel:
      task.competency_level === null || task.competency_level === undefined
        ? ""
        : String(task.competency_level) as TaskFormValue["competencyLevel"],
    enablers: task.enablers.map((item) => ({ ...item })),
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
    duty_id: value.dutyId || null,
    competency_level:
      value.competencyLevel === "" ? null : Number(value.competencyLevel),
    enablers: value.enablers
      .map((item) => ({ ...item, name: item.name.trim() }))
      .filter((item) => item.name.length > 0),
  };
}

export function isTaskFormDirty(
  baseline: TaskFormValue,
  current: TaskFormValue,
): boolean {
  return JSON.stringify(baseline) !== JSON.stringify(current);
}

export function moveTaskWithinDuty(
  tasks: Array<Pick<JdTaskView, "task_id" | "duty_id">>,
  taskId: string,
  dutyId: string | null,
  offset: -1 | 1,
): string[] {
  const visibleGroup = tasks.filter((task) => (task.duty_id ?? null) === dutyId);
  const index = visibleGroup.findIndex((task) => task.task_id === taskId);
  const target = index + offset;
  if (index < 0 || target < 0 || target >= visibleGroup.length) {
    return tasks.map((task) => task.task_id);
  }

  const next = tasks.map((task) => task.task_id);
  const currentGlobalIndex = next.indexOf(taskId);
  const targetGlobalIndex = next.indexOf(visibleGroup[target].task_id);
  [next[currentGlobalIndex], next[targetGlobalIndex]] = [
    next[targetGlobalIndex],
    next[currentGlobalIndex],
  ];
  return next;
}
