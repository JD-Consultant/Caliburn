import type {
  DocumentReadinessView,
  JdHeaderView,
  JdHeaderWrite,
} from "@caliburn/job-analysis-contract";

/**
 * 表單一律用 string 持有,送出前才 trim 成 null——空字串不是「填了」。
 * `competencyLevel` 也用 string,因為 `<select>` 的值本來就是 string,而且
 * 「未選」必須能表達成清空,不能被 0 之類的數字佔位。
 */
export interface JdHeaderFormValue {
  competencyName: string;
  occupationCategoryName: string;
  occupationName: string;
  occupationCode: string;
  industryName: string;
  industryCode: string;
  workDescription: string;
  competencyLevel: "" | "1" | "2" | "3" | "4" | "5" | "6";
  notes: string;
}

export const COMPETENCY_LEVELS = ["1", "2", "3", "4", "5", "6"] as const;

export function emptyJdHeaderForm(): JdHeaderFormValue {
  return {
    competencyName: "",
    occupationCategoryName: "",
    occupationName: "",
    occupationCode: "",
    industryName: "",
    industryCode: "",
    workDescription: "",
    competencyLevel: "",
    notes: "",
  };
}

function levelOf(value: number | null): JdHeaderFormValue["competencyLevel"] {
  if (value === null) return "";
  const text = String(value);
  return (COMPETENCY_LEVELS as readonly string[]).includes(text)
    ? (text as JdHeaderFormValue["competencyLevel"])
    : "";
}

export function fromJdHeaderView(header: JdHeaderView): JdHeaderFormValue {
  return {
    competencyName: header.competency_name ?? "",
    occupationCategoryName: header.occupation_category_name ?? "",
    occupationName: header.occupation_name ?? "",
    occupationCode: header.occupation_code ?? "",
    industryName: header.industry_name ?? "",
    industryCode: header.industry_code ?? "",
    workDescription: header.work_description ?? "",
    competencyLevel: levelOf(header.competency_level),
    notes: header.notes ?? "",
  };
}

function optionalText(value: string): string | null {
  return value.trim() || null;
}

export function toJdHeaderWrite(value: JdHeaderFormValue): JdHeaderWrite {
  return {
    competency_name: optionalText(value.competencyName),
    occupation_category_name: optionalText(value.occupationCategoryName),
    occupation_name: optionalText(value.occupationName),
    occupation_code: optionalText(value.occupationCode),
    industry_name: optionalText(value.industryName),
    industry_code: optionalText(value.industryCode),
    work_description: optionalText(value.workDescription),
    competency_level: value.competencyLevel
      ? Number(value.competencyLevel)
      : null,
    notes: optionalText(value.notes),
  };
}

export function isJdHeaderFormDirty(
  baseline: JdHeaderFormValue,
  current: JdHeaderFormValue,
): boolean {
  return (
    JSON.stringify(toJdHeaderWrite(baseline)) !==
    JSON.stringify(toJdHeaderWrite(current))
  );
}

/**
 * 缺漏提示的文案。ADR 0052 決定 7:措辭是「iCAP 版型欄位尚有 X 項未填」,
 * **不得**用「不完整」「不合格」「未通過」——我們產出的是客製 JD,不是送審的職能基準。
 *
 * 零 issue 時回 `null`,呼叫端什麼都不渲染(ADR 0053 決定 6:保持安靜,
 * 不宣稱整份 JD 已完整,也不顯示綠色「完成」)。
 */
export function readinessSummary(
  readiness: DocumentReadinessView,
): string | null {
  if (readiness.issues.length === 0) return null;
  return `iCAP 版型欄位尚有 ${readiness.issues.length} 項未填`;
}

const READINESS_FIELD_LABELS: Record<string, string> = {
  competency_name_missing: "職能基準名稱",
  work_description_missing: "工作描述",
  competency_level_missing: "基準級別",
  task_duty_missing: "工作任務的所屬主要職責",
  task_competency_level_missing: "工作任務的職能級別",
  duty_without_task: "主要職責底下的工作任務",
};

export function readinessIssueLabel(code: string): string {
  return READINESS_FIELD_LABELS[code] ?? code;
}
