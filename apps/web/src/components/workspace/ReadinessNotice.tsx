"use client";

import type { DocumentReadinessView } from "@caliburn/job-analysis-contract";

import {
  readinessIssueLabel,
  readinessSummary,
} from "@/lib/jobAnalysisHeader";

/** 只呈現 API 的 issue codes；Web 不自行重算，也不宣稱文件完成。 */
export function ReadinessNotice({
  readiness,
}: {
  readiness: DocumentReadinessView;
}) {
  const summary = readinessSummary(readiness);
  if (summary === null) return null;

  return (
    <div
      className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm dark:border-amber-900 dark:bg-amber-950/40"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <p className="font-medium">{summary}</p>
      <ul className="mt-1 list-disc pl-5 text-muted-foreground">
        {readiness.issues.map((issue) => (
          <li key={issue.code}>{readinessIssueLabel(issue.code)}</li>
        ))}
      </ul>
    </div>
  );
}
