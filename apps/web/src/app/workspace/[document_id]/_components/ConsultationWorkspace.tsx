"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download } from "lucide-react";
import { useState } from "react";

import { Button } from "@/shared/ui/button";
import { GuardedLink } from "@/shared/ui/UnsavedChangesGuard";
import { downloadBlob } from "@/shared/lib/download";
import { exportDocument, JobAnalysisApiError } from "@/shared/api/jobAnalysisApi";
import {
  consultationQueryOptions,
  documentQueryOptions,
} from "@/shared/query/jobAnalysisQueries";
import { DutyEditor, JdHeaderForm, TaskEditor } from "@/features/documents";
import { OpksEditor, documentUnlinkedCompetencies } from "@/features/opks";
import { canExport, exportFilename } from "@/features/export";
import { ConsultationPanel } from "./ConsultationPanel";

export function ConsultationWorkspace({ documentId }: { documentId: string }) {
  const consultation = useQuery(consultationQueryOptions(documentId));
  const document = useQuery(documentQueryOptions(documentId));
  const [headerDraftDirty, setHeaderDraftDirty] = useState(false);
  const [dutyDraftDirty, setDutyDraftDirty] = useState(false);
  const [taskDraftDirty, setTaskDraftDirty] = useState(false);
  const [opksDraftDirty, setOpksDraftDirty] = useState(false);
  const [dutyMutationPending, setDutyMutationPending] = useState(false);
  const [taskMutationPending, setTaskMutationPending] = useState(false);
  const [opksMutationPending, setOpksMutationPending] = useState(false);
  const dirtyState = {
    header: headerDraftDirty,
    duty: dutyDraftDirty,
    task: taskDraftDirty,
    opks: opksDraftDirty,
  };
  const mutationPending =
    dutyMutationPending || taskMutationPending || opksMutationPending;
  const exportAllowed = canExport(dirtyState, mutationPending);
  const dirty = !canExport(dirtyState);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const handleExport = async () => {
    if (!exportAllowed || exporting || !document.data) return;
    setExportError(null);
    setExporting(true);
    try {
      const blob = await exportDocument(documentId);
      downloadBlob(exportFilename(document.data.title), blob);
    } catch (error) {
      setExportError(
        error instanceof JobAnalysisApiError
          ? error.message
          : "匯出失敗，請稍後再試",
      );
    } finally {
      setExporting(false);
    }
  };

  const readinessIssues = document.data?.readiness.issues ?? [];
  const unlinkedCompetencies = document.data
    ? documentUnlinkedCompetencies(document.data.opks_items)
    : [];

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-6 py-5">
          <GuardedLink
            dirty={dirty}
            href="/workspace"
            className="rounded-lg p-2 hover:bg-muted"
            aria-label="返回文件庫"
          >
            <ArrowLeft />
          </GuardedLink>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-xl font-semibold">
              {consultation.data?.document.title ?? "職務分析"}
            </h1>
            <p className="text-xs text-muted-foreground">
              AI 顧問訪談與目前文件
            </p>
          </div>
          <Button
            variant="outline"
            disabled={!exportAllowed || exporting || !document.data}
            onClick={handleExport}
          >
            <Download />
            {exporting ? "準備匯出…" : "匯出 XLSX"}
          </Button>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 pt-6">
        {mutationPending ? (
          <p
            className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm dark:border-amber-900 dark:bg-amber-950/40"
            role="status"
          >
            目前變更尚未完成，請稍候再匯出。
          </p>
        ) : dirty ? (
          <p
            className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm dark:border-amber-900 dark:bg-amber-950/40"
            role="status"
          >
            請先儲存或取消目前編輯，再匯出。
          </p>
        ) : null}
        {!dirty &&
        (readinessIssues.length > 0 || unlinkedCompetencies.length > 0) ? (
          <div
            className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm dark:border-amber-900 dark:bg-amber-950/40"
            role="status"
          >
            <p className="font-medium">匯出前提醒（不會阻擋匯出）</p>
            <ul className="mt-1 list-disc pl-5 text-muted-foreground">
              {readinessIssues.length > 0 ? (
                <li>表頭仍有 {readinessIssues.length} 項欄位缺漏。</li>
              ) : null}
              {unlinkedCompetencies.length > 0 ? (
                <li>
                  有 {unlinkedCompetencies.length} 筆未連結的知識／技能，公版匯出不會包含。
                </li>
              ) : null}
            </ul>
          </div>
        ) : null}
        {exportError ? (
          <p className="mt-3 text-sm text-destructive" role="alert">
            {exportError}
          </p>
        ) : null}
      </div>

      <main className="mx-auto grid max-w-7xl gap-8 px-6 py-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <ConsultationPanel documentId={documentId} />
        <div className="space-y-8">
          <JdHeaderForm
            documentId={documentId}
            onDirtyChange={setHeaderDraftDirty}
          />
          <DutyEditor
            documentId={documentId}
            embedded
            onDirtyChange={setDutyDraftDirty}
            onBusyChange={setDutyMutationPending}
          />
          <TaskEditor
            documentId={documentId}
            embedded
            onDirtyChange={setTaskDraftDirty}
            onBusyChange={setTaskMutationPending}
          />
          <OpksEditor
            documentId={documentId}
            onDirtyChange={setOpksDraftDirty}
            onBusyChange={setOpksMutationPending}
          />
        </div>
      </main>
    </div>
  );
}
