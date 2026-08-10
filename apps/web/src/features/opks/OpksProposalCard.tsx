"use client";

import type {
  OpksProposalDecisionWrite,
  OpksProposalView,
} from "@caliburn/job-analysis-contract";
import { useState } from "react";

import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { opksDecisionPayload } from "./jobAnalysisOpks";

const KIND_LABELS: Record<OpksProposalView["entity_kind"], string> = {
  output: "工作產出",
  indicator: "行為指標",
  knowledge: "知識",
  skill: "技能",
  attitude: "態度",
};

const ACTION_LABELS: Record<OpksProposalView["action"], string> = {
  add: "新增",
  revise: "修改",
  remove: "移除",
};

const STATUS_LABELS: Record<OpksProposalView["status"], string> = {
  pending: "等待確認",
  deferred: "稍後處理",
  accepted: "已接受",
  edited: "修改後接受",
  rejected: "已拒絕",
  stale: "已失效",
};

export function OpksProposalCard({
  proposal,
  busy,
  onDecision,
}: {
  proposal: OpksProposalView;
  busy: boolean;
  onDecision: (decision: OpksProposalDecisionWrite) => void;
}) {
  const active = proposal.status === "pending" || proposal.status === "deferred";
  const [mode, setMode] = useState<"view" | "edit" | "reject">("view");
  const [editedText, setEditedText] = useState(proposal.after?.text ?? "");
  const [reason, setReason] = useState("");
  const quotes = [...new Set([
    ...(proposal.before?.evidence_quotes ?? []),
    ...(proposal.after?.evidence_quotes ?? []),
  ])];

  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="font-medium">
            {ACTION_LABELS[proposal.action]}{KIND_LABELS[proposal.entity_kind]}
          </h4>
          <p className="text-sm text-muted-foreground">
            {proposal.before?.text ?? "（目前沒有）"} → {proposal.after?.text ?? "（移除）"}
          </p>
        </div>
        <span className="text-xs text-muted-foreground">
          {STATUS_LABELS[proposal.status]}
        </span>
      </div>

      {quotes.length ? (
        <details>
          <summary className="cursor-pointer text-sm text-muted-foreground">
            查看相關原話
          </summary>
          <ul className="mt-2 space-y-1 border-l pl-3 text-sm">
            {quotes.map((quote, index) => (
              <li key={`${proposal.proposal_id}-${index}`}>「{quote}」</li>
            ))}
          </ul>
        </details>
      ) : null}

      {proposal.stale_reason ? (
        <p className="text-sm text-muted-foreground">{proposal.stale_reason}</p>
      ) : null}
      {proposal.rejection_reason ? (
        <p className="text-sm text-muted-foreground">{proposal.rejection_reason}</p>
      ) : null}

      {active && mode === "edit" && proposal.after ? (
        <div className="space-y-2 rounded-lg border p-3">
          <label className="block space-y-1">
            <span className="text-xs text-muted-foreground">修改文字</span>
            <textarea
              className="min-h-20 w-full rounded-lg border bg-background px-3 py-2 text-sm"
              value={editedText}
              onChange={(event) => setEditedText(event.target.value)}
            />
          </label>
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={busy || !editedText.trim() || editedText.trim() === proposal.after.text}
              onClick={() => onDecision(opksDecisionPayload("edited", editedText))}
            >
              修改後接受
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setMode("view")}>
              取消
            </Button>
          </div>
        </div>
      ) : null}

      {active && mode === "reject" ? (
        <div className="space-y-2 rounded-lg border p-3">
          <label className="block space-y-1">
            <span className="text-xs text-muted-foreground">不採用的原因</span>
            <textarea
              className="min-h-16 w-full rounded-lg border bg-background px-3 py-2 text-sm"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={busy || !reason.trim()}
              onClick={() => onDecision(opksDecisionPayload("rejected", reason))}
            >
              確認不採用
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setMode("view")}>
              取消
            </Button>
          </div>
        </div>
      ) : null}

      {active && mode === "view" ? (
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            disabled={busy}
            onClick={() => onDecision(opksDecisionPayload("accepted"))}
          >
            接受
          </Button>
          {proposal.after ? (
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => setMode("edit")}
            >
              修改文字
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => onDecision(opksDecisionPayload("unknown"))}
          >
            暫時無法判斷
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => setMode("reject")}
          >
            不採用
          </Button>
        </div>
      ) : null}
    </Card>
  );
}
