import type {
  ConsultantSnapshotEvent,
  ConsultantSnapshotView,
  DocumentChangeSetView,
  DocumentPatchActionView,
} from "@caliburn/job-analysis-contract";

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
  const headerLabels: Record<string, string> = {
    job_title: "職務名稱",
    occupation_category_name: "職類名稱",
    occupation_name: "職業名稱",
    occupation_code: "職業代碼",
    industry_name: "行業名稱",
    industry_code: "行業代碼",
    work_description: "工作描述",
    competency_level: "文件能力級別 L",
    notes: "備註",
  };
  if (headerLabels[collection]) return headerLabels[collection];

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

export type SemanticReviewOperation = "add" | "update" | "delete" | "move";

export type SemanticReviewEvidence = {
  sourceId: string;
  sourceText: string | null;
  createdAt: string | null;
  quote: string | null;
};

export type SemanticReviewGroup = {
  changesetId: string;
  summary: string;
  actionIds: string[];
  acceptanceBlocked: boolean;
  dependencyActionIds: string[];
  evidence: SemanticReviewEvidence[];
};

export type ReviewDecoration = {
  actionId: string;
  path: string;
  entityPath: string | null;
  operation: SemanticReviewOperation;
  baseline: unknown;
  current: unknown;
  group: SemanticReviewGroup;
};

export type DeletedReviewEntity = ReviewDecoration & { entityPath: string };

export type MovedTaskReview = ReviewDecoration & {
  entityPath: string;
  taskId: string;
  fromDutyId: string | null;
  toDutyId: string | null;
  operation: "move";
};

export type SemanticReviewIndex = {
  byPath: Map<string, ReviewDecoration>;
  byEntity: Map<string, ReviewDecoration[]>;
  deletedEntities: DeletedReviewEntity[];
  movedTasks: MovedTaskReview[];
};

function reviewRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function semanticOperation(
  operation: DocumentPatchActionView["operation"],
): SemanticReviewOperation {
  if (operation === "add") return "add";
  if (operation === "withdraw") return "delete";
  if (operation === "reassign") return "move";
  return "update";
}

const entityIdFields = {
  duties: "duty_id",
  tasks: "task_id",
  opks: "item_id",
} as const;

function reviewEntityPath(action: DocumentPatchActionView): string | null {
  const parts = action.path.split("/").filter(Boolean);
  const collection = parts[0] as keyof typeof entityIdFields | undefined;
  if (!collection || !(collection in entityIdFields)) return null;
  if (parts[1]) return `/${collection}/${parts[1]}`;
  const entity = reviewRecord(action.after) ?? reviewRecord(action.before);
  const identity = entity?.[entityIdFields[collection]];
  return typeof identity === "string" ? `/${collection}/${identity}` : null;
}

function reviewGroup(
  snapshot: ConsultantSnapshotView,
  changeset: DocumentChangeSetView,
): SemanticReviewGroup {
  const messages = new Map(
    snapshot.employee_messages.map((message) => [message.source_id, message]),
  );
  const quoteEvidence = changeset.actions.flatMap((action) =>
    action.quote_anchors.map((anchor) => {
      const source = messages.get(anchor.source_id);
      return {
        sourceId: anchor.source_id,
        sourceText: source?.text ?? null,
        createdAt: source?.created_at ?? null,
        quote: anchor.quote,
      } satisfies SemanticReviewEvidence;
    }),
  );
  const quotedSources = new Set(quoteEvidence.map((item) => item.sourceId));
  const sourceEvidence = changeset.source_ids.flatMap((sourceId) => {
    if (quotedSources.has(sourceId)) return [];
    const source = messages.get(sourceId);
    return [
      {
        sourceId,
        sourceText: source?.text ?? null,
        createdAt: source?.created_at ?? null,
        quote: null,
      } satisfies SemanticReviewEvidence,
    ];
  });
  const uniqueEvidence = new Map<string, SemanticReviewEvidence>();
  for (const item of [...quoteEvidence, ...sourceEvidence]) {
    uniqueEvidence.set(`${item.sourceId}:${item.quote ?? ""}`, item);
  }
  return {
    changesetId: changeset.changeset_id,
    summary: changeset.summary,
    actionIds: changeset.actions.map((action) => action.action_id),
    acceptanceBlocked: changeset.acceptance_blocked,
    dependencyActionIds: [
      ...new Set(
        changeset.actions.flatMap((action) => action.depends_on_action_ids),
      ),
    ],
    evidence: [...uniqueEvidence.values()],
  };
}

export function buildSemanticReviewIndex(
  snapshot: ConsultantSnapshotView,
): SemanticReviewIndex {
  const byPath = new Map<string, ReviewDecoration>();
  const byEntity = new Map<string, ReviewDecoration[]>();
  const deletedEntities: DeletedReviewEntity[] = [];
  const movedTasks: MovedTaskReview[] = [];

  for (const changeset of snapshot.document_review.bundles) {
    const group = reviewGroup(snapshot, changeset);
    for (const action of changeset.actions) {
      const entityPath = reviewEntityPath(action);
      const decoration: ReviewDecoration = {
        actionId: action.action_id,
        path: action.path,
        entityPath,
        operation: semanticOperation(action.operation),
        baseline: action.before,
        current: action.after,
        group,
      };
      byPath.set(action.path, decoration);
      if (entityPath) {
        byEntity.set(entityPath, [
          ...(byEntity.get(entityPath) ?? []),
          decoration,
        ]);
      }
      if (entityPath && decoration.operation === "delete") {
        deletedEntities.push({ ...decoration, entityPath });
      }
      const parts = action.path.split("/").filter(Boolean);
      if (
        entityPath &&
        decoration.operation === "move" &&
        parts[0] === "tasks" &&
        parts[1] &&
        parts[2] === "duty_id"
      ) {
        movedTasks.push({
          ...decoration,
          entityPath,
          taskId: parts[1],
          fromDutyId:
            typeof action.before === "string" ? action.before : null,
          toDutyId: typeof action.after === "string" ? action.after : null,
          operation: "move",
        });
      }
    }
  }

  return { byPath, byEntity, deletedEntities, movedTasks };
}

export type ConversationEntry = {
  key: string;
  speaker: "employee" | "consultant";
  text: string;
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
      pending: source.processing_status === "pending",
    });
    for (const message of replies.get(source.source_id) ?? []) {
      result.push({
        key: `consultant:${message.run_id}`,
        speaker: "consultant",
        text: message.text,
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
