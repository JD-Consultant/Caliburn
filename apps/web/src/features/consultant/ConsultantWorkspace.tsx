"use client";

import type { ConsultantSnapshotEvent } from "@caliburn/job-analysis-contract";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, Radio, WifiOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import {
  consultantEventsUrl,
  exportConsultantDocument,
  JobAnalysisApiError,
} from "@/shared/api/jobAnalysisApi";
import { downloadBlob } from "@/shared/lib/download";
import {
  consultantDocumentQueryOptions,
  consultantInvalidationKeys,
  consultantSnapshotQueryOptions,
} from "@/shared/query/jobAnalysisQueries";
import { Button } from "@/shared/ui/button";
import {
  GuardedLink,
  UnsavedChangesGuard,
} from "@/shared/ui/UnsavedChangesGuard";
import { ApprovedDocumentEditor } from "./ApprovedDocumentEditor";
import { ConsultantConversation } from "./ConsultantConversation";
import { ConsultantInsightPanel } from "./ConsultantInsightPanel";
import { DocumentReviewPanel } from "./DocumentReviewPanel";
import { shouldRefetchForEvent } from "./consultantWorkspaceModel";

function errorText(error: unknown): string {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "無法讀取職務分析，請稍後再試";
}

function exportFilename(title: string): string {
  const safe = title.replace(/[<>:"/\\|?*\r\n]/g, "_").trim() || "職務說明書";
  return `${safe}.xlsx`;
}

export function ConsultantWorkspace({ documentId }: { documentId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const metadata = useQuery(consultantDocumentQueryOptions(documentId));
  const snapshotQuery = useQuery(consultantSnapshotQueryOptions(documentId));
  const [documentDirty, setDocumentDirty] = useState(false);
  const [showForceExport, setShowForceExport] = useState(false);
  const [streamState, setStreamState] = useState<"connecting" | "live" | "reconnecting">("connecting");
  const revisionRef = useRef(-1);

  useEffect(() => {
    revisionRef.current = snapshotQuery.data?.revision ?? -1;
  }, [snapshotQuery.data?.revision]);

  useEffect(() => {
    const stream = new EventSource(consultantEventsUrl(documentId));
    const onSnapshot = (message: MessageEvent<string>) => {
      const event = JSON.parse(message.data) as ConsultantSnapshotEvent;
      if (event.event === "document_deleted") {
        router.replace("/workspace");
        return;
      }
      if (shouldRefetchForEvent(event, documentId, revisionRef.current)) {
        for (const queryKey of consultantInvalidationKeys(documentId)) {
          void queryClient.invalidateQueries({ queryKey });
        }
      }
    };
    stream.onopen = () => setStreamState("live");
    stream.onerror = () => setStreamState("reconnecting");
    stream.addEventListener("snapshot", onSnapshot as EventListener);
    return () => {
      stream.removeEventListener("snapshot", onSnapshot as EventListener);
      stream.close();
    };
  }, [documentId, queryClient, router]);

  const exportMutation = useMutation({
    mutationFn: (force: boolean) => exportConsultantDocument(documentId, force),
    onSuccess: (blob) => {
      downloadBlob(exportFilename(metadata.data?.title ?? "職務說明書"), blob);
      setShowForceExport(false);
    },
    onError: async (error) => {
      if (error instanceof JobAnalysisApiError && error.status === 409) {
        setShowForceExport(true);
        for (const queryKey of consultantInvalidationKeys(documentId)) {
          await queryClient.invalidateQueries({ queryKey });
        }
      }
    },
  });

  if (metadata.isPending || snapshotQuery.isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-stone-50 text-sm text-stone-500">
        正在恢復先前的訪談與正式文件…
      </div>
    );
  }
  if (metadata.isError || snapshotQuery.isError || !snapshotQuery.data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-stone-50 p-6">
        <div className="max-w-md rounded-2xl border border-stone-200 bg-white p-6 text-center shadow-sm">
          <p role="alert" className="text-sm text-destructive">
            {errorText(metadata.error ?? snapshotQuery.error)}
          </p>
          <Button className="mt-4" variant="outline" onClick={() => router.push("/workspace")}>
            返回文件庫
          </Button>
        </div>
      </div>
    );
  }

  const snapshot = snapshotQuery.data;
  const title = metadata.data?.title ?? snapshot.approved_document.job_title ?? "職務分析";

  return (
    <div className="min-h-screen bg-stone-50 text-stone-950">
      <UnsavedChangesGuard dirty={documentDirty} />
      <header className="sticky top-0 z-20 border-b border-stone-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1500px] items-center gap-4 px-5 py-4 lg:px-8">
          <GuardedLink
            dirty={documentDirty}
            href="/workspace"
            className="rounded-lg p-2 hover:bg-stone-100"
            aria-label="返回文件庫"
          >
            <ArrowLeft />
          </GuardedLink>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-semibold">{title}</h1>
            <div className="mt-0.5 flex items-center gap-2 text-xs text-stone-500">
              {streamState === "live" ? (
                <Radio className="size-3 text-emerald-600" />
              ) : (
                <WifiOff className="size-3 text-amber-600" />
              )}
              {streamState === "live" ? "已連線；變更會自動更新" : "連線恢復中；正式狀態仍保存在本機"}
            </div>
          </div>
          <Button
            variant="outline"
            disabled={documentDirty || exportMutation.isPending}
            onClick={() => {
              if (snapshot.readiness.requires_force_confirmation) {
                setShowForceExport(true);
              } else {
                exportMutation.mutate(false);
              }
            }}
          >
            <Download />
            {exportMutation.isPending ? "準備中…" : "匯出 XLSX"}
          </Button>
        </div>
      </header>

      {showForceExport ? (
        <div className="mx-auto max-w-[1500px] px-5 pt-5 lg:px-8">
          <div className="rounded-2xl border border-amber-300 bg-amber-50 p-5 text-sm text-amber-950">
            <p className="font-semibold">匯出前仍有以下缺口</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {snapshot.readiness.issues.map((issue, index) => (
                <li key={`${issue.code}-${issue.subject_id ?? index}`}>{issue.message}</li>
              ))}
            </ul>
            <p className="mt-3 text-xs leading-5 text-amber-900/75">
              強制匯出只會輸出目前已核准內容，不會接受 AI 待審變更、補造缺值或隱藏未分組工作。
            </p>
            <div className="mt-4 flex gap-2">
              <Button
                disabled={exportMutation.isPending || documentDirty}
                onClick={() => exportMutation.mutate(true)}
              >
                我已看過，仍要匯出
              </Button>
              <Button variant="ghost" onClick={() => setShowForceExport(false)}>
                返回處理缺口
              </Button>
            </div>
          </div>
        </div>
      ) : null}
      {documentDirty ? (
        <div className="mx-auto max-w-[1500px] px-5 pt-4 lg:px-8">
          <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-950">
            正式文件有未儲存修改；儲存或取消後才能離頁與匯出。
          </p>
        </div>
      ) : null}
      {exportMutation.isError ? (
        <div className="mx-auto max-w-[1500px] px-5 pt-3 lg:px-8">
          <p role="alert" className="text-sm text-destructive">
            {errorText(exportMutation.error)}
          </p>
        </div>
      ) : null}

      <main className="mx-auto max-w-[1500px] space-y-9 px-5 py-7 lg:px-8">
        <div className="grid items-start gap-7 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
          <ConsultantConversation documentId={documentId} snapshot={snapshot} />
          <ConsultantInsightPanel documentId={documentId} snapshot={snapshot} />
        </div>
        <DocumentReviewPanel documentId={documentId} snapshot={snapshot} />
        <ApprovedDocumentEditor
          key={documentId}
          documentId={documentId}
          snapshot={snapshot}
          onDirtyChange={setDocumentDirty}
        />
      </main>
    </div>
  );
}
