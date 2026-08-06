import type {
  JdTaskView,
  OpksItemView,
  OpksProposalView,
} from "@caliburn/job-analysis-contract";
import { describe, expect, it } from "vitest";

import {
  documentAttitudes,
  documentUnlinkedCompetencies,
  groupOpksByTask,
  groupOpksProposals,
  kindOrderAfterMove,
  kindOrderedIds,
  opksDecisionPayload,
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

describe("kind ordering", () => {
  const items = [
    item("out-a", "output", ["task-1"], [], 0),
    item("out-b", "output", ["task-2"], [], 1),
    item("out-c", "output", ["task-1"], [], 2),
    item("know-a", "knowledge", ["task-1"], [], 0),
  ];

  it("orders a kind by display_order and ignores other kinds", () => {
    expect(kindOrderedIds(items, "output")).toEqual([
      "out-a",
      "out-b",
      "out-c",
    ]);
    expect(kindOrderedIds(items, "knowledge")).toEqual(["know-a"]);
  });

  it("swaps within the full kind list even when the neighbour is not adjacent globally", () => {
    // 畫面上 task-1 只看得到 out-a 與 out-c（out-b 屬於 task-2 夾在中間）。
    // 員工把 out-c 往上移一格,相鄰以看得見的為準,所以應與 out-a 交換。
    const visible = ["out-a", "out-c"];

    expect(kindOrderAfterMove(items, "output", visible, "out-c", -1)).toEqual([
      "out-c",
      "out-b",
      "out-a",
    ]);
  });

  it("returns null at the edges of the visible block", () => {
    const visible = ["out-a", "out-c"];

    expect(kindOrderAfterMove(items, "output", visible, "out-a", -1)).toBeNull();
    expect(kindOrderAfterMove(items, "output", visible, "out-c", 1)).toBeNull();
  });

  it("never drops or duplicates an id", () => {
    const visible = ["out-a", "out-b", "out-c"];
    const next = kindOrderAfterMove(items, "output", visible, "out-b", 1);

    expect(next).not.toBeNull();
    expect(next!.slice().sort()).toEqual(["out-a", "out-b", "out-c"]);
    expect(new Set(next!).size).toBe(3);
  });

  it("returns null for an id that is not in the visible block", () => {
    expect(
      kindOrderAfterMove(items, "output", ["out-a"], "know-a", 1),
    ).toBeNull();
  });
});

