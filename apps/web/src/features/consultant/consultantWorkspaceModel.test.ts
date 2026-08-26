import { describe, expect, it } from "vitest";
import type {
  ConsultantSnapshotEvent,
  ConsultantSnapshotView,
  DocumentChangeSetView,
} from "@caliburn/job-analysis-contract";

import {
  EXTERNAL_AI_DISCLOSURE,
  buildConversationEntries,
  buildCurrentDocumentOutline,
  buildDocumentReviewSemanticGroups,
  buildReviewDecision,
  consultantRunStatus,
  documentPathLabel,
  interviewWorkStatusLabel,
  reviewSelectionForAction,
  reviewSelectionForDecision,
  shouldRefetchForEvent,
  toApprovedDocumentWrite,
  understandingStatusLabel,
  workspaceSections,
} from "./consultantWorkspaceModel";

const DOCUMENT_ID = "00000000-0000-0000-0000-000000000001";
const SOURCE_ID = "00000000-0000-0000-0000-000000000002";
const RUN_ID = "00000000-0000-0000-0000-000000000003";
const WORK_ID = "00000000-0000-0000-0000-000000000004";
const CHANGESET_ID = "00000000-0000-0000-0000-000000000005";
const ACTION_ID = "00000000-0000-0000-0000-000000000006";
const ACTION_ID_2 = "00000000-0000-0000-0000-000000000007";
const ATOMIC_ID = "00000000-0000-0000-0000-000000000008";

function changeset(): DocumentChangeSetView {
  const action = (actionId: string, atomicSubgroupId: string | null) => ({
    action_id: actionId,
    operation: "revise" as const,
    path: "/tasks/task-1/statement",
    target_key: "task-1",
    before: "整理需求",
    after: "彙整採購需求",
    source_ids: [SOURCE_ID],
    quote_anchors: [],
    read_set: [],
    depends_on_action_ids: [],
    atomic_subgroup_id: atomicSubgroupId,
    affected_work_ids: [WORK_ID],
    blocks_dependent_analysis: false,
    status: "pending" as const,
  });
  return {
    changeset_id: CHANGESET_ID,
    summary: "更新工作描述",
    actions: [action(ACTION_ID, ATOMIC_ID), action(ACTION_ID_2, ATOMIC_ID)],
    source_ids: [SOURCE_ID],
    created_revision: 2,
    acceptance_blocked: false,
  };
}

function snapshot(): ConsultantSnapshotView {
  return {
    document_id: DOCUMENT_ID,
    revision: 3,
    source_count: 1,
    latest_source_id: SOURCE_ID,
    run: {
      run_id: RUN_ID,
      status: "completed",
      source_id: SOURCE_ID,
      started_at: "2026-08-14T10:00:00Z",
      completed_at: "2026-08-14T10:00:02Z",
      error_code: null,
    },
    opening_navigation: {
      visible: true,
      steps: ["先大致盤點工作", "一次深入一個焦點", "正式修改由你確認"],
    },
    current_interview: {
      work_id: WORK_ID,
      title: "月結差異處理",
      why_now: "這項工作會影響後續 Duty 與產出分析。",
      missing_before_enough: "還不清楚你如何判斷異常。",
      recommended_next_step: "請說一個最近的實際案例。",
    },
    visible_work: [
      {
        work_id: WORK_ID,
        kind: "task_candidate",
        title: "月結差異處理",
        status: "active",
        priority_reason: "目前最能降低結構不確定性",
        blocked_by_decision_ids: [],
      },
    ],
    understanding: {
      label: "AI 目前理解",
      collapsible: true,
      items: [
        {
          understanding_id: "00000000-0000-0000-0000-000000000009",
          kind: "work_hypothesis",
          text: "你會整理並追查月結差異。",
          status: "active",
          source_ids: [SOURCE_ID],
        },
      ],
      parked_clues: [],
      calibration: {
        calibration_id: "00000000-0000-0000-0000-000000000010",
        kind: "soft",
        trigger: "meaningful_shift",
        status: "pending",
        affected_work_ids: [WORK_ID],
        changed_understanding_ids: ["00000000-0000-0000-0000-000000000009"],
        allowed_actions: ["confirm", "direct_correction", "later"],
      },
    },
    semantic_progress: {
      currently_known_work_count: 1,
      coverage: [
        {
          work_id: WORK_ID,
          title: "月結差異處理",
          status: "active",
          reason: "正在釐清異常判斷",
        },
      ],
      depth: [
        {
          work_id: WORK_ID,
          task_boundary: "evidence_present",
          duty_grouping: "not_yet_deepened",
          output: "gap",
          performance_indicator: "gap",
          knowledge: "not_yet_deepened",
          skill: "not_yet_deepened",
        },
      ],
      employee_decisions: {
        pending: 2,
      },
      gaps: [
        {
          gap_id: "00000000-0000-0000-0000-000000000011",
          reason_code: "OUTPUT_UNKNOWN",
          description: "還不知道這項工作交付什麼成果。",
          subject_kind: "work",
          subject_id: WORK_ID,
          blocks_dependent_analysis: false,
          status: "active",
        },
      ],
    },
    employee_messages: [
      {
        source_id: SOURCE_ID,
        text: "我每月會追查差異。",
        created_at: "2026-08-14T10:00:00Z",
        processing_status: "committed",
        validity: "current",
        supersedes_source_id: null,
        superseded_by_source_id: null,
      },
    ],
    messages: [
      {
        run_id: RUN_ID,
        answer_source_id: SOURCE_ID,
        text: "了解，接下來想釐清你如何判斷異常。",
        used_skill_ids: ["story-interview"],
        next_question: {
          text: "最近一次遇到差異時，你先看什麼？",
          answer_target: "異常判斷依據",
          reason: "補足績效與知識分析需要的證據",
        },
      },
    ],
    document_review: {
      workspace_generation: 4,
      workspace_digest: "a".repeat(64),
      workspace_status: "pending",
      diagnostics: [],
      bundles: [changeset()],
      unresolved_action_count: 2,
    },
    required_clarification: {
      clarification_id: "00000000-0000-0000-0000-000000000012",
      question: "這項核准是你本人決定，還是主管決定？",
      reason: "責任歸屬會改變 Task 邊界。",
      current_understanding: "目前理解為你本人核准。",
      choices: ["我本人決定", "主管決定"],
      affected_work_ids: [WORK_ID],
      affected_branch: "月結差異處理",
      source_ids: [SOURCE_ID],
    },
    sufficiency: {
      currently_enough: false,
      why_enough: "目前仍缺少成果與衡量方式。",
      remaining_gap_reasons: ["成果未知", "衡量方式未知"],
      likely_benefit_of_continuing: "再談一個實例可補齊成果與指標。",
      deterministic_evidence: {
        known_work_count: 1,
        sufficient_work_count: 0,
        active_or_unvisited_work_count: 1,
        blocking_gap_count: 0,
        structural_decision_count: 0,
      },
      assessed_revision: 3,
      needs_recalculation: false,
    },
    current_document: {
      schema_version: 1,
      document_id: DOCUMENT_ID,
      job_title: "採購專員",
      occupation_category_name: null,
      occupation_name: null,
      occupation_code: null,
      industry_name: null,
      industry_code: null,
      work_description: null,
      competency_level: null,
      notes: null,
      duties: [],
      tasks: [],
      opks: [
        {
          item_id: "00000000-0000-0000-0000-000000000013",
          kind: "attitude",
          text: "謹慎",
          display_order: 0,
          task_ids: [],
          indicator_ids: [],
          evidence_source_ids: [SOURCE_ID],
        },
      ],
    },
    approved_document: {
      schema_version: 1,
      document_id: DOCUMENT_ID,
      job_title: "採購專員",
      occupation_category_name: null,
      occupation_name: null,
      occupation_code: null,
      industry_name: null,
      industry_code: null,
      work_description: null,
      competency_level: null,
      notes: null,
      duties: [],
      tasks: [],
      opks: [
        {
          item_id: "00000000-0000-0000-0000-000000000013",
          kind: "attitude",
          text: "謹慎",
          display_order: 0,
          task_ids: [],
          indicator_ids: [],
          evidence_source_ids: [SOURCE_ID],
        },
      ],
    },
    readiness: {
      ready: false,
      requires_force_confirmation: true,
      force_export_allowed: true,
      issues: [
        {
          code: "INTERVIEW_NOT_YET_SUFFICIENT",
          message: "目前仍缺少成果與衡量方式。",
          subject_id: null,
        },
      ],
    },
  };
}

describe("employee-facing consultant workspace model", () => {
  it("keeps the agreed product channels visible without pause or finish concepts", () => {
    const sections = workspaceSections(snapshot());

    expect(EXTERNAL_AI_DISCLOSURE).toContain("外部 AI");
    expect(EXTERNAL_AI_DISCLOSURE).toContain("你確認");
    expect(sections.openingSteps).toHaveLength(3);
    expect(sections.focus?.label).toBe("目前訪談重點");
    expect(sections.focus?.whyNow).toContain("Duty");
    expect(sections.understanding.label).toBe("AI 目前理解");
    expect(sections.understanding.calibration?.kind).toBe("soft");
    expect(sections.gaps[0].description).toContain("交付什麼成果");
    expect(sections.sufficiency.likelyBenefit).toContain("再談一個實例");
    expect(sections.reviewBundles).toHaveLength(1);
    expect(sections.requiredClarification?.question).toContain("本人決定");
    expect(JSON.stringify(sections)).not.toMatch(/pause|resume|finish/i);
  });

  it("uses only the latest durable next question when no work focus exists", () => {
    const value = snapshot();
    value.current_interview = null;

    expect(workspaceSections(value).focus).toEqual({
      label: "目前要釐清的問題",
      title: "異常判斷依據",
      whyNow: "補足績效與知識分析需要的證據",
      missingBeforeEnough: null,
      recommendedNextStep: "最近一次遇到差異時，你先看什麼？",
    });

    value.messages.push({
      run_id: "00000000-0000-0000-0000-000000000099",
      answer_source_id: SOURCE_ID,
      text: "目前不需要再追問。",
      used_skill_ids: [],
      next_question: null,
    });
    expect(workspaceSections(value).focus).toBeNull();
  });

  it("reconstructs employee and consultant messages after reopening", () => {
    expect(buildConversationEntries(snapshot()).map((entry) => [entry.speaker, entry.text])).toEqual([
      ["employee", "我每月會追查差異。"],
      ["consultant", "了解，接下來想釐清你如何判斷異常。"],
    ]);
  });

  it("reviews an atomic subgroup together and preserves employee edits", () => {
    const bundle = changeset();
    const actionIds = reviewSelectionForAction(bundle, ACTION_ID);

    expect(actionIds).toEqual([ACTION_ID, ACTION_ID_2]);
    expect(
      buildReviewDecision("edit_and_accept_changes", actionIds, {
        [ACTION_ID]: "員工修正後的內容",
      }),
    ).toEqual({
      command: "edit_and_accept_changes",
      action_ids: [ACTION_ID, ACTION_ID_2],
      edited_after_by_action_id: { [ACTION_ID]: "員工修正後的內容" },
      rejection_reason: null,
    });
  });

  it("adds unresolved dependencies only when accepting a document change", () => {
    const bundle = changeset();
    bundle.actions[0].atomic_subgroup_id = null;
    bundle.actions[1].atomic_subgroup_id = null;
    bundle.actions[0].depends_on_action_ids = [ACTION_ID_2];

    expect(reviewSelectionForDecision(bundle, [ACTION_ID], "accept_changes")).toEqual([
      ACTION_ID,
      ACTION_ID_2,
    ]);
    expect(reviewSelectionForDecision(bundle, [ACTION_ID], "reject_changes")).toEqual([
      ACTION_ID,
    ]);
  });

  it("uses SSE only as a newer-revision refetch hint", () => {
    const newer: ConsultantSnapshotEvent = {
      event: "snapshot_changed",
      document_id: DOCUMENT_ID,
      revision: 4,
      run_id: RUN_ID,
    };
    expect(shouldRefetchForEvent(newer, DOCUMENT_ID, 3)).toBe(true);
    expect(shouldRefetchForEvent({ ...newer, revision: 3 }, DOCUMENT_ID, 3)).toBe(false);
    expect(shouldRefetchForEvent({ ...newer, document_id: WORK_ID }, DOCUMENT_ID, 3)).toBe(false);
  });

  it("reports durable processing facts rather than inventing a session lifecycle", () => {
    const value = snapshot();
    value.run = { ...value.run!, status: "source_saved", completed_at: null };
    expect(consultantRunStatus(value)).toEqual({ busy: true, text: "回答已保存，AI 正在分析…" });
    value.run = { ...value.run, status: "failed", error_code: "provider_timeout" };
    expect(consultantRunStatus(value)).toEqual({ busy: false, text: "分析未完成；你的回答已保存，可以重試。" });
  });

  it("groups atomic actions together without merging separate semantic decisions", () => {
    const bundle = changeset();
    const independentAction = {
      ...bundle.actions[0],
      action_id: "00000000-0000-0000-0000-000000000014",
      atomic_subgroup_id: null,
    };
    const secondAtomicAction = {
      ...bundle.actions[0],
      action_id: "00000000-0000-0000-0000-000000000015",
      atomic_subgroup_id: "00000000-0000-0000-0000-000000000016",
    };

    const groups = buildDocumentReviewSemanticGroups([
      {
        ...bundle,
        actions: [
          bundle.actions[0],
          bundle.actions[1],
          independentAction,
          secondAtomicAction,
        ],
      },
    ]);

    expect(groups.map((group) => group.actions.map((action) => action.action_id))).toEqual([
      [ACTION_ID, ACTION_ID_2],
      [independentAction.action_id],
      [secondAtomicAction.action_id],
    ]);
    expect(groups.map((group) => group.key)).toEqual([
      `${CHANGESET_ID}:atomic:${ATOMIC_ID}`,
      `${CHANGESET_ID}:action:${independentAction.action_id}`,
      `${CHANGESET_ID}:atomic:${secondAtomicAction.atomic_subgroup_id}`,
    ]);
  });

  it("keeps task labels stable across grouping and numbers unassigned items per kind", () => {
    const document = toApprovedDocumentWrite(snapshot().current_document);
    const dutyId = "00000000-0000-0000-0000-000000000020";
    const unassignedTaskId = "00000000-0000-0000-0000-000000000021";
    const assignedTaskId = "00000000-0000-0000-0000-000000000022";
    document.duties = [
      { duty_id: dutyId, statement: "採購管理", display_order: 0 },
    ];
    document.tasks = [
      {
        task_id: assignedTaskId,
        duty_id: dutyId,
        statement: "覆核採購",
        action: "覆核",
        object: "採購內容",
        purpose_result: null,
        context: null,
        frequency_text: null,
        responsibility_role: null,
        enablers: [],
        display_order: 1,
        competency_level: null,
      },
      {
        task_id: unassignedTaskId,
        duty_id: null,
        statement: "盤點需求",
        action: "盤點",
        object: "需求",
        purpose_result: null,
        context: null,
        frequency_text: null,
        responsibility_role: null,
        enablers: [],
        display_order: 0,
        competency_level: null,
      },
    ];
    document.opks = [
      {
        item_id: "00000000-0000-0000-0000-000000000023",
        kind: "knowledge",
        text: "知識一",
        display_order: 0,
        task_ids: [],
        indicator_ids: [],
      },
      {
        item_id: "00000000-0000-0000-0000-000000000024",
        kind: "skill",
        text: "技能一",
        display_order: 0,
        task_ids: [],
        indicator_ids: [],
      },
      {
        item_id: "00000000-0000-0000-0000-000000000025",
        kind: "knowledge",
        text: "知識二",
        display_order: 1,
        task_ids: [],
        indicator_ids: [],
      },
    ];

    const outline = buildCurrentDocumentOutline(document);

    expect(outline.duties[0].tasks[0].label).toBe("Task 2");
    expect(outline.unassignedTasks[0].label).toBe("Task 1");
    expect(outline.unassignedItems.map((item) => item.label)).toEqual([
      "K 1",
      "S 1",
      "K 2",
    ]);
  });

  it("keeps internal enum and JSON-pointer names out of the employee wording", () => {
    expect(interviewWorkStatusLabel("sufficient_for_now")).toBe("目前足夠");
    expect(interviewWorkStatusLabel("awaiting_employee_decision")).toBe("待你確認");
    expect(understandingStatusLabel("employee_confirmed")).toBe("你已確認");
    expect(documentPathLabel("/tasks/00000000-0000-0000-0000-000000000020/duty_id")).toBe(
      "工作所屬職責",
    );
    expect(documentPathLabel("/opks")).toBe("O／P／K／S 清單");
  });
});
