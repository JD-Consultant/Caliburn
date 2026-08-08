import type {
  DocumentReadinessView,
  JdHeaderView,
  JdHeaderWrite,
  ReadinessIssueView,
} from "@caliburn/job-analysis-contract";

/** 表單先以字串保存；送出時才 trim，空白欄位一律寫成 null。 */
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

export function readinessSummary(
  readiness: DocumentReadinessView,
): string | null {
  if (readiness.issues.length === 0) return null;
  return `iCAP 版型欄位尚有 ${readiness.issues.length} 項未填`;
}

export function readinessIssueLabel(
  code: ReadinessIssueView["code"],
): string {
  switch (code) {
    case "competency_name_missing":
      return "職能基準名稱";
    case "work_description_missing":
      return "工作描述";
    case "competency_level_missing":
      return "基準級別";
    default:
      return assertNever(code);
  }
}

function assertNever(value: never): never {
  throw new Error(`Unmapped readiness issue code: ${value}`);
}
