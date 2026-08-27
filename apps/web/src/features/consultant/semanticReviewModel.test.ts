import type {
  ConsultantSnapshotView,
  DocumentChangeSetView,
  DocumentPatchActionView,
} from "@caliburn/job-analysis-contract";
import { describe, expect, it } from "vitest";

import { buildSemanticReviewIndex } from "./consultantWorkspaceModel";
import { consultantSnapshotFixture } from "./consultantWorkspaceTestFixture";

const DUTY_ONE = "00000000-0000-0000-0000-000000000201";
const DUTY_TWO = "00000000-0000-0000-0000-000000000202";
const MOVED_TASK = "00000000-0000-0000-0000-000000000203";
const ADDED_TASK = "00000000-0000-0000-0000-000000000204";
const DELETED_TASK = "00000000-0000-0000-0000-000000000205";

function action(
  actionId: string,
  operation: DocumentPatchActionView["operation"],
  path: string,
  before: unknown,
  after: unknown,
  dependsOn: string[] = [],
): DocumentPatchActionView {
  return {
    action_id: actionId,
    operation,
    path,
    target_key: path,
    before,
    after,
    source_ids: ["00000000-0000-0000-0000-000000000002"],
    quote_anchors: [
      {
        source_id: "00000000-0000-0000-0000-000000000002",
        start: 0,
        end: 7,
        quote: "其實是每週追蹤",
      },
    ],
    read_set: [],
    depends_on_action_ids: dependsOn,
    atomic_subgroup_id: null,
    affected_work_ids: [],
    blocks_dependent_analysis: false,
    status: "pending",
  };
}

function bundle(
  changesetId: string,
  summary: string,
  actions: DocumentPatchActionView[],
): DocumentChangeSetView {
  return {
    changeset_id: changesetId,
    summary,
    actions,
    source_ids: ["00000000-0000-0000-0000-000000000002"],
    created_revision: 3,
    acceptance_blocked: false,
  };
}

function snapshot(): ConsultantSnapshotView {
  const value = consultantSnapshotFixture();
  const approvedTask = {
    task_id: MOVED_TASK,
    duty_id: DUTY_ONE,
    statement: "每月彙整法規",
    action: "彙整",
    object: "法規",
    purpose_result: null,
    context: null,
    frequency_text: "每月",
    responsibility_role: "primary" as const,
    enablers: [],
    display_order: 0,
    competency_level: null,
  };
  const deletedTask = {
    ...approvedTask,
    task_id: DELETED_TASK,
    statement: "寄送紙本通知",
    display_order: 1,
  };
  value.approved_document.duties = [
    { duty_id: DUTY_ONE, statement: "法遵追蹤", display_order: 0 },
    { duty_id: DUTY_TWO, statement: "教育宣導", display_order: 1 },
  ];
  value.approved_document.tasks = [approvedTask, deletedTask];
  value.current_document = structuredClone(value.approved_document);
  value.current_document.tasks = [
    {
      ...approvedTask,
      duty_id: DUTY_TWO,
      statement: "每週追蹤法規",
      frequency_text: "每週",
    },
    {
      ...approvedTask,
      task_id: ADDED_TASK,
      duty_id: DUTY_ONE,
      statement: "整理教育問答",
      display_order: 1,
    },
  ];
  const moveId = "00000000-0000-0000-0000-000000000211";
  const reviseId = "00000000-0000-0000-0000-000000000212";
  value.document_review.bundles = [
    bundle(
      "00000000-0000-0000-0000-000000000221",
      "將法規追蹤移入教育宣導並修正頻率",
      [
        action(
          moveId,
          "reassign",
          `/tasks/${MOVED_TASK}/duty_id`,
          DUTY_ONE,
          DUTY_TWO,
        ),
        action(
          reviseId,
          "revise",
          `/tasks/${MOVED_TASK}/statement`,
          "每月彙整法規",
          "每週追蹤法規",
          [moveId],
        ),
      ],
    ),
    bundle(
      "00000000-0000-0000-0000-000000000222",
      "新增教育問答工作",
      [
        action(
          "00000000-0000-0000-0000-000000000213",
          "add",
          "/tasks",
          null,
          value.current_document.tasks[1],
        ),
      ],
    ),
    bundle(
      "00000000-0000-0000-0000-000000000223",
      "移除不再執行的紙本通知",
      [
        action(
          "00000000-0000-0000-0000-000000000214",
          "withdraw",
          `/tasks/${DELETED_TASK}`,
          deletedTask,
          null,
        ),
      ],
    ),
  ];
  value.document_review.unresolved_action_count = 4;
  value.employee_messages = [
    {
      source_id: "00000000-0000-0000-0000-000000000002",
      text: "其實是每週追蹤，不再寄紙本通知。",
      created_at: "2026-08-27T10:00:00Z",
      processing_status: "committed",
    },
  ];
  return value;
}

describe("server semantic review projection", () => {
  it("indexes scalar updates, additions, removals and moves without applying patches", () => {
    const index = buildSemanticReviewIndex(snapshot());

    expect(
      index.byPath.get(`/tasks/${MOVED_TASK}/statement`),
    ).toMatchObject({
      operation: "update",
      baseline: "每月彙整法規",
      current: "每週追蹤法規",
    });
    expect(index.byEntity.get(`/tasks/${ADDED_TASK}`)?.[0]).toMatchObject({
      operation: "add",
    });
    expect(index.deletedEntities).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          entityPath: `/tasks/${DELETED_TASK}`,
          operation: "delete",
        }),
      ]),
    );
    expect(index.movedTasks).toEqual([
      expect.objectContaining({
        taskId: MOVED_TASK,
        fromDutyId: DUTY_ONE,
        toDutyId: DUTY_TWO,
        operation: "move",
      }),
    ]);
  });

  it("keeps the server bundle as one decision and projects employee Evidence", () => {
    const index = buildSemanticReviewIndex(snapshot());
    const decoration = index.byPath.get(`/tasks/${MOVED_TASK}/statement`)!;

    expect(decoration.group.actionIds).toEqual([
      "00000000-0000-0000-0000-000000000211",
      "00000000-0000-0000-0000-000000000212",
    ]);
    expect(decoration.group.evidence).toEqual([
      expect.objectContaining({
        quote: "其實是每週追蹤",
        sourceText: "其實是每週追蹤，不再寄紙本通知。",
      }),
    ]);
  });
});
