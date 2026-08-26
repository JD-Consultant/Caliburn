"use client";

import type {
  ApprovedJobDocumentView,
  ConsultantSnapshotEvent,
} from "@caliburn/job-analysis-contract";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, Radio, WifiOff, X } from "lucide-react";
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
import { ConsultantConversation } from "./ConsultantConversation";
import { ConsultantInsightPanel } from "./ConsultantInsightPanel";
import { ConsultantWorkMap } from "./ConsultantWorkMap";
import { CurrentDocumentEditor } from "./CurrentDocumentEditor";
import { CurrentDocumentReview } from "./CurrentDocumentReview";
import { CurrentDocumentSemanticOutline } from "./CurrentDocumentOutline";
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

function ApprovedBaselineDrawer({
  document,
  pendingCount,
  onClose,
}: {
  document: ApprovedJobDocumentView;
  pendingCount: number;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-stone-950/20" role="presentation">
      <button className="min-w-8 flex-1 cursor-default" aria-label="關閉匯出版本" onClick={onClose} />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="匯出版本"
        className="h-full w-full max-w-3xl overflow-y-auto border-l border-stone-200 bg-stone-50 p-5 shadow-2xl sm:p-7"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.16em] text-stone-500 uppercase">只讀核准基線</p>
            <h2 className="mt-1 text-2xl font-semibold">匯出版本</h2>
            <p className="mt-2 text-sm leading-6 text-stone-600">
              這是現在實際會匯出的核准內容。{pendingCount
                ? `目前 ${pendingCount} 項待審 AI 變更不會出現在匯出檔案。`
                : "目前沒有待審 AI 變更。"}
            </p>
          </div>
          <Button variant="ghost" size="icon-sm" aria-label="關閉匯出版本" onClick={onClose}>
            <X />
          </Button>
        </div>
        <div className="mt-6 rounded-xl border border-stone-200 bg-white p-5">
          <p className="text-xs font-medium text-stone-500">職務名稱</p>
          <p className="mt-1 text-lg font-semibold">{document.job_title ?? "未填"}</p>
          {document.work_description ? (
            <>
              <p className="mt-4 text-xs font-medium text-stone-500">工作描述</p>
              <p className="mt-1 text-sm leading-6 text-stone-700">{document.work_description}</p>
            </>
          ) : null}
        </div>
        <div className="mt-5">
          <CurrentDocumentSemanticOutline
            document={document}
            approvedDocument={document}
          />
        </div>
      </aside>
    </div>
  );
}

export function ConsultantWorkspace({ documentId }: { documentId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const metadata = useQuery(consultantDocumentQueryOptions(documentId));
  const snapshotQuery = useQuery(consultantSnapshotQueryOptions(documentId));
  const [documentDirty, setDocumentDirty] = useState(false);
  const [showForceExport, setShowForceExport] = useState(false);
  const [workMapOpen, setWorkMapOpen] = useState(true);
  const [interviewOpen, setInterviewOpen] = useState(true);
  const [documentMode, setDocumentMode] = useState<"current" | "review">("current");
  const [approvedOpen, setApprovedOpen] = useState(false);
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
        正在恢復先前的訪談與目前 JD…
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
  const title = metadata.data?.title ?? snapshot.current_document.job_title ?? "職務分析";
  const layout = `${workMapOpen ? "work-map-" : ""}document${interviewOpen ? "-interview" : ""}`;
  const gridColumns = workMapOpen && interviewOpen
    ? "xl:grid-cols-[minmax(210px,0.28fr)_minmax(0,1fr)_minmax(340px,0.48fr)]"
    : workMapOpen
      ? "xl:grid-cols-[minmax(210px,0.28fr)_minmax(0,1fr)]"
      : interviewOpen
        ? "xl:grid-cols-[minmax(0,1fr)_minmax(340px,0.48fr)]"
        : "xl:grid-cols-1";

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
            目前 JD 有未儲存修改；儲存或取消後才能離頁與匯出。
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

      <main
        data-layout={layout}
        className="mx-auto max-w-[1500px] space-y-9 px-5 py-7 lg:px-8"
      >
        {!workMapOpen || !interviewOpen ? (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              {!workMapOpen ? (
                <Button
                  variant="outline"
                  aria-expanded={false}
                  onClick={() => setWorkMapOpen(true)}
                >
                  開啟工作地圖
                </Button>
              ) : null}
            </div>
            <div>
              {!interviewOpen ? (
                <Button
                  variant="outline"
                  aria-expanded={false}
                  onClick={() => setInterviewOpen(true)}
                >
                  開啟訪談
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
        <div className={`grid grid-cols-1 items-start gap-6 ${gridColumns}`}>
          {workMapOpen ? (
            <ConsultantWorkMap
              snapshot={snapshot}
              onToggle={() => setWorkMapOpen(false)}
            />
          ) : null}
          <div className="min-w-0">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-stone-200 bg-white p-2 shadow-sm">
              <div className="flex gap-1" role="group" aria-label="JD 顯示模式">
                <Button
                  size="sm"
                  variant={documentMode === "current" ? "default" : "ghost"}
                  disabled={documentDirty}
                  onClick={() => setDocumentMode("current")}
                >
                  目前 JD
                </Button>
                <Button
                  size="sm"
                  variant={documentMode === "review" ? "default" : "ghost"}
                  disabled={documentDirty}
                  onClick={() => setDocumentMode("review")}
                >
                  審核變更 {snapshot.document_review.unresolved_action_count}
                </Button>
              </div>
              <Button
                size="sm"
                variant="outline"
                disabled={documentDirty}
                onClick={() => setApprovedOpen(true)}
              >
                查看匯出版本
              </Button>
            </div>
            {documentMode === "current" ? (
              <CurrentDocumentEditor
                key={documentId}
                documentId={documentId}
                snapshot={snapshot}
                onDirtyChange={setDocumentDirty}
              />
            ) : (
              <CurrentDocumentReview
                key={`${documentId}:${snapshot.document_review.workspace_digest}`}
                documentId={documentId}
                snapshot={snapshot}
              />
            )}
          </div>
          {interviewOpen ? (
            <aside aria-label="訪談" className="min-w-0">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold tracking-[0.16em] text-stone-500 uppercase">
                    AI 職務分析顧問
                  </p>
                  <h2 className="mt-1 font-semibold">訪談</h2>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  aria-expanded={true}
                  onClick={() => setInterviewOpen(false)}
                >
                  收合訪談
                </Button>
              </div>
              <div className="space-y-6">
                <ConsultantConversation
                  documentId={documentId}
                  snapshot={snapshot}
                />
                <ConsultantInsightPanel
                  documentId={documentId}
                  snapshot={snapshot}
                />
              </div>
            </aside>
          ) : null}
        </div>
      </main>
      {approvedOpen ? (
        <ApprovedBaselineDrawer
          document={snapshot.approved_document}
          pendingCount={snapshot.document_review.unresolved_action_count}
          onClose={() => setApprovedOpen(false)}
        />
      ) : null}
    </div>
  );
}
