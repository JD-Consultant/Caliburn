import type {
  ProposalJdEntryView,
  ProposalView,
} from "@caliburn/job-analysis-contract";

const ACTIVE_STATUSES = new Set<ProposalView["status"]>(["pending", "deferred"]);

export function groupProposals(proposals: ProposalView[]) {
  return {
    active: proposals.filter((proposal) => ACTIVE_STATUSES.has(proposal.status)),
    history: proposals.filter((proposal) => !ACTIVE_STATUSES.has(proposal.status)),
  };
}

export function editableJdAfter(
  entries: ProposalJdEntryView[],
): ProposalJdEntryView[] {
  return entries.map((entry) => ({
    task_id: entry.task_id,
    value: entry.value
      ? {
          ...entry.value,
          enablers: entry.value.enablers.map((enabler) => ({ ...enabler })),
        }
      : null,
  }));
}

export interface DraftOperation {
  text: string;
  idempotencyKey: string;
}

export function operationForDraft(
  previous: DraftOperation | undefined,
  previousFailed: boolean,
  draft: string,
  createKey: () => string,
): DraftOperation {
  const text = draft.trim();
  if (previousFailed && previous?.text === text) return previous;
  return { text, idempotencyKey: createKey() };
}
