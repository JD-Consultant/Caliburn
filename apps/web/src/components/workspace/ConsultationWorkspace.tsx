"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { downloadBlob } from "@/lib/download";
import { exportDocument, JobAnalysisApiError } from "@/lib/jobAnalysisApi";
import { exportFilename } from "@/lib/jobAnalysisExport";
import { consultationQueryOptions } from "@/lib/jobAnalysisQueries";
import { ConsultationPanel } from "./ConsultationPanel";
import { DutyEditor } from "./DutyEditor";
import { JdHeaderForm } from "./JdHeaderForm";
import { OpksEditor } from "./OpksEditor";
import { TaskEditor } from "./TaskEditor";
import { GuardedLink } from "./UnsavedChangesGuard";

export function ConsultationWorkspace({ documentId }: { documentId: string }) {
  const consultation = useQuery(consultationQueryOptions(documentId));
  const [headerDraftDirty, setHeaderDraftDirty] = useState(false);
  const [dutyDraftDirty, setDutyDraftDirty] = useState(false);
  const [taskDraftDirty, setTaskDraftDirty] = useState(false);
  const [opksDraftDirty, setOpksDraftDirty] = useState(false);
  const dirty =
    headerDraftDirty || dutyDraftDirty || taskDraftDirty || opksDraftDirty;
  const title = consultation.data?.document.title ?? "職務分析";

  // 匯出是純讀取,**不需要 dirty guard**——它不會動到任何權威狀態。
  const exportMutation = useMutation({
    mutationFn: async () => {
      const blob = await exportDocument(documentId);
      downloadBlob(exportFilename(title), blob);
    },
  });

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
            <h1 className="truncate text-xl font-semibold">{title}</h1>
            <p className="text-xs text-muted-foreground">
              AI 顧問訪談與目前文件
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Button
              variant="outline"
              disabled={exportMutation.isPending || !consultation.data}
              onClick={() => exportMutation.mutate()}
            >
              <Download />
              {exportMutation.isPending ? "匯出中…" : "匯出"}
            </Button>
            <span
              aria-live="polite"
              className="min-h-4 text-xs text-destructive"
            >
              {exportMutation.isError
                ? exportMutation.error instanceof JobAnalysisApiError
                  ? exportMutation.error.message
                  : "匯出失敗，請稍後再試"
                : null}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-8 px-6 py-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <ConsultationPanel documentId={documentId} />
        <div className="space-y-8">
          <JdHeaderForm
            documentId={documentId}
            onDirtyChange={setHeaderDraftDirty}
          />
          <DutyEditor
            documentId={documentId}
            onDirtyChange={setDutyDraftDirty}
          />
          <TaskEditor
            documentId={documentId}
            embedded
            onDirtyChange={setTaskDraftDirty}
          />
          <OpksEditor
            documentId={documentId}
            onDirtyChange={setOpksDraftDirty}
          />
        </div>
      </main>
    </div>
  );
}
