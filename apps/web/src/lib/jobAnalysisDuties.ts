import type { DutyView, JdTaskView } from "@caliburn/job-analysis-contract";

/**
 * Current JD 的兩層呈現：主要職責 → 工作任務。
 *
 * **不產生 `T1`／`T1.1`。** 那是匯出時依排序決定性算出的版面位置碼，不是畫面上的
 * identity（ADR 0052 決定 10）。畫面顯示職責敘述本身。
 */
export interface DutyGroup {
  /** `null` 代表「尚未歸入主要職責」那一區。 */
  duty: DutyView | null;
  tasks: JdTaskView[];
}

/** 未歸入職責的工作任務那一區的標題。缺漏要在成品上看得見（ADR 0052 決定 5）。 */
export const UNASSIGNED_GROUP_LABEL = "尚未歸入主要職責";

export const TASK_COMPETENCY_LEVELS = ["1", "2", "3", "4", "5", "6"] as const;

/**
 * 依主要職責分組。職責照傳入順序（API 已是 canonical），任務照各自的順序。
 *
 * 三條刻意的行為：
 *
 * - **空職責照樣出現**——那正是 `duty_without_task` 要讓人看見的缺漏，藏起來就沒意義。
 * - **未指派那一區只在真的有任務時出現**——沒有缺漏就不要憑空多一個空區塊。
 * - **任何任務都不會消失**。`duty_id` 指向不存在的職責在 API 那端是不可表示的狀態，
 *   但這裡仍把它歸進未指派區而不是丟掉：畫面少一條任務比多一條錯位的任務難發現得多。
 */
export function groupTasksByDuty(
  duties: readonly DutyView[],
  tasks: readonly JdTaskView[],
): DutyGroup[] {
  const groups = new Map<string, JdTaskView[]>(
    duties.map((duty) => [duty.duty_id, []]),
  );
  const unassigned: JdTaskView[] = [];

  for (const task of tasks) {
    const bucket = task.duty_id === null ? undefined : groups.get(task.duty_id);
    if (bucket) bucket.push(task);
    else unassigned.push(task);
  }

  const result: DutyGroup[] = duties.map((duty) => ({
    duty,
    tasks: groups.get(duty.duty_id) ?? [],
  }));
  if (unassigned.length > 0) result.push({ duty: null, tasks: unassigned });
  return result;
}

/** 下拉選單用的職責標籤。沒有位置碼，就是敘述本身。 */
export function dutyOptionLabel(duty: DutyView): string {
  return duty.statement;
}

export function competencyLevelLabel(level: number | null): string {
  return level === null ? "尚未填寫" : `第 ${level} 級`;
}

export function dutyLabelFor(
  duties: readonly DutyView[],
  dutyId: string | null,
): string {
  if (dutyId === null) return UNASSIGNED_GROUP_LABEL;
  return duties.find((duty) => duty.duty_id === dutyId)?.statement
    ?? UNASSIGNED_GROUP_LABEL;
}
