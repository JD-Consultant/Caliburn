import type {
  JdTaskView,
  OpksItemView,
  OpksProposalDecisionWrite,
  OpksProposalView,
  OpksTaskStatusView,
} from "@caliburn/job-analysis-contract";

export type OpksStatus = OpksTaskStatusView["status"];

/**
 * ADR 0054 決定 36 允許的**全部**措辭；措辭受 0052 決定 7 約束
 * （不得使用「不完整」「不合格」「未通過」——我們產出的是客製 JD，
 * 不是送審的職能基準）。
 *
 * 沒有第四個標籤是刻意的：分析完且都處理掉的工作與尚未分析的工作，從現況分不出來，
 * 依 0052 決定 6「無法確定的一律不提示」。狀態由 API 帶來，Web 不自行重算（決定 3）。
 */
export const OPKS_STATUS_LABELS: Record<OpksStatus, string> = {
  not_ready_for_analysis: "尚未適合分析",
  awaiting_employee_answer: "尚有待確認資訊",
  proposals_ready: "已可提出建議",
};

export function opksStatusByTask(
  entries: OpksTaskStatusView[],
): Map<string, OpksStatus> {
  return new Map(entries.map((entry) => [entry.task_id, entry.status]));
}

const ACTIVE_PROPOSAL_STATUSES = new Set<OpksProposalView["status"]>([
  "pending",
  "deferred",
]);

export type OpksTaskGroup = {
  task: JdTaskView;
  items: OpksItemView[];
};

export function groupOpksByTask(
  tasks: JdTaskView[],
  items: OpksItemView[],
): OpksTaskGroup[] {
  const indicatorTaskRefs = new Map(
    items
      .filter((item) => item.entity_kind === "indicator")
      .map((item) => [item.entity_id, item.task_refs] as const),
  );
  return tasks.map((task) => {
    const seen = new Set<string>();
    return {
      task,
      items: items.filter((item) => {
        const linkedThroughIndicator = item.indicator_refs.some((indicatorId) =>
          indicatorTaskRefs.get(indicatorId)?.includes(task.task_id),
        );
        if (
          item.entity_kind === "attitude" ||
          (!item.task_refs.includes(task.task_id) && !linkedThroughIndicator) ||
          seen.has(item.entity_id)
        ) {
          return false;
        }
        seen.add(item.entity_id);
        return true;
      }),
    };
  });
}

export function documentAttitudes(items: OpksItemView[]): OpksItemView[] {
  return items.filter((item) => item.entity_kind === "attitude");
}

export function documentUnlinkedCompetencies(
  items: OpksItemView[],
): OpksItemView[] {
  return items.filter(
    (item) =>
      (item.entity_kind === "knowledge" || item.entity_kind === "skill") &&
      item.task_refs.length === 0 &&
      item.indicator_refs.length === 0,
  );
}

export function groupOpksProposals(proposals: OpksProposalView[]) {
  const groups = new Map<string, OpksProposalView[]>();
  for (const proposal of proposals) {
    const current = groups.get(proposal.operation_id) ?? [];
    current.push(proposal);
    groups.set(proposal.operation_id, current);
  }
  return [...groups].map(([operationId, values]) => ({
    operationId,
    active: values.filter((proposal) =>
      ACTIVE_PROPOSAL_STATUSES.has(proposal.status),
    ),
    history: values.filter(
      (proposal) => !ACTIVE_PROPOSAL_STATUSES.has(proposal.status),
    ),
  }));
}

export type OpksEmployeeChoice =
  | "accepted"
  | "edited"
  | "rejected"
  | "unknown";

export function opksDecisionPayload(
  choice: OpksEmployeeChoice,
  text?: string,
): OpksProposalDecisionWrite {
  const normalized = text?.trim();
  switch (choice) {
    case "accepted":
      return { decision: "accepted" };
    case "edited":
      return { decision: "edited", edited_text: normalized };
    case "rejected":
      return { decision: "rejected", reason: normalized };
    case "unknown":
      return { decision: "deferred" };
  }
}
