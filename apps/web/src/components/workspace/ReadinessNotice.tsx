"use client";

import type { DocumentReadinessView } from "@caliburn/job-analysis-contract";

import { readinessIssueLabel, readinessSummary } from "@/lib/jobAnalysisHeader";

/**
 * 只呈現 API 回來的缺漏,**不自行重算**(ADR 0052 決定 3)。
 * 零 issue 時什麼都不渲染:不宣稱整份 JD 已完整,也沒有綠色「完成」(ADR 0053 決定 6)。
 * 缺漏只提示、不阻止保存／訪談／匯出(ADR 0052 決定 5)。
 */
export function ReadinessNotice({
  readiness,
}: {
  readiness: DocumentReadinessView;
}) {
  const summary = readinessSummary(readiness);
  if (summary === null) return null;

  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm dark:border-amber-900 dark:bg-amber-950/40">
      <p className="font-medium">{summary}</p>
      <ul className="mt-1 list-disc pl-5 text-muted-foreground">
        {readiness.issues.map((issue) => (
          <li key={issue.code}>{readinessIssueLabel(issue.code)}</li>
        ))}
      </ul>
    </div>
  );
}
