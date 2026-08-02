import type {
  JdTaskView,
  OpksItemView,
  OpksProposalDecisionWrite,
  OpksProposalView,
} from "@caliburn/job-analysis-contract";

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
