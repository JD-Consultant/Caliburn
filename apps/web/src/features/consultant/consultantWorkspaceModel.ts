import type {
  ApprovedJobDocumentView,
  ApprovedJobDocumentWrite,
  ConsultantSnapshotEvent,
  ConsultantSnapshotView,
  DocumentChangeSetView,
  DocumentReviewDecisionWrite,
} from "@caliburn/job-analysis-contract";

type CurrentDocumentDuty = ApprovedJobDocumentView["duties"][number];
type CurrentDocumentTask = ApprovedJobDocumentView["tasks"][number];
type CurrentDocumentItem =
  | ApprovedJobDocumentView["opks"][number]
  | ApprovedJobDocumentWrite["opks"][number];

export type CurrentDocumentOutlineItem = {
  item: CurrentDocumentItem;
  label: string;
  sharedTaskCount: number;
};

export type CurrentDocumentOutlineTask = {
  task: CurrentDocumentTask;
  label: string;
  items: CurrentDocumentOutlineItem[];
};

export type CurrentDocumentOutlineDuty = {
  duty: CurrentDocumentDuty;
  tasks: CurrentDocumentOutlineTask[];
};

export type CurrentDocumentOutlineModel = {
  duties: CurrentDocumentOutlineDuty[];
  unassignedTasks: CurrentDocumentOutlineTask[];
  unassignedItems: CurrentDocumentOutlineItem[];
  documentItems: CurrentDocumentOutlineItem[];
};

const currentDocumentItemKindLabels = {
  output: "O",
  indicator: "P",
  knowledge: "K",
  skill: "S",
  attitude: "A",
} as const;

function currentDocumentItemLabel(
  kind: CurrentDocumentItem["kind"],
  ordinal: number,
): string {
  return `${currentDocumentItemKindLabels[kind]} ${ordinal}`;
}

function sortByDisplayOrder<T extends { display_order: number }>(values: T[]): T[] {
  return [...values].sort((left, right) => left.display_order - right.display_order);
}

function outlineItemsForTask(
  task: CurrentDocumentTask,
  items: CurrentDocumentItem[],
): CurrentDocumentOutlineItem[] {
  const ordinals = new Map<CurrentDocumentItem["kind"], number>();
  return sortByDisplayOrder(
    items.filter((item) => item.task_ids.includes(task.task_id)),
  ).map((item) => {
    const ordinal = (ordinals.get(item.kind) ?? 0) + 1;
    ordinals.set(item.kind, ordinal);
    return {
      item,
      label: currentDocumentItemLabel(item.kind, ordinal),
      sharedTaskCount:
        ["knowledge", "skill"].includes(item.kind) ? item.task_ids.length : 0,
    };
  });
}

/**
 * Builds only the employee-facing projection of the current document.
 * It groups existing records for display and intentionally does not repair,
 * validate, or infer Duty/Task/OPKS relationships.
 */
export function buildCurrentDocumentOutline(
  document: ApprovedJobDocumentView | ApprovedJobDocumentWrite,
): CurrentDocumentOutlineModel {
  const duties = sortByDisplayOrder(document.duties);
  const tasks = sortByDisplayOrder(document.tasks);
  const items = sortByDisplayOrder(document.opks);
  const taskIds = new Set(tasks.map((task) => task.task_id));
  const taskLabels = new Map(
    tasks.map((task, index) => [task.task_id, `Task ${index + 1}`]),
  );
  const taskItems = items.filter((item) => item.kind !== "attitude");
  const toTask = (task: CurrentDocumentTask): CurrentDocumentOutlineTask => ({
    task,
    label: taskLabels.get(task.task_id) ?? "Task",
    items: outlineItemsForTask(task, taskItems),
  });

  const assignedTaskIds = new Set<string>();
  const dutyGroups = duties.map((duty) => {
    const dutyTasks = tasks.filter((task) => task.duty_id === duty.duty_id);
    dutyTasks.forEach((task) => assignedTaskIds.add(task.task_id));
    return {
      duty,
      tasks: dutyTasks.map(toTask),
    };
  });

  const unassignedTasks = tasks
    .filter((task) => !task.duty_id || !assignedTaskIds.has(task.task_id))
    .map(toTask);
  const unassignedOrdinals = new Map<CurrentDocumentItem["kind"], number>();
  const unassignedItems = taskItems
    .filter(
      (item) =>
        item.task_ids.length === 0 ||
        !item.task_ids.some((id) => taskIds.has(id)),
    )
    .map((item) => {
      const ordinal = (unassignedOrdinals.get(item.kind) ?? 0) + 1;
      unassignedOrdinals.set(item.kind, ordinal);
      return {
        item,
        label: currentDocumentItemLabel(item.kind, ordinal),
        sharedTaskCount:
          ["knowledge", "skill"].includes(item.kind)
            ? item.task_ids.length
            : 0,
      };
    });
  const documentItems = items
    .filter((item) => item.kind === "attitude")
    .map((item, index) => ({
      item,
      label: currentDocumentItemLabel(item.kind, index + 1),
      sharedTaskCount: 0,
    }));

  return {
    duties: dutyGroups,
    unassignedTasks,
    unassignedItems,
    documentItems,
  };
}

export const EXTERNAL_AI_DISCLOSURE =
  "你的訪談內容會送往已設定的外部 AI 服務協助分析；AI 產生的文件內容必須經過你確認，才會進入正式文件。";

const interviewWorkStatusLabels: Record<string, string> = {
  available: "可繼續深入",
  active: "目前訪談中",
  parked: "稍後處理",
  blocked: "等待相關決定",
  sufficient_for_now: "目前足夠",
  unknown: "尚待辨識",
  not_applicable: "不適用",
  retired: "已排除",
  awaiting_employee_decision: "待你確認",
};

const understandingStatusLabels: Record<string, string> = {
  active: "目前理解",
  challenged: "需要重看",
  employee_confirmed: "你已確認",
  superseded: "已有新版",
  retired: "已排除",
};

export function interviewWorkStatusLabel(status: string): string {
  return interviewWorkStatusLabels[status] ?? "狀態待確認";
}

export function understandingStatusLabel(status: string): string {
  return understandingStatusLabels[status] ?? "狀態待確認";
}

export function documentPathLabel(path: string): string {
  const [collection, , field] = path.split("/").filter(Boolean);
  if (collection === "job_title") return "職務名稱";
  if (collection === "work_description") return "工作描述";

  const collectionLabels: Record<string, string> = {
    duties: "職責",
    tasks: "工作",
    opks: "O／P／K／S",
  };
  const fieldLabels: Record<string, string> = {
    statement: "敘述",
    display_order: "順序",
    duty_id: "所屬職責",
    action: "動作",
    object: "對象",
    purpose_result: "目的／結果",
    context: "情境",
    frequency_text: "頻率",
    responsibility_role: "責任角色",
    enablers: "工具／方法／促成條件",
    text: "內容",
    task_ids: "關聯工作",
    indicator_ids: "關聯績效指標",
  };
  const collectionLabel = collectionLabels[collection];
  if (!collectionLabel) return "正式文件內容";
  if (!path.split("/").filter(Boolean)[1]) {
    return collection === "opks" ? `${collectionLabel} 清單` : `${collectionLabel}清單`;
  }
  return field ? `${collectionLabel}${fieldLabels[field] ?? "內容"}` : `${collectionLabel}內容`;
}

export type ConversationEntry = {
  key: string;
  speaker: "employee" | "consultant";
  text: string;
  superseded: boolean;
  pending: boolean;
};

export function buildConversationEntries(
  snapshot: ConsultantSnapshotView,
): ConversationEntry[] {
  const replies = new Map<string, typeof snapshot.messages>();
  for (const message of snapshot.messages) {
    const values = replies.get(message.answer_source_id) ?? [];
    values.push(message);
    replies.set(message.answer_source_id, values);
  }

  const result: ConversationEntry[] = [];
  for (const source of [...snapshot.employee_messages].sort((left, right) =>
    left.created_at.localeCompare(right.created_at),
  )) {
    result.push({
      key: `employee:${source.source_id}`,
      speaker: "employee",
      text: source.text,
      superseded: source.validity === "superseded",
      pending: source.processing_status === "pending",
    });
    for (const message of replies.get(source.source_id) ?? []) {
      result.push({
        key: `consultant:${message.run_id}`,
        speaker: "consultant",
        text: message.text,
        superseded: false,
        pending: false,
      });
    }
    replies.delete(source.source_id);
  }
  for (const messages of replies.values()) {
    for (const message of messages) {
      result.push({
        key: `consultant:${message.run_id}`,
        speaker: "consultant",
        text: message.text,
        superseded: false,
        pending: false,
      });
    }
  }
  return result;
}

export function workspaceSections(snapshot: ConsultantSnapshotView) {
  const latestQuestion =
    snapshot.messages[snapshot.messages.length - 1]?.next_question ?? null;
  return {
    openingSteps: snapshot.opening_navigation.visible
      ? snapshot.opening_navigation.steps
      : [],
    focus: snapshot.current_interview
      ? {
          label: "目前訪談重點",
          title: snapshot.current_interview.title,
          whyNow: snapshot.current_interview.why_now,
          missingBeforeEnough: snapshot.current_interview.missing_before_enough,
          recommendedNextStep: snapshot.current_interview.recommended_next_step,
        }
      : latestQuestion
        ? {
            label: "目前要釐清的問題",
            title: latestQuestion.answer_target,
            whyNow: latestQuestion.reason,
            missingBeforeEnough: null,
            recommendedNextStep: latestQuestion.text,
          }
        : null,
    understanding: {
      label: snapshot.understanding.label,
      items: snapshot.understanding.items,
      parkedClues: snapshot.understanding.parked_clues,
      calibration: snapshot.understanding.calibration,
    },
    gaps: snapshot.semantic_progress.gaps.filter(
      (gap) => gap.status !== "resolved",
    ),
    sufficiency: {
      currentlyEnough: snapshot.sufficiency.currently_enough,
      why: snapshot.sufficiency.why_enough,
      remainingGapReasons: snapshot.sufficiency.remaining_gap_reasons,
      likelyBenefit: snapshot.sufficiency.likely_benefit_of_continuing,
      evidence: snapshot.sufficiency.deterministic_evidence,
    },
    reviewBundles: snapshot.document_review.bundles,
    requiredClarification: snapshot.required_clarification,
  };
}

const REVIEWABLE_STATUSES = new Set(["pending"]);

export function reviewSelectionForAction(
  changeset: DocumentChangeSetView,
  actionId: string,
): string[] {
  const action = changeset.actions.find((item) => item.action_id === actionId);
  if (!action || !REVIEWABLE_STATUSES.has(action.status)) return [];
  if (!action.atomic_subgroup_id) return [action.action_id];
  return changeset.actions
    .filter(
      (item) =>
        item.atomic_subgroup_id === action.atomic_subgroup_id &&
        REVIEWABLE_STATUSES.has(item.status),
    )
    .map((item) => item.action_id);
}

export function buildReviewDecision(
  command: DocumentReviewDecisionWrite["command"],
  actionIds: string[],
  editedAfterByActionId: DocumentReviewDecisionWrite["edited_after_by_action_id"] = {},
  rejectionReason: string | null = null,
): DocumentReviewDecisionWrite {
  if (actionIds.length === 0) {
    throw new Error("At least one review action is required");
  }
  return {
    command,
    action_ids: actionIds as [string, ...string[]],
    edited_after_by_action_id: editedAfterByActionId,
    rejection_reason: rejectionReason,
  };
}

export function reviewSelectionForDecision(
  changeset: DocumentChangeSetView,
  actionIds: string[],
  command: DocumentReviewDecisionWrite["command"],
): string[] {
  if (!["accept_changes", "edit_and_accept_changes"].includes(command)) {
    return actionIds;
  }
  const selected = new Set(actionIds);
  let changed = true;
  while (changed) {
    changed = false;
    for (const action of changeset.actions) {
      if (!selected.has(action.action_id)) continue;
      for (const dependencyId of action.depends_on_action_ids) {
        for (const groupedId of reviewSelectionForAction(
          changeset,
          dependencyId,
        )) {
          if (!selected.has(groupedId)) {
            selected.add(groupedId);
            changed = true;
          }
        }
      }
    }
  }
  return changeset.actions
    .filter((action) => selected.has(action.action_id))
    .map((action) => action.action_id);
}

export function toApprovedDocumentWrite(
  value: ApprovedJobDocumentView,
): ApprovedJobDocumentWrite {
  return {
    schema_version: value.schema_version,
    document_id: value.document_id,
    job_title: value.job_title,
    occupation_category_name: value.occupation_category_name,
    occupation_name: value.occupation_name,
    occupation_code: value.occupation_code,
    industry_name: value.industry_name,
    industry_code: value.industry_code,
    work_description: value.work_description,
    competency_level: value.competency_level,
    notes: value.notes,
    duties: value.duties.map((item) => ({ ...item })),
    tasks: value.tasks.map((item) => ({
      ...item,
      enablers: item.enablers.map((enabler) => ({ ...enabler })),
    })),
    opks: value.opks.map((item) => ({
      item_id: item.item_id,
      kind: item.kind,
      text: item.text,
      display_order: item.display_order,
      task_ids: [...item.task_ids],
      indicator_ids: [...item.indicator_ids],
    })),
  };
}

export function shouldRefetchForEvent(
  event: ConsultantSnapshotEvent,
  documentId: string,
  knownRevision: number,
): boolean {
  if (event.document_id !== documentId) return false;
  return event.event === "document_deleted" || event.revision > knownRevision;
}

export function consultantRunStatus(snapshot: ConsultantSnapshotView): {
  busy: boolean;
  text: string | null;
} {
  switch (snapshot.run?.status) {
    case "source_saved":
      return { busy: true, text: "回答已保存，AI 正在分析…" };
    case "failed":
      return {
        busy: false,
        text: "分析未完成；你的回答已保存，可以重試。",
      };
    case "completed":
    case "idle":
    case undefined:
      return { busy: false, text: null };
  }
}
