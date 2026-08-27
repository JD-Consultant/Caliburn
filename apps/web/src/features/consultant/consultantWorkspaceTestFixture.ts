import type {
  ConsultantSnapshotView,
  DocumentChangeSetView,
} from "@caliburn/job-analysis-contract";

export const DOCUMENT_ID = "00000000-0000-0000-0000-000000000001";
export const SOURCE_ID = "00000000-0000-0000-0000-000000000002";
export const RUN_ID = "00000000-0000-0000-0000-000000000003";
export const WORK_ID = "00000000-0000-0000-0000-000000000004";
export const CHANGESET_ID = "00000000-0000-0000-0000-000000000005";
export const ACTION_ID = "00000000-0000-0000-0000-000000000006";
export const ACTION_ID_2 = "00000000-0000-0000-0000-000000000007";
export const ATOMIC_ID = "00000000-0000-0000-0000-000000000008";

export function consultantDocumentFixture(): ConsultantSnapshotView["approved_document"] {
  return {
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
  };
}

export function changesetFixture(): DocumentChangeSetView {
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

export function consultantSnapshotFixture(): ConsultantSnapshotView {
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
        deferred: 0,
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
      workspace_digest:
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      workspace_status: "pending",
      diagnostics: [],
      bundles: [changesetFixture()],
      unresolved_action_count: 2,
      blocked_branches: [],
      safe_interview_work_available: true,
      decision_required_before_more_interview: false,
      explanation: null,
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
    current_document: consultantDocumentFixture(),
    approved_document: consultantDocumentFixture(),
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
