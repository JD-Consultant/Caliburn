"use client";

import type {
  ApprovedJobDocumentView,
  ConsultantSnapshotView,
  DocumentPatchActionView,
  DocumentReviewDecisionWrite,
} from "@caliburn/job-analysis-contract";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, GitCompareArrows, X } from "lucide-react";
import { useMemo, useState } from "react";

import {
  JobAnalysisApiError,
  reviewDocumentChanges,
} from "@/shared/api/jobAnalysisApi";
import {
  cacheConsultantSnapshot,
  refreshConsultantQueries,
} from "@/shared/query/jobAnalysisQueries";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import {
  DocumentChangeEditor,
  type ReviewValue,
  toReviewValue,
} from "./DocumentChangeEditor";
import { CurrentDocumentSemanticOutline } from "./CurrentDocumentOutline";
import {
  buildDocumentReviewSemanticGroups,
  buildReviewDecision,
  documentPathLabel,
  reviewSelectionForDecision,
} from "./consultantWorkspaceModel";

const headerFields: Array<{
  key: keyof ApprovedJobDocumentView;
  path: string;
  label: string;
}> = [
  { key: "job_title", path: "/job_title", label: "職務名稱" },
  { key: "occupation_category_name", path: "/occupation_category_name", label: "職類名稱" },
  { key: "occupation_name", path: "/occupation_name", label: "職業名稱" },
  { key: "occupation_code", path: "/occupation_code", label: "職業分類代碼" },
  { key: "industry_name", path: "/industry_name", label: "行業名稱" },
  { key: "industry_code", path: "/industry_code", label: "行業分類代碼" },
  { key: "work_description", path: "/work_description", label: "工作描述" },
  { key: "notes", path: "/notes", label: "備註" },
];

function valueText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "未填";
  return typeof value === "string" ? value : JSON.stringify(value);
}

function errorText(error: unknown): string {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "無法保存這項決定，請稍後再試";
}

function HeaderReview({
  document,
  actions,
}: {
  document: ApprovedJobDocumentView;
  actions: DocumentPatchActionView[];
}) {
  return (
    <Card className="border-stone-200 bg-white p-5 shadow-sm">
      <div className="grid gap-4 sm:grid-cols-2">
        {headerFields.map(({ key, path, label }) => {
          const action = actions.find((entry) => entry.path === path);
          const current = document[key];
          if (!action && (current === null || current === "")) return null;
          return (
            <div key={path} data-change-id={action?.action_id}>
              <p className="text-xs font-medium text-stone-500">{label}</p>
              {action?.before !== null && action ? (
                <p className="mt-1 text-sm leading-6 text-rose-700 line-through decoration-rose-400">
                  {valueText(action.before)}
                </p>
              ) : null}
              {action ? (
                action.after !== null ? (
                  <p className="mt-1 rounded-md bg-emerald-50 px-2 py-1 text-sm leading-6 text-emerald-800">
                    {valueText(action.after)}
                  </p>
                ) : null
              ) : (
                <p className="mt-1 text-sm leading-6 text-stone-700">{valueText(current)}</p>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export function CurrentDocumentReview({
  documentId,
  snapshot,
}: {
  documentId: string;
  snapshot: ConsultantSnapshotView;
}) {
  const queryClient = useQueryClient();
  const groups = useMemo(
    () => buildDocumentReviewSemanticGroups(snapshot.document_review.bundles),
    [snapshot.document_review.bundles],
  );
  const [activeKey, setActiveKey] = useState<string | null>(() => groups[0]?.key ?? null);
  const [edits, setEdits] = useState<Record<string, ReviewValue>>(() =>
    Object.fromEntries(
      groups.flatMap((group) =>
        group.actions.map((action) => [action.action_id, toReviewValue(action.after)]),
      ),
    ),
  );
  const [rejectionReason, setRejectionReason] = useState("");
  const [decisionError, setDecisionError] = useState<string | null>(null);

  const activeIndex =
    activeKey === null || !groups.length
      ? null
      : Math.max(0, groups.findIndex((group) => group.key === activeKey));
  const currentGroup = activeIndex === null ? null : groups[activeIndex] ?? null;
  const allActions = groups.flatMap((group) => group.actions);
  const visibleActions = currentGroup?.actions ?? allActions;
  const review = snapshot.document_review;

  const mutation = useMutation({
    mutationFn: (operation: {
      changesetId: string;
      idempotencyKey: string;
      decision: DocumentReviewDecisionWrite;
    }) =>
      reviewDocumentChanges(
        documentId,
        operation.changesetId,
        operation.idempotencyKey,
        snapshot.revision,
        operation.decision,
      ),
    onSuccess: async (result) => {
      cacheConsultantSnapshot(queryClient, documentId, result);
      setRejectionReason("");
      setDecisionError(null);
      await refreshConsultantQueries(queryClient, documentId);
    },
    onError: async (error) => {
      if (error instanceof JobAnalysisApiError && error.status === 409) {
        setDecisionError("文件變更已更新，請重新查看後再決定。");
        await refreshConsultantQueries(queryClient, documentId);
      }
    },
  });

  const decide = (command: DocumentReviewDecisionWrite["command"]) => {
    if (!currentGroup || mutation.isPending) return;
    if (
      currentGroup.bundle.acceptance_blocked &&
      ["accept_changes", "edit_and_accept_changes"].includes(command)
    ) {
      return;
    }
    if (command === "reject_changes" && !rejectionReason.trim()) {
      setDecisionError("拒絕時請簡短說明原因，讓顧問之後不要重複提出同一內容。");
      return;
    }
    const selectedActionIds = currentGroup.actions.map((action) => action.action_id);
    const decidedActionIds = reviewSelectionForDecision(
      currentGroup.bundle,
      selectedActionIds,
      command,
    );
    let editedAfter: DocumentReviewDecisionWrite["edited_after_by_action_id"] = {};
    if (command === "edit_and_accept_changes") {
      editedAfter = Object.fromEntries(
        decidedActionIds.flatMap((actionId) => {
          const action = currentGroup.bundle.actions.find((entry) => entry.action_id === actionId);
          if (!action) return [];
          const value = edits[actionId];
          return JSON.stringify(value) === JSON.stringify(action.after)
            ? []
            : [[actionId, value]];
        }),
      );
      if (!Object.keys(editedAfter).length) {
        setDecisionError("請先修改至少一項 AI 建議，再選擇「修改後接受」。");
        return;
      }
    }
    setDecisionError(null);
    const decision = buildReviewDecision(
      command,
      decidedActionIds,
      editedAfter,
      command === "reject_changes" ? rejectionReason.trim() : null,
    );
    const previous = mutation.variables;
    const retry =
      mutation.isError &&
      previous?.changesetId === currentGroup.changesetId &&
      JSON.stringify(previous.decision) === JSON.stringify(decision);
    mutation.mutate(
      retry
        ? previous
        : {
            changesetId: currentGroup.changesetId,
            idempotencyKey: crypto.randomUUID(),
            decision,
          },
    );
  };

  if (review.workspace_status === "invalid") {
    return (
      <section aria-label="審核變更" className="space-y-4">
        <h2 className="text-2xl font-semibold">審核變更</h2>
        <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm">
          <p className="font-semibold">AI 正在修正目前 JD 的工作內容</p>
          {review.diagnostics.map((diagnostic, index) => (
            <p key={`${diagnostic.code}:${diagnostic.path}:${index}`} className="mt-1 text-stone-700">
              {diagnostic.message}
            </p>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section aria-label="審核變更" className="space-y-4">
      <Card className="sticky top-[76px] z-10 border-stone-200 bg-white/95 p-4 shadow-sm backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="rounded-lg bg-stone-100 p-2 text-stone-700"><GitCompareArrows className="size-5" /></span>
            <div>
              <h2 className="text-xl font-semibold">審核變更</h2>
              <p className="mt-0.5 text-xs text-stone-500">
                {groups.length
                  ? activeIndex === null
                    ? `全部 ${groups.length} 組變更`
                    : `第 ${activeIndex + 1}／${groups.length} 組`
                  : "目前沒有待審變更"}
              </p>
            </div>
          </div>
          {groups.length ? (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => setActiveKey(null)}>
                全部變更
              </Button>
              <Button
                variant="ghost"
                size="sm"
                aria-label="上一組"
                disabled={activeIndex === 0}
                onClick={() => {
                  const targetIndex = activeIndex === null
                    ? groups.length - 1
                    : Math.max(0, activeIndex - 1);
                  setActiveKey(groups[targetIndex]?.key ?? null);
                }}
              >
                <ArrowLeft />上一組
              </Button>
              <Button
                variant="ghost"
                size="sm"
                aria-label="下一組"
                disabled={activeIndex === groups.length - 1}
                onClick={() => {
                  const targetIndex = activeIndex === null
                    ? 0
                    : Math.min(groups.length - 1, activeIndex + 1);
                  setActiveKey(groups[targetIndex]?.key ?? null);
                }}
              >
                下一組<ArrowRight />
              </Button>
            </div>
          ) : null}
        </div>

        {currentGroup ? (
          <div className="mt-4 border-t border-stone-100 pt-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-medium">{currentGroup.summary}</p>
                <p className="mt-1 text-xs text-stone-500">
                  {currentGroup.actions.length > 1
                    ? `這是一個決定，包含 ${currentGroup.actions.length} 項相關變更。`
                    : `影響內容：${documentPathLabel(currentGroup.actions[0].path)}`}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  disabled={mutation.isPending || currentGroup.bundle.acceptance_blocked}
                  onClick={() => decide("accept_changes")}
                >
                  <Check />接受這項變更
                </Button>
                <Button
                  variant="destructive"
                  disabled={mutation.isPending}
                  onClick={() => decide("reject_changes")}
                >
                  <X />拒絕這項變更
                </Button>
              </div>
            </div>
            <label className="mt-3 block text-xs text-stone-500" htmlFor={`review-reason-${currentGroup.key}`}>
              若要拒絕，請簡短說明原因
            </label>
            <input
              id={`review-reason-${currentGroup.key}`}
              className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
              value={rejectionReason}
              onChange={(event) => setRejectionReason(event.target.value)}
            />
            <details className="mt-3 rounded-lg border border-stone-200 bg-stone-50/70 px-3 py-2">
              <summary className="cursor-pointer text-xs font-medium text-stone-600">先修改 AI 建議再接受</summary>
              <div className="mt-3 space-y-3">
                {currentGroup.actions.map((action) => (
                  <div key={action.action_id} className="rounded-lg bg-white p-3">
                    <p className="mb-2 text-xs font-medium text-stone-500">{documentPathLabel(action.path)}</p>
                    <DocumentChangeEditor
                      action={action}
                      value={edits[action.action_id]}
                      approvedDocument={snapshot.approved_document}
                      bundle={currentGroup.bundle}
                      label={documentPathLabel(action.path)}
                      disabled={mutation.isPending}
                      onChange={(value) => setEdits((current) => ({ ...current, [action.action_id]: value }))}
                    />
                  </div>
                ))}
                <Button
                  variant="outline"
                  disabled={mutation.isPending || currentGroup.bundle.acceptance_blocked}
                  onClick={() => decide("edit_and_accept_changes")}
                >
                  修改後接受
                </Button>
              </div>
            </details>
          </div>
        ) : groups.length ? (
          <p className="mt-4 border-t border-stone-100 pt-4 text-sm text-stone-600">
            目前顯示所有差異；使用上一組／下一組逐項決定。
          </p>
        ) : null}
        {decisionError ? <p role="alert" className="mt-3 text-sm text-destructive">{decisionError}</p> : null}
        {mutation.isError ? (
          <p role="alert" className="mt-3 text-sm text-destructive">{errorText(mutation.error)}；目前內容仍保留。</p>
        ) : null}
      </Card>

      {!groups.length ? (
        <div role="status" className="rounded-xl border border-dashed border-stone-300 bg-white px-5 py-8 text-center text-sm text-stone-500">
          目前沒有等待你決定的文件變更。
        </div>
      ) : (
        <>
          <HeaderReview document={snapshot.current_document} actions={visibleActions} />
          <CurrentDocumentSemanticOutline
            document={snapshot.current_document}
            approvedDocument={snapshot.approved_document}
            actions={visibleActions}
          />
        </>
      )}
    </section>
  );
}
