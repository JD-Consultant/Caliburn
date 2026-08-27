"use client";

import type { ConsultantSnapshotView } from "@caliburn/job-analysis-contract";
import { Popover } from "@base-ui/react/popover";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, FileText, X } from "lucide-react";
import { useState } from "react";

import {
  JobAnalysisApiError,
  reviewDocumentChanges,
} from "@/shared/api/jobAnalysisApi";
import {
  cacheConsultantSnapshot,
  refreshConsultantQueries,
  jobAnalysisKeys,
} from "@/shared/query/jobAnalysisQueries";
import { Button } from "@/shared/ui/button";
import {
  buildSemanticReviewIndex,
  documentPathLabel,
  type ReviewDecoration,
} from "./consultantWorkspaceModel";

const operationLabels: Record<ReviewDecoration["operation"], string> = {
  add: "AI 新增",
  update: "AI 修改",
  delete: "AI 移除",
  move: "AI 移動",
};

function errorText(error: unknown): string {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "這組變更目前無法處理，請稍後再試。";
}

function resolveLatestDecoration(
  snapshot: ConsultantSnapshotView,
  previous: ReviewDecoration,
): ReviewDecoration | null {
  const index = buildSemanticReviewIndex(snapshot);
  if (!previous.entityPath) return index.byPath.get(previous.path) ?? null;
  const candidates = index.byEntity.get(previous.entityPath) ?? [];
  return (
    candidates.find((item) => item.path === previous.path) ??
    candidates.find((item) => item.operation === previous.operation) ??
    null
  );
}

export function SemanticReviewPopover({
  documentId,
  snapshot,
  decoration,
  mutationLocked,
  beforeDecision,
  triggerLabel,
}: {
  documentId: string;
  snapshot: ConsultantSnapshotView;
  decoration: ReviewDecoration;
  mutationLocked: boolean;
  beforeDecision: () => Promise<void>;
  triggerLabel: string;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const employeeTitle = /^workspace semantic review$/i.test(
    decoration.group.summary.trim(),
  )
    ? `${operationLabels[decoration.operation]}${documentPathLabel(decoration.path)}`
    : decoration.group.summary;

  const mutation = useMutation({
    mutationKey: jobAnalysisKeys.consultantCurrentDocument(documentId),
    scope: { id: `consultant-current-document:${documentId}` },
    mutationFn: async (operation: {
      command: "accept_changes" | "reject_changes";
      rejectionReason: string | null;
      idempotencyKey: string;
    }) => {
      await beforeDecision();
      const latest =
        queryClient.getQueryData<ConsultantSnapshotView>(
          jobAnalysisKeys.consultantSnapshot(documentId),
        ) ?? snapshot;
      const latestDecoration = resolveLatestDecoration(latest, decoration);
      if (!latestDecoration) {
        return { snapshot: latest, alreadyResolved: true };
      }
      return {
        snapshot: await reviewDocumentChanges(
          documentId,
          latestDecoration.group.changesetId,
          operation.idempotencyKey,
          latest.revision,
          {
            command: operation.command,
            action_ids: latestDecoration.group.actionIds as [
              string,
              ...string[],
            ],
            rejection_reason: operation.rejectionReason,
          },
        ),
        alreadyResolved: false,
      };
    },
    onSuccess: async ({ snapshot: result }) => {
      cacheConsultantSnapshot(queryClient, documentId, result);
      setOpen(false);
      setRejecting(false);
      setRejectionReason("");
      await refreshConsultantQueries(queryClient, documentId);
    },
    onError: async (error) => {
      if (error instanceof JobAnalysisApiError && error.status === 409) {
        await refreshConsultantQueries(queryClient, documentId);
      }
    },
  });

  const decide = (
    command: "accept_changes" | "reject_changes",
    rejectionReasonValue: string | null,
  ) => {
    if (mutationLocked || mutation.isPending) return;
    mutation.mutate({
      command,
      rejectionReason: rejectionReasonValue,
      idempotencyKey: crypto.randomUUID(),
    });
  };

  return (
    <Popover.Root
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) {
          setRejecting(false);
          setRejectionReason("");
        }
      }}
    >
      <Popover.Trigger
        type="button"
        aria-label={triggerLabel}
        className={`inline-flex h-6 items-center rounded-full px-2 text-[11px] font-semibold outline-none ring-offset-2 focus-visible:ring-2 focus-visible:ring-blue-500 ${
          decoration.operation === "delete"
            ? "bg-rose-100 text-rose-700"
            : "bg-emerald-100 text-emerald-800"
        }`}
      >
        {operationLabels[decoration.operation]}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner
          side="bottom"
          align="start"
          sideOffset={8}
          className="z-50"
        >
          <Popover.Popup className="w-[min(24rem,calc(100vw-2rem))] rounded-2xl border border-stone-200 bg-white p-4 text-stone-950 shadow-2xl outline-none">
            <Popover.Title className="text-sm font-semibold">
              {employeeTitle}
            </Popover.Title>
            <Popover.Description className="mt-1 text-xs leading-5 text-stone-500">
              {decoration.group.actionIds.length > 1
                ? `此組 ${decoration.group.actionIds.length} 項變更會一起處理`
                : "這是一項完整變更；接受或拒絕後才會結束審核。"}
            </Popover.Description>
            {decoration.group.dependencyActionIds.length ? (
              <p className="mt-2 text-xs leading-5 text-stone-600">
                伺服器已把相依內容收進同一組；你只需要對整組做一次決定。
              </p>
            ) : null}

            <details className="mt-3 rounded-xl border border-stone-200 bg-stone-50 px-3 py-2">
              <summary className="cursor-pointer text-xs font-medium text-stone-700">
                查看訪談依據
              </summary>
              <div className="mt-2 space-y-2">
                {decoration.group.evidence.length ? (
                  decoration.group.evidence.map((item, index) => (
                    <div
                      key={`${item.sourceId}:${item.quote ?? index}`}
                      className="rounded-lg bg-white px-3 py-2 text-xs leading-5 text-stone-600"
                    >
                      <p className="flex items-center gap-1 font-medium text-stone-800">
                        <FileText className="size-3" /> 員工原話
                      </p>
                      {item.quote ? (
                        <blockquote className="mt-1 border-l-2 border-stone-300 pl-2 text-stone-900">
                          {item.quote}
                        </blockquote>
                      ) : null}
                      {item.sourceText && item.sourceText !== item.quote ? (
                        <p className="mt-1 text-stone-500">
                          對話內容：{item.sourceText}
                        </p>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-stone-500">
                    來源已保存；目前沒有可顯示的逐字引文。
                  </p>
                )}
              </div>
            </details>

            {decoration.group.acceptanceBlocked ? (
              <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
                這組內容目前有衝突，需先拒絕或等待 AI 修正，不能直接接受。
              </p>
            ) : null}

            {rejecting ? (
              <div className="mt-3 rounded-xl bg-stone-50 p-3">
                <label className="block text-xs font-medium text-stone-700">
                  拒絕原因
                  <textarea
                    aria-label="拒絕原因"
                    className="mt-1 min-h-16 w-full resize-y rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                    value={rejectionReason}
                    disabled={mutationLocked || mutation.isPending}
                    onChange={(event) => setRejectionReason(event.target.value)}
                    placeholder="簡短說明哪裡不符合實際工作"
                  />
                </label>
                <div className="mt-2 flex justify-end gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={mutation.isPending}
                    onClick={() => setRejecting(false)}
                  >
                    返回
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    disabled={
                      mutationLocked ||
                      mutation.isPending ||
                      !rejectionReason.trim()
                    }
                    onClick={() =>
                      decide("reject_changes", rejectionReason.trim())
                    }
                  >
                    確認拒絕
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mt-4 flex justify-end gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={mutationLocked || mutation.isPending}
                  onClick={() => setRejecting(true)}
                >
                  <X /> 拒絕整組變更
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={
                    mutationLocked ||
                    mutation.isPending ||
                    decoration.group.acceptanceBlocked
                  }
                  onClick={() => decide("accept_changes", null)}
                >
                  <Check /> 接受整組變更
                </Button>
              </div>
            )}

            {mutation.isError ? (
              <p role="alert" className="mt-3 text-xs text-rose-700">
                {errorText(mutation.error)}
              </p>
            ) : null}
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}
