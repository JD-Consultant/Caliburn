import { describe, expect, it } from "vitest";
import type { ProposalView } from "@caliburn/job-analysis-contract";

import {
  editableJdAfter,
  groupProposals,
  operationForDraft,
} from "./jobAnalysisProposals";

function proposal(status: ProposalView["status"]): ProposalView {
  return {
    proposal_id: status,
    action: "add",
    status,
    jd_before: [],
    jd_after: [],
    edited_jd_after: null,
    rejection_reason: null,
    stale_reason: null,
    evidence_quotes: [],
  };
}

describe("proposal presentation", () => {
  it("keeps pending and deferred actionable while all terminal states are history", () => {
    const grouped = groupProposals([
      proposal("accepted"),
      proposal("pending"),
      proposal("stale"),
      proposal("deferred"),
      proposal("revision_requested"),
    ]);

    expect(grouped.active.map((item) => item.status)).toEqual(["pending", "deferred"]);
    expect(grouped.history.map((item) => item.status)).toEqual([
      "accepted",
      "stale",
      "revision_requested",
    ]);
  });

  it("copies the complete proposed map before text-only editing", () => {
    const source: ProposalView["jd_after"] = [
      { task_id: "task-1", value: null },
      {
        task_id: "task-2",
        value: {
          task_id: "task-2",
          statement: "彙整週報",
          purpose_result: null,
          context: null,
          frequency_text: "每週",
          responsibility_role: "primary",
          enablers: [],
          display_order: 0,
          duty_id: null,
          competency_level: null,
        },
      },
    ];

    const copy = editableJdAfter(source);
    copy[1].value!.statement = "彙整營運週報";

    expect(source[1].value!.statement).toBe("彙整週報");
    expect(copy[0]).toEqual({ task_id: "task-1", value: null });
  });
});

describe("turn retry identity", () => {
  it("reuses the failed operation only for the same normalized draft", () => {
    const previous = { text: "每週盤點", idempotencyKey: "same-key" };
    expect(operationForDraft(previous, true, "  每週盤點  ", () => "new-key")).toEqual(
      previous,
    );
    expect(operationForDraft(previous, true, "每月盤點", () => "new-key")).toEqual({
      text: "每月盤點",
      idempotencyKey: "new-key",
    });
    expect(operationForDraft(previous, false, "每週盤點", () => "new-key")).toEqual({
      text: "每週盤點",
      idempotencyKey: "new-key",
    });
  });
});
