"use client";

import type { ConsultantSnapshotView } from "@caliburn/job-analysis-contract";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCircle2, RotateCcw, Send, ShieldCheck, UserRound } from "lucide-react";
import { useMemo, useState } from "react";

import {
  JobAnalysisApiError,
  retryConsultantRun,
  submitConsultantAnswer,
} from "@/shared/api/jobAnalysisApi";
import { refreshConsultantQueries } from "@/shared/query/jobAnalysisQueries";
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

export function ConsultantConversation({
  documentId,
  snapshot,
}: {
  documentId: string;
  snapshot: ConsultantSnapshotView;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const entries = useMemo(() => buildConversationEntries(snapshot), [snapshot]);
  const runStatus = consultantRunStatus(snapshot);
  const runFailed = snapshot.run?.status === "failed";
  const latestQuestion = [...snapshot.messages]
    .reverse()
    .find((message) => message.next_question)?.next_question;

  const refresh = async () => {
    await refreshConsultantQueries(queryClient, documentId);
  };
  const answerMutation = useMutation({
    mutationFn: (operation: {
      text: string;
      idempotencyKey: string;
    }) =>
      submitConsultantAnswer(documentId, operation.idempotencyKey, {
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
    mutationFn: (runId: string) => retryConsultantRun(documentId, runId),
    onSuccess: refresh,
  });

  const send = () => {
    const text = draft;
    if (
      !text.trim() ||
      runStatus.busy ||
      answerMutation.isPending
    )
      return;
    const previous = answerMutation.variables;
    const sameFailedInput =
      answerMutation.isError &&
      previous?.text === text;
    answerMutation.mutate(
      sameFailedInput
        ? previous
        : {
            text,
            idempotencyKey: crypto.randomUUID(),
          },
    );
  };

  return (
    <section className="space-y-5" aria-label="AI 職務分析顧問對話">
      <div className="rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-950">
        <div className="flex gap-3">
          <ShieldCheck className="mt-0.5 size-5 shrink-0 text-sky-700" />
          <div>
            <p className="font-semibold">外部 AI 與文件權限</p>
            <p className="mt-1 leading-6 text-sky-900/80">{EXTERNAL_AI_DISCLOSURE}</p>
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
                <span className="font-semibold text-amber-700">{index + 1}</span>
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
            <h2 className="mt-1 text-lg font-semibold">一次談清楚一個重點</h2>
          </div>
          {snapshot.run?.status === "completed" ? (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
              <CheckCircle2 className="size-4" /> 已保存
            </span>
          ) : null}
        </div>

        <div
          role="log"
          aria-label="訪談紀錄"
          className="mt-2 max-h-[52vh] space-y-4 overflow-y-auto rounded-xl bg-stone-50 p-4"
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
                    entry.speaker === "employee" ? "justify-end" : "justify-start"
                  }`}
                >
                  {entry.speaker === "employee" ? <UserRound /> : <Bot />}
                  {entry.speaker === "employee" ? "你" : "顧問"}
                  {entry.pending ? " · 已保存，待分析" : null}
                  {entry.superseded ? " · 已被更正" : null}
                </div>
                <div
                  className={`rounded-2xl px-4 py-3 text-sm leading-6 whitespace-pre-wrap ${
                    entry.speaker === "employee"
                      ? "bg-stone-900 text-white"
                      : "border border-stone-200 bg-white"
                  } ${entry.superseded ? "opacity-60" : ""}`}
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
            上一則回答已保存，但分析失敗。你可以重試同一則回答，也可以直接補充或更正下一則說法；新的訊息會另行保存。
          </div>
        ) : null}

        <form
          className="mt-4 space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            send();
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
              runStatus.busy ||
              answerMutation.isPending
            }
            placeholder={
              latestQuestion?.text ??
              snapshot.current_interview?.recommended_next_step ??
              "用自己的話描述實際工作；想到其他工作也可以一起說。"
            }
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                event.preventDefault();
                send();
              }
            }}
          />
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-stone-500">Ctrl/Cmd + Enter 送出</span>
            <Button
              type="submit"
              disabled={
                !draft.trim() ||
                runStatus.busy ||
                answerMutation.isPending
              }
            >
              <Send />
              {answerMutation.isPending ? "保存中…" : "送出回答"}
            </Button>
          </div>
        </form>

        <div role="status" aria-live="polite" className="mt-3 min-h-5 text-sm">
          {runStatus.text}
        </div>
        {snapshot.run?.status === "failed" ? (
          <Button
            variant="outline"
            disabled={retryMutation.isPending}
            onClick={() => retryMutation.mutate(snapshot.run!.run_id)}
          >
            <RotateCcw />
            {retryMutation.isPending ? "重新啟動中…" : "重試同一則回答"}
          </Button>
        ) : null}
        {answerMutation.isError || retryMutation.isError ? (
          <p role="alert" className="mt-2 text-sm text-destructive">
            {errorText(answerMutation.error ?? retryMutation.error)}；員工原話不會遺失。
          </p>
        ) : null}
      </Card>
    </section>
  );
}
