"use client";

import type {
  ConsultationView,
  ProposalDecisionWrite,
} from "@caliburn/job-analysis-contract";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  decideProposal,
  JobAnalysisApiError,
  submitEmployeeTurn,
} from "@/lib/jobAnalysisApi";
import { groupProposals, operationForDraft } from "@/lib/jobAnalysisProposals";
import {
  consultationQueryOptions,
  jobAnalysisKeys,
} from "@/lib/jobAnalysisQueries";
import { ProposalCard } from "./ProposalCard";

function errorText(error: unknown) {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "操作失敗，請稍後再試";
}

export function ConsultationPanel({ documentId }: { documentId: string }) {
  const queryClient = useQueryClient();
  const consultation = useQuery(consultationQueryOptions(documentId));
  const [draft, setDraft] = useState("");

  const applyView = async (view: ConsultationView) => {
    queryClient.setQueryData(jobAnalysisKeys.consultation(documentId), view);
    queryClient.setQueryData(jobAnalysisKeys.document(documentId), {
      ...view.document,
      tasks: view.tasks,
    });
    await queryClient.invalidateQueries({ queryKey: jobAnalysisKeys.documents });
  };

  const turnMutation = useMutation({
    mutationFn: (operation: { text: string; idempotencyKey: string }) =>
      submitEmployeeTurn(documentId, operation.idempotencyKey, operation.text),
    onSuccess: async (view) => {
      setDraft("");
      await applyView(view);
    },
  });

  const decisionMutation = useMutation({
    mutationFn: (variables: {
      proposalId: string;
      idempotencyKey: string;
      decision: ProposalDecisionWrite;
    }) =>
      decideProposal(
        documentId,
        variables.proposalId,
        variables.idempotencyKey,
        variables.decision,
      ),
    onSuccess: applyView,
  });

  const send = () => {
    if (!draft.trim() || turnMutation.isPending || decisionMutation.isPending) return;
    turnMutation.mutate(
      operationForDraft(
        turnMutation.variables,
        turnMutation.isError,
        draft,
        () => crypto.randomUUID(),
      ),
    );
  };

  const decide = (proposalId: string, decision: ProposalDecisionWrite) => {
    const previous = decisionMutation.variables;
    const sameFailedDecision =
      decisionMutation.isError &&
      previous?.proposalId === proposalId &&
      JSON.stringify(previous.decision) === JSON.stringify(decision);
    decisionMutation.mutate(
      sameFailedDecision
        ? previous
        : {
            proposalId,
            decision,
            idempotencyKey: crypto.randomUUID(),
          },
    );
  };

  if (consultation.isPending) {
    return <p className="text-sm text-muted-foreground">正在讀取訪談…</p>;
  }
  if (consultation.isError || !consultation.data) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {errorText(consultation.error)}
      </p>
    );
  }

  const proposals = groupProposals(consultation.data.proposals);

  return (
    <section className="space-y-6" aria-label="AI 職務分析顧問">
      <div>
        <h2 className="text-lg font-semibold">訪談</h2>
        <p className="text-sm text-muted-foreground">
          可以說故事、補充工作，或直接更正先前內容。
        </p>
      </div>

      <div
        role="log"
        aria-label="訪談紀錄"
        className="max-h-[44vh] space-y-3 overflow-y-auto rounded-xl border bg-background p-4"
      >
        {consultation.data.conversation.map((turn) => (
          <div
            key={turn.turn_id}
            className={turn.speaker === "employee" ? "ml-8 text-right" : "mr-8"}
          >
            <p className="text-xs text-muted-foreground">
              {turn.speaker === "employee" ? "我" : "顧問"}
            </p>
            <p className="mt-1 inline-block rounded-xl bg-muted px-3 py-2 text-left text-sm whitespace-pre-wrap">
              {turn.text}
            </p>
          </div>
        ))}
      </div>

      <form
        className="space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
      >
        <label className="sr-only" htmlFor="employee-turn">
          回覆顧問
        </label>
        <textarea
          id="employee-turn"
          className="min-h-28 w-full rounded-xl border bg-background px-3 py-2 text-sm"
          value={draft}
          disabled={turnMutation.isPending || decisionMutation.isPending}
          placeholder={consultation.data.active_question?.text ?? "補充你的工作內容"}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
              event.preventDefault();
              send();
            }
          }}
        />
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">
            Enter 換行 · Ctrl/Cmd+Enter 送出
          </span>
          <Button
            type="submit"
            disabled={!draft.trim() || turnMutation.isPending || decisionMutation.isPending}
          >
            <Send />
            {turnMutation.isPending ? "分析中…" : "送出"}
          </Button>
        </div>
        <div role="status" aria-live="polite" className="min-h-5 text-sm">
          {turnMutation.isPending ? "顧問正在分析這段內容…" : null}
        </div>
        {turnMutation.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {errorText(turnMutation.error)}；原文已保留，可直接重試。
          </p>
        ) : null}
      </form>

      <div className="space-y-3">
        <h2 className="text-lg font-semibold">待確認建議</h2>
        {proposals.active.length === 0 ? (
          <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
            目前沒有需要你確認的文件變更。
          </p>
        ) : (
          proposals.active.map((proposal) => (
            <ProposalCard
              key={proposal.proposal_id}
              proposal={proposal}
              busy={decisionMutation.isPending || turnMutation.isPending}
              onDecision={(decision) => decide(proposal.proposal_id, decision)}
            />
          ))
        )}
        {decisionMutation.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {errorText(decisionMutation.error)}
          </p>
        ) : null}
      </div>

      {proposals.history.length ? (
        <details>
          <summary className="cursor-pointer text-sm text-muted-foreground">
            歷史建議（{proposals.history.length}）
          </summary>
          <div className="mt-3 space-y-3">
            {proposals.history.map((proposal) => (
              <ProposalCard
                key={proposal.proposal_id}
                proposal={proposal}
                busy={false}
                onDecision={() => undefined}
              />
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}
