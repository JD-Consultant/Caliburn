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

/**
 * 單一 kind 在整份文件裡的順序（`display_order` 的唯一性範圍就是 kind）。
 */
export function kindOrderedIds(
  items: OpksItemView[],
  kind: OpksItemView["entity_kind"],
): string[] {
  return items
    .filter((item) => item.entity_kind === kind)
    .slice()
    .sort((a, b) => a.display_order - b.display_order)
    .map((item) => item.entity_id);
}

/**
 * 把「在畫面上把某一項往上／往下移一格」翻譯成該 kind 的**完整**順序。
 *
 * 畫面是按 Task 分區呈現的，但 `display_order` 是文件層 per-kind 唯一——所以看得見的
 * 那幾項只是全體的子集合。相鄰是**以看得見的子集合為準**（員工看到什麼就移動什麼），
 * 交換則發生在完整清單上，其餘項目留在原位。
 *
 * 回 `null` 表示移不動（已在該區塊的頭或尾），呼叫端據此 disable 按鈕。
 */
export function kindOrderAfterMove(
  items: OpksItemView[],
  kind: OpksItemView["entity_kind"],
  visibleIds: string[],
  entityId: string,
  offset: -1 | 1,
): string[] | null {
  const from = visibleIds.indexOf(entityId);
  const to = from + offset;
  if (from < 0 || to < 0 || to >= visibleIds.length) return null;

  const full = kindOrderedIds(items, kind);
  const a = full.indexOf(entityId);
  const b = full.indexOf(visibleIds[to]);
  if (a < 0 || b < 0) return null;

  const next = full.slice();
  [next[a], next[b]] = [next[b], next[a]];
  return next;
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
