import type {
  JdTaskView,
  OpksItemView,
  OpksProposalView,
} from "@caliburn/job-analysis-contract";
import { describe, expect, it } from "vitest";

import {
  OPKS_STATUS_LABELS,
  opksStatusByTask,
  documentAttitudes,
  documentUnlinkedCompetencies,
  groupOpksByTask,
  groupOpksProposals,
  opksDecisionPayload,
  moveOpksWithinVisibleGroup,
} from "./jobAnalysisOpks";

const tasks = [
  { task_id: "task-1", statement: "彙整週報" },
  { task_id: "task-2", statement: "分析異常" },
] as JdTaskView[];

function item(
  entityId: string,
  entityKind: OpksItemView["entity_kind"],
  taskRefs: string[],
  indicatorRefs: string[] = [],
  displayOrder = 0,
): OpksItemView {
  return {
    entity_id: entityId,
    entity_kind: entityKind,
    text: entityId,
    task_refs: taskRefs,
    indicator_refs: indicatorRefs,
    evidence_quotes: [],
    display_order: displayOrder,
  };
}

function proposal(
  proposalId: string,
  operationId: string,
  status: OpksProposalView["status"],
): OpksProposalView {
  return {
    proposal_id: proposalId,
    operation_id: operationId,
    entity_id: `${proposalId}-entity`,
    entity_kind: "knowledge",
    action: "add",
    status,
    before: null,
    after: item(`${proposalId}-entity`, "knowledge", ["task-1"]),
    edited_after: null,
    rejection_reason: null,
    stale_reason: null,
  };
}

describe("OPKS product projection", () => {
  it("swaps visible same-kind neighbors without moving hidden items", () => {
    const values = [
      item("output-1", "output", ["task-1"], [], 0),
      item("output-2", "output", ["task-2"], [], 1),
      item("output-3", "output", ["task-1"], [], 2),
    ];

    expect(
      moveOpksWithinVisibleGroup(values, "output", "output-3", -1, [
        "output-1",
        "output-3",
      ]),
    ).toEqual(["output-3", "output-2", "output-1"]);
  });

  it("projects O/P/K/S by Task while preserving shared K/S identity", () => {
    const sharedKnowledge = item("knowledge-1", "knowledge", ["task-1", "task-2"]);
    const indicator = item("indicator-1", "indicator", ["task-1"]);
    const indicatorLinkedSkill = item("skill-1", "skill", [], ["indicator-1"]);
    const grouped = groupOpksByTask(tasks, [
      item("output-1", "output", ["task-1"]),
      indicator,
      sharedKnowledge,
      indicatorLinkedSkill,
      item("attitude-1", "attitude", []),
    ]);

    expect(grouped.map((group) => group.task.task_id)).toEqual(["task-1", "task-2"]);
    expect(grouped[0].items.map((value) => value.entity_id)).toEqual([
      "output-1",
      "indicator-1",
      "knowledge-1",
      "skill-1",
    ]);
    expect(grouped[1].items).toEqual([sharedKnowledge]);
    expect(grouped[0].items[2]).toBe(grouped[1].items[0]);
  });

  it("keeps Attitude at document level", () => {
    const attitude = item("attitude-1", "attitude", []);

    expect(documentAttitudes([item("skill-1", "skill", ["task-1"]), attitude])).toEqual([
      attitude,
    ]);
  });

  it("keeps unlinked K/S visible after their Task is removed", () => {
    const knowledge = item("knowledge-1", "knowledge", []);
    const skill = item("skill-1", "skill", []);

    expect(
      documentUnlinkedCompetencies([
        knowledge,
        skill,
        item("knowledge-linked", "knowledge", [], ["indicator-1"]),
        item("output-1", "output", ["task-1"]),
      ]),
    ).toEqual([knowledge, skill]);
  });

  it("groups proposals by operation without merging their decisions", () => {
    const groups = groupOpksProposals([
      proposal("p1", "operation-1", "pending"),
      proposal("p2", "operation-1", "accepted"),
      proposal("p3", "operation-2", "deferred"),
    ]);

    expect(groups.map((group) => group.operationId)).toEqual([
      "operation-1",
      "operation-2",
    ]);
    expect(groups[0].active.map((value) => value.proposal_id)).toEqual(["p1"]);
    expect(groups[0].history.map((value) => value.proposal_id)).toEqual(["p2"]);
  });

  it("maps employee choices to the thin proposal decision payload", () => {
    expect(opksDecisionPayload("unknown")).toEqual({ decision: "deferred" });
    expect(opksDecisionPayload("edited", "  熟悉營運指標定義  ")).toEqual({
      decision: "edited",
      edited_text: "熟悉營運指標定義",
    });
    expect(opksDecisionPayload("rejected", "  不是必要知識  ")).toEqual({
      decision: "rejected",
      reason: "不是必要知識",
    });
  });
});

describe("OPKS task status labels", () => {
  it("carries exactly the three phrasings ADR 0054 decision 36 allows", () => {
    // 多一個標籤就是往完成度 dashboard 滑；ADR 0052 決定 6 已明令不做百分比。
    expect(Object.values(OPKS_STATUS_LABELS)).toEqual([
      "尚未適合分析",
      "尚有待確認資訊",
      "已可提出建議",
    ]);
  });

  it("never uses the wording ADR 0052 decision 7 forbids", () => {
    // 我們產出的是客製 JD，不是送審的職能基準。
    const rendered = Object.values(OPKS_STATUS_LABELS).join("");
    for (const banned of ["不完整", "不合格", "未通過"]) {
      expect(rendered).not.toContain(banned);
    }
  });

  it("leaves a settled task without any label", () => {
    // 分析完且都處理掉的工作，與尚未分析的工作，從現況分不出來
    // ——ADR 0052 決定 6:「無法確定的一律不提示。」
    const byTask = opksStatusByTask([
      { task_id: "task-1", status: "awaiting_employee_answer" },
    ]);

    expect(byTask.get("task-1")).toBe("awaiting_employee_answer");
    expect(byTask.get("task-settled")).toBeUndefined();
  });
});
