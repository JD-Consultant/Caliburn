"use client";

import type {
  ConsultantRunAccepted,
  ConsultantSnapshotView,
} from "@caliburn/job-analysis-contract";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  CheckCircle2,
  RotateCcw,
  Send,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useMemo, useState } from "react";

import {
  answerRequiredClarification,
  JobAnalysisApiError,
  retryConsultantRun,
  submitConsultantAnswer,
} from "@/shared/api/jobAnalysisApi";
import {
  jobAnalysisKeys,
  refreshConsultantQueries,
} from "@/shared/query/jobAnalysisQueries";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import {
  EXTERNAL_AI_DISCLOSURE,
  buildConversationEntries,
  consultantRunStatus,
} from "./consultantWorkspaceModel";

function errorText(error: unknown): string {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "顧問暫時無法處理，請稍後重試";
}

type ConversationSubmission = {
  text: string;
  idempotencyKey: string;
  clarificationId: string | null;
  expectedRevision: number;
};

export function ConsultantConversation({
  documentId,
  snapshot,
  mutationLocked = false,
  beforeSubmit,
}: {
  documentId: string;
  snapshot: ConsultantSnapshotView;
  mutationLocked?: boolean;
  beforeSubmit?: () => Promise<void>;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [preparingSubmission, setPreparingSubmission] = useState(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const entries = useMemo(() => buildConversationEntries(snapshot), [snapshot]);
  const runStatus = consultantRunStatus(snapshot);
  const runFailed = snapshot.run?.status === "failed";
  const clarification = snapshot.required_clarification;
  const latestQuestion = [...snapshot.messages]
    .reverse()
    .find((message) => message.next_question)?.next_question;

  const refresh = async () => {
    await refreshConsultantQueries(queryClient, documentId);
  };
  const answerMutation = useMutation<
    ConsultantSnapshotView | ConsultantRunAccepted,
    Error,
    ConversationSubmission
  >({
    mutationKey: jobAnalysisKeys.consultantAnalysisAdmission(documentId),
    mutationFn: (operation) =>
      operation.clarificationId
        ? answerRequiredClarification(
            documentId,
            operation.clarificationId,
            operation.idempotencyKey,
            operation.expectedRevision,
            { text: operation.text },
          )
        : submitConsultantAnswer(documentId, operation.idempotencyKey, {
            text: operation.text,
          }),
    onSuccess: async () => {
      setDraft("");
      await refresh();
    },
    onError: async (error) => {
      if (error instanceof JobAnalysisApiError && error.status === 409) {
        await refresh();
      }
    },
  });
  const retryMutation = useMutation({
    mutationKey: jobAnalysisKeys.consultantAnalysisAdmission(documentId),
    mutationFn: (runId: string) => retryConsultantRun(documentId, runId),
    onSuccess: refresh,
  });
  const localMutationPending =
    preparingSubmission || answerMutation.isPending || retryMutation.isPending;

  const send = async () => {
    const text = draft;
    if (
      !text.trim() ||
      mutationLocked ||
      runStatus.busy ||
      preparingSubmission ||
      answerMutation.isPending
    )
      return;
    setPreparingSubmission(true);
    setSubmissionError(null);
    try {
      await beforeSubmit?.();
    } catch {
      setSubmissionError("請先完成目前 JD 儲存，再送出這則訊息。");
      setPreparingSubmission(false);
      return;
    }
    const latestSnapshot =
      queryClient.getQueryData<ConsultantSnapshotView>(
        jobAnalysisKeys.consultantSnapshot(documentId),
      ) ?? snapshot;
    const previous = answerMutation.variables;
    const sameFailedInput =
      answerMutation.isError &&
      previous?.text === text &&
      previous.clarificationId ===
        (latestSnapshot.required_clarification?.clarification_id ?? null) &&
      previous.expectedRevision === latestSnapshot.revision;
    answerMutation.mutate(
      sameFailedInput
        ? previous
        : {
            text,
            idempotencyKey: crypto.randomUUID(),
            clarificationId:
              latestSnapshot.required_clarification?.clarification_id ?? null,
            expectedRevision: latestSnapshot.revision,
          },
    );
    setPreparingSubmission(false);
  };

  return (
    <section
      className="flex h-full min-h-0 flex-col gap-3"
      aria-label="AI 職務分析顧問對話"
    >
      <div
        data-slot="conversation-scroll-region"
        className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1"
      >
        <div className="rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-950">
          <div className="flex gap-3">
            <ShieldCheck className="mt-0.5 size-5 shrink-0 text-sky-700" />
            <div>
              <p className="font-semibold">外部 AI 與文件權限</p>
              <p className="mt-1 leading-6 text-sky-900/80">
                {EXTERNAL_AI_DISCLOSURE}
              </p>
            </div>
          </div>
        </div>

        {snapshot.opening_navigation.visible ? (
          <Card className="border-amber-200 bg-amber-50 p-5">
            <p className="text-xs font-semibold tracking-[0.16em] text-amber-800 uppercase">
              訪談會怎麼進行
            </p>
            <ol className="mt-1 grid gap-2 text-sm leading-6 text-amber-950">
              {snapshot.opening_navigation.steps.map((step, index) => (
                <li key={step} className="flex gap-3">
                  <span className="font-semibold text-amber-700">
                    {index + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </Card>
        ) : null}

        <Card className="border-stone-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold tracking-[0.16em] text-stone-500 uppercase">
                訪談對話
              </p>
              <h2 className="mt-1 text-lg font-semibold">
                一次談清楚一個重點
              </h2>
            </div>
            {snapshot.run?.status === "completed" ? (
              <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
                <CheckCircle2 className="size-4" /> 已保存
              </span>
            ) : null}
          </div>

          <div className="mt-2">
            <div
              role="log"
              aria-label="訪談紀錄"
              className="space-y-4 rounded-xl bg-stone-50 p-4"
            >
              {entries.length === 0 ? (
                <div className="py-8 text-center text-sm text-stone-500">
                  <Bot className="mx-auto mb-3 size-7" />
                  先用自己的話說說：你主要負責哪些工作？
                </div>
              ) : (
                entries.map((entry) => (
                  <div
                    key={entry.key}
                    className={entry.speaker === "employee" ? "ml-8" : "mr-8"}
                  >
                    <div
                      className={`mb-1 flex items-center gap-1.5 text-xs text-stone-500 ${
                        entry.speaker === "employee"
                          ? "justify-end"
                          : "justify-start"
                      }`}
                    >
                      {entry.speaker === "employee" ? <UserRound /> : <Bot />}
                      {entry.speaker === "employee" ? "你" : "顧問"}
                      {entry.pending ? " · 已保存，待分析" : null}
                    </div>
                    <div
                      className={`rounded-2xl px-4 py-3 text-sm leading-6 whitespace-pre-wrap ${
                        entry.speaker === "employee"
                          ? "bg-stone-900 text-white"
                          : "border border-stone-200 bg-white"
                      }`}
                    >
                      {entry.text}
                    </div>
                  </div>
                ))
              )}
            </div>

          {latestQuestion ? (
            <div className="mt-4 rounded-xl border border-stone-200 bg-stone-50 px-4 py-3">
              <p className="text-xs font-medium text-stone-500">目前問題</p>
              <p className="mt-1 text-sm font-medium">{latestQuestion.text}</p>
              <p className="mt-1 text-xs leading-5 text-stone-500">
                為什麼問：{latestQuestion.reason}
              </p>
            </div>
          ) : null}

          {runFailed ? (
            <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-950">
              上一則回答已保存，但分析失敗。你可以重試同一則回答，也可以直接傳送新的補充或更正；兩則都會保留在訪談紀錄中。
            </div>
          ) : null}

          {clarification ? (
            <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3">
              <p className="text-xs font-semibold text-rose-800">需要先釐清</p>
              <p className="mt-1 text-sm font-medium text-rose-950">
                {clarification.question}
              </p>
              <p className="mt-1 text-xs leading-5 text-rose-900/75">
                {clarification.reason}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {clarification.choices.map((choice) => (
                  <Button
                    key={choice}
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={mutationLocked || localMutationPending}
                    onClick={() => setDraft(choice)}
                  >
                    {choice}
                  </Button>
                ))}
              </div>
              <p className="mt-2 text-xs text-rose-900/70">
                選項只是快速填入，你也可以在同一個輸入框自由回答。
              </p>
            </div>
          ) : null}
          </div>
        </Card>
      </div>

      <form
        className="shrink-0 space-y-2 rounded-xl border border-stone-200 bg-white p-3 shadow-sm"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <label htmlFor="employee-answer" className="sr-only">
          回覆顧問
        </label>
        <textarea
          id="employee-answer"
          className="min-h-32 w-full rounded-xl border border-stone-300 bg-white px-4 py-3 text-sm leading-6"
          value={draft}
          disabled={
            mutationLocked ||
            runStatus.busy ||
            answerMutation.isPending ||
            preparingSubmission
          }
          placeholder={
            clarification?.question ??
            latestQuestion?.text ??
            snapshot.current_interview?.recommended_next_step ??
            "用自己的話描述實際工作；想到其他工作也可以一起說。"
          }
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
              event.preventDefault();
              void send();
            }
          }}
        />
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-stone-500">Ctrl/Cmd + Enter 送出</span>
          <Button
            type="submit"
            disabled={
              !draft.trim() ||
              mutationLocked ||
              runStatus.busy ||
              preparingSubmission ||
              answerMutation.isPending
            }
          >
            <Send />
            {preparingSubmission
              ? "準備送出…"
              : answerMutation.isPending
                ? "保存中…"
                : clarification
                  ? "送出澄清"
                  : "送出回答"}
          </Button>
        </div>
      </form>

      <div role="status" aria-live="polite" className="min-h-5 shrink-0 text-sm">
        {runStatus.text}
      </div>
      {snapshot.run?.status === "failed" ? (
        <Button
          variant="outline"
          disabled={mutationLocked || retryMutation.isPending}
          onClick={() => {
            if (!mutationLocked) retryMutation.mutate(snapshot.run!.run_id);
          }}
        >
          <RotateCcw />
          {retryMutation.isPending ? "重新啟動中…" : "重試同一則回答"}
        </Button>
      ) : null}
      {submissionError ? (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {submissionError} 聊天草稿仍保留。
        </p>
      ) : answerMutation.isError || retryMutation.isError ? (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {errorText(answerMutation.error ?? retryMutation.error)}
          ；員工原話不會遺失。
        </p>
      ) : null}
    </section>
  );
}
