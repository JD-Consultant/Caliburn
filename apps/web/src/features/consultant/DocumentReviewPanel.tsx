"use client";

import type {
  ApprovedJobDocumentView,
  ConsultantSnapshotView,
  DocumentChangeSetView,
  DocumentPatchActionView,
  DocumentReviewDecisionWrite,
} from "@caliburn/job-analysis-contract";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileCheck2, LockKeyhole } from "lucide-react";
import { useState } from "react";

import {
  JobAnalysisApiError,
  reviewDocumentChanges,
} from "@/shared/api/jobAnalysisApi";
import {
  cacheConsultantSnapshot,
  refreshConsultantQueries,
} from "@/shared/query/jobAnalysisQueries";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import {
  DocumentChangeEditor,
  DocumentChangePreview,
  type ReviewValue,
  toReviewValue,
} from "./DocumentChangeEditor";
import {
  buildReviewDecision,
  documentPathLabel,
  reviewSelectionForAction,
  reviewSelectionForDecision,
} from "./consultantWorkspaceModel";

const operationLabels: Record<DocumentPatchActionView["operation"], string> = {
  add: "新增",
  revise: "修改",
  withdraw: "移除",
  reassign: "重新歸類",
  reorder: "調整順序",
};

const statusLabels: Record<DocumentPatchActionView["status"], string> = {
  pending: "待確認",
};

function errorText(error: unknown): string {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "無法保存這項決定，請稍後再試";
}

function diagnosticRenderKeys(
  diagnostics: ConsultantSnapshotView["document_review"]["diagnostics"],
): string[] {
  const occurrences = new Map<string, number>();
  return diagnostics.map((diagnostic) => {
    const identity = JSON.stringify([
      diagnostic.code,
      diagnostic.path,
      diagnostic.message,
    ]);
    const occurrence = occurrences.get(identity) ?? 0;
    occurrences.set(identity, occurrence + 1);
    return `${identity}:${occurrence}`;
  });
}

function ReviewBundle({
  documentId,
  revision,
  bundleOrdinal,
  bundle,
  approvedDocument,
}: {
  documentId: string;
  revision: number;
  bundleOrdinal: number;
  bundle: DocumentChangeSetView;
  approvedDocument: ApprovedJobDocumentView;
}) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const [edits, setEdits] = useState<Record<string, ReviewValue>>(() =>
    Object.fromEntries(
      bundle.actions.map((action) => [
        action.action_id,
        toReviewValue(action.after),
      ]),
    ),
  );
  const [rejectionReason, setRejectionReason] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (operation: {
      idempotencyKey: string;
      decision: DocumentReviewDecisionWrite;
    }) =>
      reviewDocumentChanges(
        documentId,
        bundle.changeset_id,
        operation.idempotencyKey,
        revision,
        operation.decision,
      ),
    onSuccess: async (result) => {
      cacheConsultantSnapshot(queryClient, documentId, result);
      setSelected([]);
      setRejectionReason("");
      setEditError(null);
      await refreshConsultantQueries(queryClient, documentId);
    },
    onError: async (error) => {
      if (error instanceof JobAnalysisApiError && error.status === 409) {
        setSelected([]);
        setRejectionReason("");
        setEditError("文件變更已更新，請重新查看後再決定。");
        await refreshConsultantQueries(queryClient, documentId);
      }
    },
  });

  const toggle = (actionId: string) => {
    const group = reviewSelectionForAction(bundle, actionId);
    setSelected((current) => {
      const allSelected = group.every((id) => current.includes(id));
      return allSelected
        ? current.filter((id) => !group.includes(id))
        : [...new Set([...current, ...group])];
    });
  };

  const decide = (command: DocumentReviewDecisionWrite["command"]) => {
    if (!selected.length || mutation.isPending) return;
    if (
      bundle.acceptance_blocked &&
      ["accept_changes", "edit_and_accept_changes"].includes(command)
    ) {
      return;
    }
    if (command === "reject_changes" && !rejectionReason.trim()) {
      setEditError("拒絕時請簡短說明原因，讓顧問之後不要重複提出同一內容。");
      return;
    }
    const decidedActionIds = reviewSelectionForDecision(
      bundle,
      selected,
      command,
    );
    let edited: DocumentReviewDecisionWrite["edited_after_by_action_id"] = {};
    if (command === "edit_and_accept_changes") {
      edited = Object.fromEntries(
        decidedActionIds.flatMap((actionId) => {
          const action = bundle.actions.find((item) => item.action_id === actionId)!;
          const value = edits[actionId];
          return JSON.stringify(value) === JSON.stringify(action.after)
            ? []
            : [[actionId, value]];
        }),
      );
      if (Object.keys(edited).length === 0) {
        setEditError("請先修改至少一項 AI 建議，再選擇「修改後接受」。");
        return;
      }
      setEditError(null);
    }
    const decision = buildReviewDecision(
      command,
      decidedActionIds,
      edited,
      command === "reject_changes" ? rejectionReason.trim() || null : null,
    );
    const previous = mutation.variables;
    const retry =
      mutation.isError &&
      JSON.stringify(previous?.decision) === JSON.stringify(decision);
    mutation.mutate(
      retry
        ? previous!
        : { decision, idempotencyKey: crypto.randomUUID() },
    );
  };

  const active = bundle.actions.filter((action) =>
    action.status === "pending",
  );

  return (
    <Card className="border-stone-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-[0.16em] text-stone-500 uppercase">
            一組相關變更
          </p>
          <h3 className="mt-1 font-semibold">{bundle.summary}</h3>
        </div>
        <Badge variant="outline">{active.length} 項待處理</Badge>
      </div>

      <div className="mt-4 space-y-3">
        {bundle.actions.map((action, index) => {
          const reviewable = action.status === "pending";
          const selectionLabel = `選取第 ${bundleOrdinal} 組第 ${index + 1} 項${operationLabels[action.operation]}變更：${documentPathLabel(action.path)}（${bundle.summary}）${action.atomic_subgroup_id ? "；必須整組決定" : ""}`;
          return (
            <div
              key={action.action_id}
              className={`rounded-xl border p-4 ${
                selected.includes(action.action_id)
                  ? "border-stone-900 bg-stone-50"
                  : "border-stone-200"
              }`}
            >
              <div className="flex items-start gap-3">
                <input
                  className="mt-1"
                  type="checkbox"
                  aria-label={selectionLabel}
                  checked={selected.includes(action.action_id)}
                  disabled={!reviewable || mutation.isPending}
                  onChange={() => toggle(action.action_id)}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{operationLabels[action.operation]}</Badge>
                    <span className="text-xs text-stone-500">{statusLabels[action.status]}</span>
                    {action.atomic_subgroup_id ? (
                      <span className="inline-flex items-center gap-1 text-xs text-stone-500">
                        <LockKeyhole className="size-3" /> 必須整組決定
                      </span>
                    ) : null}
                    {action.blocks_dependent_analysis ? (
                      <Badge variant="destructive">會阻擋相依分析</Badge>
                    ) : null}
                  </div>
                  <p className="mt-2 text-xs text-stone-500">
                    影響內容：{documentPathLabel(action.path)}
                  </p>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <div>
                      <p className="text-xs font-medium text-stone-500">目前正式內容</p>
                      <DocumentChangePreview
                        action={action}
                        value={action.before}
                        approvedDocument={approvedDocument}
                        bundle={bundle}
                      />
                    </div>
                    <div>
                      <p className="mb-1 text-xs font-medium text-stone-500">
                        AI 建議（可直接修改）
                      </p>
                      <DocumentChangeEditor
                        action={action}
                        value={edits[action.action_id]}
                        approvedDocument={approvedDocument}
                        bundle={bundle}
                        label={documentPathLabel(action.path)}
                        disabled={!reviewable || mutation.isPending}
                        onChange={(value) =>
                          setEdits((current) => ({
                            ...current,
                            [action.action_id]: value,
                          }))
                        }
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {selected.length ? (
        <div className="mt-4 rounded-xl bg-stone-50 p-4">
          <p className="text-sm font-medium">已選 {selected.length} 項</p>
          <label className="mt-3 block text-xs text-stone-500" htmlFor={`reject-${bundle.changeset_id}`}>
            若要拒絕，可補充原因
          </label>
          <input
            id={`reject-${bundle.changeset_id}`}
            className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
            value={rejectionReason}
            onChange={(event) => setRejectionReason(event.target.value)}
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              disabled={mutation.isPending || bundle.acceptance_blocked}
              onClick={() => decide("accept_changes")}
            >
              接受 AI 建議
            </Button>
            <Button
              variant="outline"
              disabled={mutation.isPending || bundle.acceptance_blocked}
              onClick={() => decide("edit_and_accept_changes")}
            >
              修改後接受
            </Button>
            <Button
              variant="destructive"
              disabled={mutation.isPending}
              onClick={() => decide("reject_changes")}
            >
              拒絕
            </Button>
          </div>
        </div>
      ) : null}

      {editError ? (
        <p role="alert" className="mt-3 text-sm text-destructive">{editError}</p>
      ) : null}
      {mutation.isError ? (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {errorText(mutation.error)}；請重新查看目前內容後再決定。
        </p>
      ) : null}
    </Card>
  );
}

export function DocumentReviewPanel({
  documentId,
  snapshot,
}: {
  documentId: string;
  snapshot: ConsultantSnapshotView;
}) {
  const activeBundles = snapshot.document_review.bundles.filter((bundle) =>
    bundle.actions.some((action) => action.status === "pending"),
  );
  const review = snapshot.document_review;
  const diagnosticKeys = diagnosticRenderKeys(review.diagnostics);
  const isInvalid = review.workspace_status === "invalid";
  const isConflicted = review.workspace_status === "conflicted";
  const statusMessage = isInvalid
    ? "AI 正在修正工作草稿"
    : isConflicted
      ? "正式文件與工作草稿需要你選擇"
      : review.workspace_status === "clean"
        ? "目前沒有等待你決定的文件變更。"
        : "AI 建議的文件變更";

  return (
    <section className="space-y-4" aria-label="AI 文件變更審核">
      <div className="flex items-center gap-3">
        <div className="rounded-lg bg-emerald-100 p-2 text-emerald-800">
          <FileCheck2 className="size-5" />
        </div>
        <div>
          <p className="text-xs font-semibold tracking-[0.16em] text-stone-500 uppercase">
            正式文件權限
          </p>
          <h2 className="text-lg font-semibold">{statusMessage}</h2>
          <p className="text-xs text-stone-500">
            接受或修改後接受，才會更新下方正式文件。
          </p>
        </div>
      </div>

      {review.workspace_status === "pending" ? (
        <p role="status" className="sr-only">
          {statusMessage}
        </p>
      ) : null}

      {isInvalid || isConflicted ? (
        <div
          role={isConflicted ? "alert" : "status"}
          className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm"
        >
          <p className="font-medium">{statusMessage}</p>
          {review.diagnostics.map((diagnostic, index) => (
            <p key={diagnosticKeys[index]} className="mt-1 text-stone-700">
              {diagnostic.message}
            </p>
          ))}
        </div>
      ) : null}
      {isInvalid ? null : activeBundles.length === 0 ? (
        <div role="status" className="rounded-xl border border-dashed border-stone-300 bg-white px-5 py-8 text-center text-sm text-stone-500">
          目前沒有等待你決定的文件變更。
        </div>
      ) : (
        activeBundles.map((bundle, index) => (
          <ReviewBundle
            key={bundle.changeset_id}
            documentId={documentId}
            revision={snapshot.revision}
            bundleOrdinal={index + 1}
            bundle={bundle}
            approvedDocument={snapshot.approved_document}
          />
        ))
      )}
    </section>
  );
}
