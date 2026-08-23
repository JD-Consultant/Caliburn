"use client";

import type {
  ConsultantRunAccepted,
  ConsultantSnapshotView,
  RequiredClarificationAnswerWrite,
  UnderstandingCalibrationDecisionWrite,
} from "@caliburn/job-analysis-contract";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CircleHelp, Compass, Lightbulb, ListChecks } from "lucide-react";
import { useState } from "react";

import {
  answerRequiredClarification,
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

function isSnapshot(
  value: ConsultantSnapshotView | ConsultantRunAccepted,
): value is ConsultantSnapshotView {
  return "revision" in value;
}

export function ConsultantInsightPanel({
  documentId,
  snapshot,
}: {
  documentId: string;
  snapshot: ConsultantSnapshotView;
}) {
  const queryClient = useQueryClient();
  const [correction, setCorrection] = useState("");
  const [clarificationChoice, setClarificationChoice] = useState("");
  const [clarificationText, setClarificationText] = useState("");
  const calibration = snapshot.understanding.calibration;
  const clarification = snapshot.required_clarification;
  const focus = workspaceSections(snapshot).focus;

  const refresh = async () => {
    await refreshConsultantQueries(queryClient, documentId);
  };
  const applySnapshot = async (
    result: ConsultantSnapshotView | ConsultantRunAccepted,
  ) => {
    if (isSnapshot(result)) {
      cacheConsultantSnapshot(queryClient, documentId, result);
    }
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
        operation.decision.decision === "direct_correction"
          ? null
          : snapshot.revision,
        operation.decision,
      ),
    onSuccess: async (result) => {
      setCorrection("");
      await applySnapshot(result);
    },
    onError: async (error) => {
      if (error instanceof JobAnalysisApiError && error.status === 409) {
        await refresh();
      }
    },
  });

  const clarificationMutation = useMutation({
    mutationFn: (operation: {
      clarificationId: string;
      idempotencyKey: string;
      answer: RequiredClarificationAnswerWrite;
    }) =>
      answerRequiredClarification(
        documentId,
        operation.clarificationId,
        operation.idempotencyKey,
        snapshot.revision,
        operation.answer,
      ),
    onSuccess: async (result) => {
      cacheConsultantSnapshot(queryClient, documentId, result);
      setClarificationChoice("");
      setClarificationText("");
      await refresh();
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
    if (!calibration || calibrationMutation.isPending) return;
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

  const submitClarification = () => {
    if (!clarification || !clarificationChoice || !clarificationText.trim()) return;
    const answer = {
      choice: clarificationChoice,
      text: clarificationText,
    };
    const previous = clarificationMutation.variables;
    const retry =
      clarificationMutation.isError &&
      previous?.clarificationId === clarification.clarification_id &&
      JSON.stringify(previous.answer) === JSON.stringify(answer);
    clarificationMutation.mutate(
      retry
        ? previous
        : {
            clarificationId: clarification.clarification_id,
            answer,
            idempotencyKey: crypto.randomUUID(),
          },
    );
  };

  return (
    <div className="space-y-5">
      {clarification ? (
        <Card className="border-rose-300 bg-rose-50 p-5 shadow-sm" aria-label="需要先釐清">
          <div className="flex items-start gap-3">
            <CircleHelp className="mt-0.5 size-5 shrink-0 text-rose-700" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-semibold text-rose-950">這個問題需要你決定</h2>
                <Badge variant="destructive">只阻擋：{clarification.affected_branch}</Badge>
              </div>
              <p className="mt-2 text-sm font-medium text-rose-950">
                {clarification.question}
              </p>
              <p className="mt-2 text-xs leading-5 text-rose-900/75">
                目前理解：{clarification.current_understanding}
                <br />原因：{clarification.reason}
              </p>
              <div className="mt-4 space-y-2">
                {clarification.choices.map((choice) => (
                  <label key={choice} className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="required-clarification"
                      value={choice}
                      checked={clarificationChoice === choice}
                      onChange={(event) => setClarificationChoice(event.target.value)}
                    />
                    {choice}
                  </label>
                ))}
                <label className="block text-xs font-medium text-rose-900" htmlFor="clarification-detail">
                  用你的話補充
                </label>
                <textarea
                  id="clarification-detail"
                  className="min-h-20 w-full rounded-lg border border-rose-300 bg-white px-3 py-2 text-sm"
                  value={clarificationText}
                  onChange={(event) => setClarificationText(event.target.value)}
                />
                <Button
                  disabled={
                    !clarificationChoice ||
                    !clarificationText.trim() ||
                    clarificationMutation.isPending
                  }
                  onClick={submitClarification}
                >
                  {clarificationMutation.isPending ? "保存中…" : "送出決定"}
                </Button>
                <p className="text-xs text-rose-900/70">
                  其他不受影響的工作仍可繼續訪談，不會整頁鎖住。
                </p>
              </div>
            </div>
          </div>
          {clarificationMutation.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {errorText(clarificationMutation.error)}
            </p>
          ) : null}
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
                <h2 className="mt-1 text-lg font-semibold">
                  {focus.title}
                </h2>
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
                <h2 className="mt-1 font-semibold">{snapshot.understanding.label}</h2>
              </div>
              <span className="text-xs text-violet-700">展開／收合</span>
            </div>
          </summary>
          <div className="mt-4 space-y-3">
            {snapshot.understanding.items.length === 0 ? (
              <p className="text-sm text-violet-900/70">還在建立初步理解。</p>
            ) : (
              snapshot.understanding.items.map((item) => (
                <div key={item.understanding_id} className="rounded-lg bg-white px-3 py-2 text-sm">
                  <p>{item.text}</p>
                  <p className="mt-1 text-xs text-stone-500">
                    {understandingStatusLabel(item.status)}
                  </p>
                </div>
              ))
            )}
            {snapshot.understanding.parked_clues.length ? (
              <div>
                <p className="text-xs font-medium text-violet-900">稍後處理的線索</p>
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
                  <Badge variant={calibration.kind === "branch_blocking" ? "destructive" : "secondary"}>
                    {calibration.kind === "branch_blocking" ? "影響後續分析" : "理解校準"}
                  </Badge>
                  <span className="text-xs text-stone-500">請確認 AI 是否理解正確</span>
                </div>
                <textarea
                  className="mt-3 min-h-20 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  placeholder="若不正確，請直接寫出應如何修正"
                  value={correction}
                  onChange={(event) => setCorrection(event.target.value)}
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  {calibration.allowed_actions.includes("confirm") ? (
                    <Button
                      size="sm"
                      disabled={calibrationMutation.isPending}
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
                  {calibration.allowed_actions.includes("direct_correction") ? (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!correction.trim() || calibrationMutation.isPending}
                      onClick={() =>
                        submitCalibration({
                          decision: "direct_correction",
                          employee_text: correction,
                        })
                      }
                    >
                      送出修正
                    </Button>
                  ) : null}
                  {calibration.allowed_actions.includes("later") ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={calibrationMutation.isPending}
                      onClick={() =>
                        submitCalibration({ decision: "later", employee_text: null })
                      }
                    >
                      稍後再確認
                    </Button>
                  ) : null}
                </div>
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
              目前已辨識 {snapshot.semantic_progress.currently_known_work_count} 項工作
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
          <span className="rounded-full bg-stone-100 px-3 py-1.5 text-stone-700">
            你已延後 {snapshot.semantic_progress.employee_decisions.deferred} 項
          </span>
        </div>

        <div className="mt-4 space-y-3">
          {snapshot.semantic_progress.coverage.map((item) => (
            <div key={item.work_id} className="rounded-lg border border-stone-200 px-3 py-2">
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
                  <div key={depth.work_id} className="mt-2 flex flex-wrap gap-1.5">
                    {Object.entries(depthLabels).map(([key, label]) => (
                      <span
                        key={key}
                        className="rounded-full bg-stone-100 px-2 py-1 text-[11px] text-stone-600"
                      >
                        {label}：{depthStatusLabels[depth[key as keyof typeof depthLabels]] ?? depth[key as keyof typeof depthLabels]}
                      </span>
                    ))}
                  </div>
                ))}
            </div>
          ))}
        </div>

        <div className="mt-5 border-t border-stone-200 pt-4">
          <p className="text-sm font-semibold">具體待處理缺口</p>
          {snapshot.semantic_progress.gaps.filter((gap) => gap.status !== "resolved").length === 0 ? (
            <p className="mt-2 text-sm text-stone-500">目前沒有已知未解缺口。</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {snapshot.semantic_progress.gaps
                .filter((gap) => gap.status !== "resolved")
                .map((gap) => (
                  <li key={gap.gap_id} className="flex gap-2 text-sm leading-5">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-700" />
                    <span>
                      {gap.description}
                      {gap.blocks_dependent_analysis ? "（會影響相依分析）" : ""}
                    </span>
                  </li>
                ))}
            </ul>
          )}
        </div>

        <div className={`mt-5 rounded-xl p-4 ${snapshot.sufficiency.currently_enough ? "bg-emerald-50" : "bg-amber-50"}`}>
          <p className="text-sm font-semibold">
            {snapshot.sufficiency.currently_enough ? "目前資訊已足夠" : "目前還值得繼續訪談"}
          </p>
          <p className="mt-1 text-sm leading-6">{snapshot.sufficiency.why_enough}</p>
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
            <p className="mt-2 text-xs text-stone-500">內容剛更新，足夠性正在重新計算。</p>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
