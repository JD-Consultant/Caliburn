"use client";

import type {
  ConsultantSnapshotView,
  UnderstandingCalibrationDecisionWrite,
} from "@caliburn/job-analysis-contract";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CircleHelp,
  Compass,
  Lightbulb,
  ListChecks,
} from "lucide-react";

import {
  decideUnderstandingCalibration,
  JobAnalysisApiError,
} from "@/shared/api/jobAnalysisApi";
import {
  cacheConsultantSnapshot,
  refreshConsultantQueries,
} from "@/shared/query/jobAnalysisQueries";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import {
  interviewWorkStatusLabel,
  understandingStatusLabel,
  workspaceSections,
} from "./consultantWorkspaceModel";

function errorText(error: unknown): string {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "操作失敗，請稍後再試";
}

const depthLabels = {
  task_boundary: "工作邊界",
  duty_grouping: "職責分組",
  output: "產出 O",
  performance_indicator: "績效 P",
  knowledge: "知識 K",
  skill: "技能 S",
} as const;

const depthStatusLabels: Record<string, string> = {
  evidence_present: "已有證據",
  gap: "仍有缺口",
  interviewing: "訪談中",
  not_yet_deepened: "尚未深入",
  sufficient_for_now: "目前足夠",
  held_with_reason: "有理由暫緩",
};

export function ConsultantInsightPanel({
  documentId,
  snapshot,
  mutationLocked = false,
}: {
  documentId: string;
  snapshot: ConsultantSnapshotView;
  mutationLocked?: boolean;
}) {
  const queryClient = useQueryClient();
  const calibration = snapshot.understanding.calibration;
  const clarification = snapshot.required_clarification;
  const focus = workspaceSections(snapshot).focus;

  const refresh = async () => {
    await refreshConsultantQueries(queryClient, documentId);
  };
  const applySnapshot = async (result: ConsultantSnapshotView) => {
    cacheConsultantSnapshot(queryClient, documentId, result);
    await refresh();
  };

  const calibrationMutation = useMutation({
    mutationFn: (operation: {
      calibrationId: string;
      idempotencyKey: string;
      decision: UnderstandingCalibrationDecisionWrite;
    }) =>
      decideUnderstandingCalibration(
        documentId,
        operation.calibrationId,
        operation.idempotencyKey,
        snapshot.revision,
        operation.decision,
      ),
    onSuccess: async (result) => {
      await applySnapshot(result);
    },
    onError: async (error) => {
      if (error instanceof JobAnalysisApiError && error.status === 409) {
        await refresh();
      }
    },
  });

  const submitCalibration = (
    decision: UnderstandingCalibrationDecisionWrite,
  ) => {
    if (!calibration || mutationLocked || calibrationMutation.isPending) return;
    const previous = calibrationMutation.variables;
    const retry =
      calibrationMutation.isError &&
      previous?.calibrationId === calibration.calibration_id &&
      JSON.stringify(previous.decision) === JSON.stringify(decision);
    calibrationMutation.mutate(
      retry
        ? previous
        : {
            calibrationId: calibration.calibration_id,
            decision,
            idempotencyKey: crypto.randomUUID(),
          },
    );
  };

  return (
    <div className="space-y-5">
      {clarification ? (
        <Card
          className="border-rose-300 bg-rose-50 p-5 shadow-sm"
          aria-label="需要先釐清"
        >
          <div className="flex items-start gap-3">
            <CircleHelp className="mt-0.5 size-5 shrink-0 text-rose-700" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-semibold text-rose-950">
                  這個問題需要你決定
                </h2>
                <Badge variant="destructive">
                  只阻擋：{clarification.affected_branch}
                </Badge>
              </div>
              <p className="mt-2 text-xs leading-5 text-rose-900/75">
                必要澄清已顯示在訪談區；回答後 AI 才會繼續受影響的分析分支。
              </p>
              <p className="mt-3 text-sm text-rose-900">
                請在訪談對話的同一個輸入框回答；選項只會作為快速填入建議，你仍可自由描述。
              </p>
            </div>
          </div>
        </Card>
      ) : null}

      <Card className="border-stone-200 bg-white p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <Compass className="mt-0.5 size-5 shrink-0 text-amber-700" />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold tracking-[0.16em] text-stone-500 uppercase">
              {focus?.label ?? "目前訪談重點"}
            </p>
            {focus ? (
              <>
                <h2 className="mt-1 text-lg font-semibold">{focus.title}</h2>
                <p className="mt-2 text-sm leading-6 text-stone-700">
                  {focus.whyNow}
                </p>
                {focus.missingBeforeEnough ? (
                  <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-950">
                    還差：{focus.missingBeforeEnough}
                  </p>
                ) : null}
                {focus.recommendedNextStep ? (
                  <p className="mt-3 text-sm font-medium text-stone-700">
                    接下來：{focus.recommendedNextStep}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="mt-2 text-sm text-stone-500">
                顧問會依目前線索選擇下一個最值得釐清的工作。
              </p>
            )}
          </div>
        </div>
      </Card>

      <Card className="border-violet-200 bg-violet-50/60 p-5 shadow-sm">
        <details open={Boolean(calibration)}>
          <summary className="cursor-pointer list-none">
            <div className="flex items-center gap-3">
              <Lightbulb className="size-5 text-violet-700" />
              <div className="flex-1">
                <p className="text-xs font-semibold tracking-[0.16em] text-violet-700 uppercase">
                  可修正的理解
                </p>
                <h2 className="mt-1 font-semibold">
                  {snapshot.understanding.label}
                </h2>
              </div>
              <span className="text-xs text-violet-700">展開／收合</span>
            </div>
          </summary>
          <div className="mt-4 space-y-3">
            {snapshot.understanding.items.length === 0 ? (
              <p className="text-sm text-violet-900/70">還在建立初步理解。</p>
            ) : (
              snapshot.understanding.items.map((item) => (
                <div
                  key={item.understanding_id}
                  className="rounded-lg bg-white px-3 py-2 text-sm"
                >
                  <p>{item.text}</p>
                  <p className="mt-1 text-xs text-stone-500">
                    {understandingStatusLabel(item.status)}
                  </p>
                </div>
              ))
            )}
            {snapshot.understanding.parked_clues.length ? (
              <div>
                <p className="text-xs font-medium text-violet-900">
                  稍後處理的線索
                </p>
                <ul className="mt-1 list-disc pl-5 text-sm text-violet-900/80">
                  {snapshot.understanding.parked_clues.map((clue) => (
                    <li key={clue.work_id}>{clue.title}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {calibration && calibration.status === "pending" ? (
              <div className="rounded-xl border border-violet-200 bg-white p-4">
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      calibration.kind === "branch_blocking"
                        ? "destructive"
                        : "secondary"
                    }
                  >
                    {calibration.kind === "branch_blocking"
                      ? "影響後續分析"
                      : "理解校準"}
                  </Badge>
                  <span className="text-xs text-stone-500">
                    請確認 AI 是否理解正確
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {calibration.allowed_actions.includes("confirm") ? (
                    <Button
                      size="sm"
                      disabled={mutationLocked || calibrationMutation.isPending}
                      onClick={() =>
                        submitCalibration({
                          decision: "confirm",
                          employee_text: "我確認以上理解正確。",
                        })
                      }
                    >
                      理解正確
                    </Button>
                  ) : null}
                  {calibration.allowed_actions.includes("later") ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={mutationLocked || calibrationMutation.isPending}
                      onClick={() =>
                        submitCalibration({
                          decision: "later",
                          employee_text: null,
                        })
                      }
                    >
                      稍後再確認
                    </Button>
                  ) : null}
                </div>
                <p className="mt-2 text-xs text-stone-500">
                  若理解不正確，直接在訪談對話補充或更正即可。
                </p>
                {calibrationMutation.isError ? (
                  <p role="alert" className="mt-2 text-sm text-destructive">
                    {errorText(calibrationMutation.error)}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        </details>
      </Card>

      <Card className="border-stone-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <ListChecks className="size-5 text-emerald-700" />
          <div>
            <p className="text-xs font-semibold tracking-[0.16em] text-stone-500 uppercase">
              訪談進度
            </p>
            <h2 className="mt-1 font-semibold">
              目前已辨識 {snapshot.semantic_progress.currently_known_work_count}{" "}
              項工作
            </h2>
          </div>
        </div>

        <div
          aria-label="文件變更決定進度"
          className="mt-4 flex flex-wrap gap-2 text-sm"
        >
          <span className="rounded-full bg-amber-50 px-3 py-1.5 text-amber-900">
            待你確認 {snapshot.semantic_progress.employee_decisions.pending} 項
          </span>
        </div>

        <div className="mt-4 space-y-3">
          {snapshot.semantic_progress.coverage.map((item) => (
            <div
              key={item.work_id}
              className="rounded-lg border border-stone-200 px-3 py-2"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium">{item.title}</p>
                <Badge variant="outline">
                  {interviewWorkStatusLabel(item.status)}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-stone-500">{item.reason}</p>
              {snapshot.semantic_progress.depth
                .filter((depth) => depth.work_id === item.work_id)
                .map((depth) => (
                  <div
                    key={depth.work_id}
                    className="mt-2 flex flex-wrap gap-1.5"
                  >
                    {Object.entries(depthLabels).map(([key, label]) => (
                      <span
                        key={key}
                        className="rounded-full bg-stone-100 px-2 py-1 text-[11px] text-stone-600"
                      >
                        {label}：
                        {depthStatusLabels[
                          depth[key as keyof typeof depthLabels]
                        ] ?? depth[key as keyof typeof depthLabels]}
                      </span>
                    ))}
                  </div>
                ))}
            </div>
          ))}
        </div>

        <div className="mt-5 border-t border-stone-200 pt-4">
          <p className="text-sm font-semibold">具體待處理缺口</p>
          {snapshot.semantic_progress.gaps.filter(
            (gap) => gap.status !== "resolved",
          ).length === 0 ? (
            <p className="mt-2 text-sm text-stone-500">
              目前沒有已知未解缺口。
            </p>
          ) : (
            <ul className="mt-2 space-y-2">
              {snapshot.semantic_progress.gaps
                .filter((gap) => gap.status !== "resolved")
                .map((gap) => (
                  <li key={gap.gap_id} className="flex gap-2 text-sm leading-5">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-700" />
                    <span>
                      {gap.description}
                      {gap.blocks_dependent_analysis
                        ? "（會影響相依分析）"
                        : ""}
                    </span>
                  </li>
                ))}
            </ul>
          )}
        </div>

        <div
          className={`mt-5 rounded-xl p-4 ${snapshot.sufficiency.currently_enough ? "bg-emerald-50" : "bg-amber-50"}`}
        >
          <p className="text-sm font-semibold">
            {snapshot.sufficiency.currently_enough
              ? "目前資訊已足夠"
              : "目前還值得繼續訪談"}
          </p>
          <p className="mt-1 text-sm leading-6">
            {snapshot.sufficiency.why_enough}
          </p>
          <p className="mt-2 text-xs text-stone-600">
            繼續的可能幫助：{snapshot.sufficiency.likely_benefit_of_continuing}
          </p>
          {snapshot.sufficiency.remaining_gap_reasons.length ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-stone-600">
              {snapshot.sufficiency.remaining_gap_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
          {snapshot.sufficiency.needs_recalculation ? (
            <p className="mt-2 text-xs text-stone-500">
              內容剛更新，足夠性正在重新計算。
            </p>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
