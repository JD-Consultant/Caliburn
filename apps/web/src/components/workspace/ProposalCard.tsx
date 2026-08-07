"use client";

import type {
  ProposalDecisionWrite,
  ProposalJdEntryView,
  ProposalView,
} from "@caliburn/job-analysis-contract";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { editableJdAfter } from "@/lib/jobAnalysisProposals";

const ACTION_LABELS: Record<ProposalView["action"], string> = {
  add: "新增工作",
  revise: "修改工作",
  withdraw: "移除工作",
  merge: "合併工作",
  split: "拆分工作",
};

const STATUS_LABELS: Record<ProposalView["status"], string> = {
  pending: "等待確認",
  deferred: "稍後處理",
  accepted: "已接受",
  edited: "修改後接受",
  rejected: "已拒絕",
  revision_requested: "已要求調整",
  stale: "已失效",
};

/**
 * `value === null` 在兩邊的意思**相反**，所以文案不能共用：
 *
 * - `jd_before`（目前內容）的 null ＝ 這條**還不在**職務說明書裡（新增提案的常態）
 * - `jd_after`（建議內容）的 null ＝ 建議**移除**這條
 *
 * 先前兩邊共用「從職務說明書移除」，害新增提案看起來像要刪東西。
 */
function EntryList({
  title,
  entries,
  side,
}: {
  title: string;
  entries: ProposalJdEntryView[];
  side: "before" | "after";
}) {
  const shown =
    side === "before" ? entries.filter((entry) => entry.value !== null) : entries;
  if (shown.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground">{title}</p>
      <ul className="mt-1 space-y-1 text-sm">
        {shown.map((entry) => (
          <li key={entry.task_id}>
            {entry.value ? entry.value.statement : "從職務說明書移除"}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ProposalCard({
  proposal,
  busy,
  onDecision,
}: {
  proposal: ProposalView;
  busy: boolean;
  onDecision: (decision: ProposalDecisionWrite) => void;
}) {
  const active = proposal.status === "pending" || proposal.status === "deferred";
  const hasEditableText = proposal.jd_after.some((entry) => entry.value !== null);
  const [editing, setEditing] = useState(false);
  const [editedAfter, setEditedAfter] = useState(() =>
    editableJdAfter(proposal.jd_after),
  );

  return (
    <Card className="space-y-4 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold">{ACTION_LABELS[proposal.action]}</h3>
        <span className="text-xs text-muted-foreground">
          {STATUS_LABELS[proposal.status]}
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <EntryList
          title="目前內容"
          entries={proposal.jd_before}
          side="before"
        />
        <EntryList title="建議內容" entries={proposal.jd_after} side="after" />
      </div>

      {proposal.evidence_quotes.length ? (
        <details>
          <summary className="cursor-pointer text-sm text-muted-foreground">
            查看相關原話
          </summary>
          <ul className="mt-2 space-y-2 border-l pl-3 text-sm">
            {proposal.evidence_quotes.map((quote, index) => (
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

      {active && editing ? (
        <div className="space-y-3 rounded-lg border p-3">
          <p className="text-sm font-medium">修改文字後接受</p>
          {editedAfter.map((entry, index) =>
            entry.value ? (
              <label className="block space-y-1" key={entry.task_id}>
                <span className="text-xs text-muted-foreground">工作敘述</span>
                <textarea
                  className="min-h-20 w-full rounded-lg border bg-background px-3 py-2 text-sm"
                  value={entry.value.statement}
                  onChange={(event) => {
                    const next = editableJdAfter(editedAfter);
                    next[index].value!.statement = event.target.value;
                    setEditedAfter(next);
                  }}
                />
              </label>
            ) : null,
          )}
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={busy || editedAfter.some((entry) => entry.value && !entry.value.statement.trim())}
              onClick={() =>
                onDecision({ decision: "edited", edited_jd_after: editedAfter })
              }
            >
              儲存並接受
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              取消
            </Button>
          </div>
        </div>
      ) : null}

      {active && !editing ? (
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            disabled={busy}
            onClick={() => onDecision({ decision: "accepted" })}
          >
            接受
          </Button>
          {hasEditableText ? (
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => setEditing(true)}
            >
              修改文字
            </Button>
          ) : null}
          {proposal.status === "pending" ? (
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => onDecision({ decision: "deferred" })}
            >
              稍後處理
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => onDecision({ decision: "rejected" })}
          >
            不採用
          </Button>
        </div>
      ) : null}
    </Card>
  );
}
