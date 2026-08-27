"use client";

import type {
  ApprovedJobDocumentView,
  ApprovedJobDocumentWrite,
  ConsultantSnapshotView,
} from "@caliburn/job-analysis-contract";
import { useForm, useStore } from "@tanstack/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronUp,
  FilePenLine,
  Link2,
  Plus,
  RotateCcw,
  Trash2,
  Unlink,
} from "lucide-react";
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";

import {
  applyCurrentDocumentCommand,
  type CurrentDocumentAuthorityGuards,
  type CurrentDocumentCommand,
  editCurrentDocument,
  JobAnalysisApiError,
  previewCurrentDocumentCommand,
} from "@/shared/api/jobAnalysisApi";
import {
  cacheConsultantSnapshot,
  jobAnalysisKeys,
  refreshConsultantQueries,
} from "@/shared/query/jobAnalysisQueries";
import { Button } from "@/shared/ui/button";
import { CurrentDocumentSection } from "./CurrentDocumentSection";
import {
  DocumentLifecycleMenu,
  type LifecycleConfirmation,
  LifecycleConfirmationDialog,
} from "./DocumentLifecycleMenu";
import { SemanticReviewPopover } from "./SemanticReviewPopover";
import {
  buildSemanticReviewIndex,
  type ReviewDecoration,
} from "./consultantWorkspaceModel";

type CurrentDocument = ApprovedJobDocumentWrite;
type Duty = CurrentDocument["duties"][number];
type Task = CurrentDocument["tasks"][number];
type Opks = CurrentDocument["opks"][number];
type OpksKind = Opks["kind"];
type Enabler = Task["enablers"][number];

export type CurrentJobDocumentEditorHandle = {
  flush: () => Promise<void>;
};

type PendingConfirmation = LifecycleConfirmation & {
  command: CurrentDocumentCommand;
};

const OPKS_LABELS: Record<OpksKind, string> = {
  output: "產出 O",
  indicator: "績效指標 P",
  knowledge: "知識 K",
  skill: "技能 S",
  attitude: "態度 A",
};

const OPKS_SHORT_LABELS: Record<Exclude<OpksKind, "attitude">, string> = {
  output: "O",
  indicator: "P",
  knowledge: "K",
  skill: "S",
};

const ENABLER_LABELS: Record<Enabler["kind"], string> = {
  tool_system: "工具／系統",
  method: "方法",
  knowledge: "知識",
  skill: "技能",
  other: "其他",
};

function toCurrentDocumentWrite(
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

function serialized(value: CurrentDocument): string {
  return JSON.stringify(value);
}

function sameValue(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function mergeCleanEntityFields<T extends object>(
  baseline: T,
  local: T,
  incoming: T,
): T {
  const merged = { ...incoming };
  for (const key of Object.keys(incoming) as Array<keyof T>) {
    if (!sameValue(local[key], baseline[key])) {
      (merged as T)[key] = local[key];
    }
  }
  return merged;
}

function mergeCleanCollectionFields<T extends object, K extends keyof T>(
  baseline: T[],
  local: T[],
  incoming: T[],
  identityKey: K,
): T[] {
  const baselineById = new Map(
    baseline.map((item) => [String(item[identityKey]), item]),
  );
  const localById = new Map(
    local.map((item) => [String(item[identityKey]), item]),
  );
  const incomingIds = new Set(
    incoming.map((item) => String(item[identityKey])),
  );
  const merged = incoming.flatMap((item) => {
    const identity = String(item[identityKey]);
    const baselineItem = baselineById.get(identity);
    const localItem = localById.get(identity);
    if (!localItem) return baselineItem ? [] : [item];
    if (!baselineItem) return [localItem];
    return [mergeCleanEntityFields(baselineItem, localItem, item)];
  });
  for (const localItem of local) {
    const identity = String(localItem[identityKey]);
    if (!incomingIds.has(identity) && !baselineById.has(identity)) {
      merged.push(localItem);
    }
  }
  return merged;
}

function mergeCleanDocumentFields(
  baseline: CurrentDocument,
  local: CurrentDocument,
  incoming: CurrentDocument,
): CurrentDocument {
  const merged = mergeCleanEntityFields(baseline, local, incoming);
  merged.duties = mergeCleanCollectionFields(
    baseline.duties,
    local.duties,
    incoming.duties,
    "duty_id",
  );
  merged.tasks = mergeCleanCollectionFields(
    baseline.tasks,
    local.tasks,
    incoming.tasks,
    "task_id",
  );
  merged.opks = mergeCleanCollectionFields(
    baseline.opks,
    local.opks,
    incoming.opks,
    "item_id",
  );
  return merged;
}

function authorityGuards(
  snapshot: ConsultantSnapshotView,
): CurrentDocumentAuthorityGuards {
  return {
    expectedRevision: snapshot.revision,
    workspaceGeneration: snapshot.document_review.workspace_generation,
    workspaceDigest: snapshot.document_review.workspace_digest,
  };
}

function snapshotSignature(snapshot: ConsultantSnapshotView): string {
  return [
    snapshot.revision,
    snapshot.document_review.workspace_generation,
    snapshot.document_review.workspace_digest,
  ].join(":");
}

function errorText(error: unknown): string {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "目前 JD 尚未儲存，請重試。";
}

function byDisplayOrder<T extends { display_order: number }>(values: T[]): T[] {
  return [...values].sort(
    (left, right) => left.display_order - right.display_order,
  );
}

function reviewValue(value: unknown, path?: string): string {
  if (value === null || value === undefined || value === "") return "未填寫";
  if (path?.endsWith("/responsibility_role") && typeof value === "string") {
    return (
      {
        primary: "主要負責",
        shared: "共同負責",
        assist: "協助",
      }[value] ?? value
    );
  }
  if (path?.endsWith("/competency_level") && typeof value === "number") {
    return `L${value}`;
  }
  if (path?.endsWith("/display_order") && typeof value === "number") {
    return `第 ${value + 1} 順位`;
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) {
    const labels = value.map((item) => {
      if (typeof item === "string" || typeof item === "number") {
        return String(item);
      }
      if (item && typeof item === "object" && "name" in item) {
        return String((item as { name: unknown }).name);
      }
      return "一項內容";
    });
    return labels.length ? labels.join("、") : "未填寫";
  }
  if (typeof value === "object") return "一項完整內容";
  return String(value);
}

function primaryEntityReview(
  decorations: ReviewDecoration[] | undefined,
): ReviewDecoration | undefined {
  if (!decorations?.length) return undefined;
  return (
    decorations.find((item) => item.operation === "add") ??
    decorations.find((item) => item.operation === "move") ??
    decorations.find((item) => item.operation === "update")
  );
}

function ReviewFieldFrame({
  review,
  marker,
  children,
}: {
  review?: ReviewDecoration;
  marker?: ReactNode;
  children: ReactNode;
}) {
  const currentReview = review && review.operation !== "delete" ? review : null;
  return (
    <div
      data-review-current={currentReview ? "true" : undefined}
      className={
        currentReview
          ? "rounded-xl border border-emerald-200 bg-emerald-50/45 p-2"
          : undefined
      }
    >
      {review?.operation === "update" || review?.operation === "delete" ? (
        <p className="mb-2 rounded-lg bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-800">
          <span className="mr-2 font-semibold">
            {review.operation === "delete" ? "AI 建議移除" : "原內容"}
          </span>
          <del>{reviewValue(review.baseline, review.path)}</del>
        </p>
      ) : null}
      {marker ? <div className="mb-1 flex justify-end">{marker}</div> : null}
      {children}
    </div>
  );
}

function TextField({
  label,
  value,
  multiline = false,
  readOnly,
  review,
  reviewMarker,
  onChange,
  onBlur,
}: {
  label: string;
  value: string | null;
  multiline?: boolean;
  readOnly: boolean;
  review?: ReviewDecoration;
  reviewMarker?: ReactNode;
  onChange: (value: string) => void;
  onBlur: () => void;
}) {
  const classes =
    "mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm leading-6 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100 read-only:bg-stone-50";
  return (
    <ReviewFieldFrame review={review} marker={reviewMarker}>
      <label className="block text-xs font-medium text-stone-600">
        {label}
        {multiline ? (
          <textarea
            aria-label={label}
            className={`${classes} min-h-24 resize-y`}
            value={value ?? ""}
            readOnly={readOnly}
            onChange={(event) => onChange(event.target.value)}
            onBlur={onBlur}
          />
        ) : (
          <input
            aria-label={label}
            className={classes}
            value={value ?? ""}
            readOnly={readOnly}
            onChange={(event) => onChange(event.target.value)}
            onBlur={onBlur}
          />
        )}
      </label>
    </ReviewFieldFrame>
  );
}

export const CurrentJobDocumentEditor = forwardRef<
  CurrentJobDocumentEditorHandle,
  {
    documentId: string;
    snapshot: ConsultantSnapshotView;
    mutationLocked?: boolean;
    onDirtyChange: (dirty: boolean) => void;
  }
>(function CurrentJobDocumentEditor(
  { documentId, snapshot, mutationLocked = false, onDirtyChange },
  ref,
) {
  const queryClient = useQueryClient();
  const [formDefaultValues, setFormDefaultValues] = useState<CurrentDocument>(
    () => toCurrentDocumentWrite(snapshot.current_document),
  );
  const form = useForm({ defaultValues: formDefaultValues });
  const values = useStore(form.store, (state) => state.values);
  const reviewIndex = useMemo(
    () => buildSemanticReviewIndex(snapshot),
    [snapshot],
  );
  const valuesSerialized = serialized(values);
  const savedDocumentRef = useRef<CurrentDocument>(formDefaultValues);
  const guardsRef = useRef(authorityGuards(snapshot));
  const latestServerRevisionRef = useRef(snapshot.revision);
  const appliedSnapshotSignatureRef = useRef(snapshotSignature(snapshot));
  const lastSavedSerializedRef = useRef(valuesSerialized);
  const [lastSavedSerialized, setLastSavedSerialized] =
    useState(valuesSerialized);
  const failedSerializedRef = useRef<string | null>(null);
  const staleDraftRef = useRef<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inflightRef = useRef(new Map<string, Promise<void>>());
  const structuralMutationRef = useRef<Promise<void> | null>(null);
  const structuralOperationRef = useRef(false);
  const staleConflictRef = useRef(false);
  const [saveVersion, setSaveVersion] = useState(0);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [staleDraftAvailable, setStaleDraftAvailable] = useState(false);
  const [structuralOperationPending, setStructuralOperationPending] =
    useState(false);
  const [undoToken, setUndoToken] = useState<string | null>(null);
  const [previewPending, setPreviewPending] = useState(false);
  const [pendingConfirmation, setPendingConfirmation] =
    useState<PendingConfirmation | null>(null);

  const absorbSnapshot = useCallback(
    (
      incoming: ConsultantSnapshotView,
      submittedSerialized: string | null = null,
    ) => {
      guardsRef.current = authorityGuards(incoming);
      latestServerRevisionRef.current = incoming.revision;
      appliedSnapshotSignatureRef.current = snapshotSignature(incoming);
      cacheConsultantSnapshot(queryClient, documentId, incoming);
      const serverDocument = toCurrentDocumentWrite(incoming.current_document);
      const serverSerialized = serialized(serverDocument);
      const currentDocument = form.state.values;
      const currentSerialized = serialized(currentDocument);
      const submittedDocument = submittedSerialized
        ? (JSON.parse(submittedSerialized) as CurrentDocument)
        : null;
      const nextDocument =
        submittedDocument && currentSerialized !== submittedSerialized
          ? mergeCleanDocumentFields(
              submittedDocument,
              currentDocument,
              serverDocument,
            )
          : serverDocument;
      savedDocumentRef.current = serverDocument;
      lastSavedSerializedRef.current = serverSerialized;
      setLastSavedSerialized(serverSerialized);
      setFormDefaultValues(nextDocument);
      form.reset(nextDocument);
      failedSerializedRef.current = null;
      staleDraftRef.current = null;
      staleConflictRef.current = false;
      setStaleDraftAvailable(false);
      setSaveError(null);
      setSaveVersion((value) => value + 1);
    },
    [documentId, form, queryClient],
  );

  const autosaveMutation = useMutation({
    mutationKey: jobAnalysisKeys.consultantCurrentDocument(documentId),
    scope: { id: `consultant-current-document:${documentId}` },
    mutationFn: async (operation: {
      document: CurrentDocument;
      documentSerialized: string;
      idempotencyKey: string;
    }) => ({
      snapshot: await editCurrentDocument(
        documentId,
        operation.idempotencyKey,
        guardsRef.current,
        operation.document,
      ),
      documentSerialized: operation.documentSerialized,
    }),
    onSuccess: ({ snapshot: incoming, documentSerialized }) => {
      absorbSnapshot(incoming, documentSerialized);
    },
    onError: async (error, operation) => {
      failedSerializedRef.current = operation.documentSerialized;
      setSaveError(errorText(error));
      setSaveVersion((value) => value + 1);
      if (error instanceof JobAnalysisApiError && error.status === 409) {
        staleDraftRef.current = operation.documentSerialized;
        staleConflictRef.current = true;
        await refreshConsultantQueries(queryClient, documentId);
      }
    },
  });

  const saveDocument = useCallback(
    (document: CurrentDocument, forceRetry = false): Promise<void> => {
      const documentSerialized = serialized(document);
      const existing = inflightRef.current.get(documentSerialized);
      if (existing) return existing;
      if (
        documentSerialized === lastSavedSerializedRef.current ||
        (!forceRetry && failedSerializedRef.current === documentSerialized)
      ) {
        return Promise.resolve();
      }
      const promise = autosaveMutation
        .mutateAsync({
          document,
          documentSerialized,
          idempotencyKey: crypto.randomUUID(),
        })
        .then(() => undefined)
        .finally(() => {
          inflightRef.current.delete(documentSerialized);
          setSaveVersion((value) => value + 1);
        });
      inflightRef.current.set(documentSerialized, promise);
      return promise;
    },
    [autosaveMutation],
  );

  const flushCurrentFields = useCallback(async () => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    if (inflightRef.current.size > 0) {
      await Promise.all(inflightRef.current.values());
    }
    await saveDocument(form.state.values, true);
  }, [form, saveDocument]);

  const flush = useCallback(async () => {
    if (mutationLocked) {
      throw new Error("analysis is active");
    }
    if (structuralMutationRef.current) {
      await structuralMutationRef.current;
    }
    await flushCurrentFields();
  }, [flushCurrentFields, mutationLocked]);

  const requestFlush = useCallback(() => {
    void flush().catch(() => undefined);
  }, [flush]);

  useImperativeHandle(ref, () => ({ flush }), [flush]);

  useEffect(() => {
    if (
      mutationLocked ||
      inflightRef.current.size > 0 ||
      valuesSerialized === lastSavedSerializedRef.current ||
      failedSerializedRef.current === valuesSerialized
    ) {
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      debounceRef.current = null;
      void saveDocument(form.state.values).catch(() => undefined);
    }, 650);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = null;
    };
  }, [form, mutationLocked, saveDocument, saveVersion, valuesSerialized]);

  useEffect(() => {
    const incomingSignature = snapshotSignature(snapshot);
    if (
      snapshot.revision < latestServerRevisionRef.current ||
      incomingSignature === appliedSnapshotSignatureRef.current
    ) {
      return;
    }
    latestServerRevisionRef.current = snapshot.revision;
    appliedSnapshotSignatureRef.current = incomingSignature;
    guardsRef.current = authorityGuards(snapshot);
    const serverDocument = toCurrentDocumentWrite(snapshot.current_document);
    const serverSerialized = serialized(serverDocument);
    const currentDocument = form.state.values;
    const hadStaleConflict = staleConflictRef.current;
    const nextDocument = hadStaleConflict
      ? serverDocument
      : mergeCleanDocumentFields(
          savedDocumentRef.current,
          currentDocument,
          serverDocument,
        );
    savedDocumentRef.current = serverDocument;
    lastSavedSerializedRef.current = serverSerialized;
    setLastSavedSerialized(serverSerialized);
    setFormDefaultValues(nextDocument);
    form.reset(nextDocument);
    if (hadStaleConflict) {
      staleConflictRef.current = false;
      failedSerializedRef.current = null;
      setStaleDraftAvailable(staleDraftRef.current !== null);
      setSaveError("文件已有較新內容，剛才的修改沒有自動合併。");
    } else if (failedSerializedRef.current !== null) {
      failedSerializedRef.current = serialized(nextDocument);
    }
    setSaveVersion((value) => value + 1);
  }, [form, snapshot]);

  const commandMutation = useMutation({
    mutationKey: jobAnalysisKeys.consultantCurrentDocument(documentId),
    scope: { id: `consultant-current-document:${documentId}` },
    mutationFn: (operation: {
      command: CurrentDocumentCommand;
      idempotencyKey: string;
    }) =>
      applyCurrentDocumentCommand(
        documentId,
        operation.idempotencyKey,
        guardsRef.current,
        operation.command,
      ),
    onSuccess: (result) => {
      absorbSnapshot(result.snapshot);
      setUndoToken(result.undo_token);
      setPendingConfirmation(null);
    },
    onError: async (error) => {
      setSaveError(errorText(error));
      if (error instanceof JobAnalysisApiError && error.status === 409) {
        staleConflictRef.current = true;
        await refreshConsultantQueries(queryClient, documentId);
      }
    },
  });

  const documentMutationPending =
    autosaveMutation.isPending ||
    commandMutation.isPending ||
    structuralOperationPending ||
    previewPending;
  const documentDirty =
    valuesSerialized !== lastSavedSerialized || documentMutationPending;

  useEffect(
    () => onDirtyChange(documentDirty),
    [documentDirty, onDirtyChange, saveVersion],
  );

  const runCommand = useCallback(
    async (command: CurrentDocumentCommand) => {
      if (mutationLocked || structuralOperationRef.current) return;
      structuralOperationRef.current = true;
      setStructuralOperationPending(true);
      const promise = (async () => {
        await flushCurrentFields();
        await commandMutation.mutateAsync({
          command,
          idempotencyKey: crypto.randomUUID(),
        });
      })();
      structuralMutationRef.current = promise;
      try {
        await promise;
      } catch {
        // Mutation callbacks keep the employee's values and surface the error.
      } finally {
        if (structuralMutationRef.current === promise) {
          structuralMutationRef.current = null;
        }
        structuralOperationRef.current = false;
        setStructuralOperationPending(false);
      }
    },
    [commandMutation, flushCurrentFields, mutationLocked],
  );

  const restoreStaleDraft = useCallback(() => {
    const draftSerialized = staleDraftRef.current;
    if (!draftSerialized) return;
    const draft = JSON.parse(draftSerialized) as CurrentDocument;
    setFormDefaultValues(draft);
    form.reset(draft);
    failedSerializedRef.current = draftSerialized;
    setStaleDraftAvailable(false);
    setSaveError("剛才的內容已取回，請確認後重試儲存。");
    setSaveVersion((value) => value + 1);
  }, [form]);

  const previewHighImpact = useCallback(
    async (
      command: CurrentDocumentCommand,
      copy: Omit<LifecycleConfirmation, "affectedNames">,
    ) => {
      if (mutationLocked) return;
      setPreviewPending(true);
      setSaveError(null);
      try {
        await flush();
        const preview = await previewCurrentDocumentCommand(
          documentId,
          guardsRef.current,
          command,
        );
        if (!preview.confirmation_required) {
          await runCommand(command);
          return;
        }
        setPendingConfirmation({
          ...copy,
          affectedNames: preview.affected_names,
          command: {
            ...command,
            preview_digest: preview.preview_digest,
          } as CurrentDocumentCommand,
        });
      } catch (error) {
        setSaveError(errorText(error));
      } finally {
        setPreviewPending(false);
      }
    },
    [documentId, flush, mutationLocked, runCommand],
  );

  const patchHeader = (
    field: keyof Pick<
      CurrentDocument,
      | "job_title"
      | "occupation_category_name"
      | "occupation_name"
      | "occupation_code"
      | "industry_name"
      | "industry_code"
      | "work_description"
      | "notes"
    >,
    value: string,
  ) => form.setFieldValue(field, value || null);

  const updateDuty = (dutyId: string, update: Partial<Duty>) =>
    form.setFieldValue("duties", (duties) =>
      duties.map((duty) =>
        duty.duty_id === dutyId ? { ...duty, ...update } : duty,
      ),
    );

  const updateTask = (taskId: string, update: Partial<Task>) =>
    form.setFieldValue("tasks", (tasks) =>
      tasks.map((task) =>
        task.task_id === taskId ? { ...task, ...update } : task,
      ),
    );

  const updateOpks = (itemId: string, update: Partial<Opks>) =>
    form.setFieldValue("opks", (items) =>
      items.map((item) =>
        item.item_id === itemId ? { ...item, ...update } : item,
      ),
    );

  const reorder = (
    entityKind: "duty" | "task" | "opks",
    identities: string[],
    index: number,
    direction: "up" | "down",
    parentId: string | null,
  ) => {
    if (direction === "up" && index === 0) return;
    if (direction === "down" && index === identities.length - 1) return;
    const beforeEntityId =
      direction === "up"
        ? identities[index - 1]
        : (identities[index + 2] ?? null);
    void runCommand({
      operation: "reorder_entity",
      entity_kind: entityKind,
      entity_id: identities[index],
      parent_id: parentId,
      before_entity_id: beforeEntityId,
    });
  };

  const orderedDuties = byDisplayOrder(values.duties);
  const orderedTasks = byDisplayOrder(values.tasks);
  const attitudes = byDisplayOrder(
    values.opks.filter((item) => item.kind === "attitude"),
  );
  const sharedItems = byDisplayOrder(
    values.opks.filter(
      (item) => item.kind === "knowledge" || item.kind === "skill",
    ),
  );
  const unlinkedSharedItems = sharedItems.filter(
    (item) => item.task_ids.length === 0,
  );
  const controlsLocked =
    mutationLocked || structuralOperationPending || previewPending;

  const reviewControl = (
    review: ReviewDecoration | undefined,
    label: string,
  ) =>
    review ? (
      <SemanticReviewPopover
        documentId={documentId}
        snapshot={snapshot}
        decoration={review}
        mutationLocked={controlsLocked}
        beforeDecision={flush}
        triggerLabel={`審核${
          review.operation === "add"
            ? "新增"
            : review.operation === "delete"
              ? "移除"
              : review.operation === "move"
                ? "移動"
                : "修改"
        }：${label}`}
      />
    ) : null;

  const reviewControls = (
    reviews: Array<ReviewDecoration | undefined>,
    label: string,
  ) => {
    const byGroup = new Map<string, ReviewDecoration>();
    for (const review of reviews) {
      if (review) byGroup.set(review.group.changesetId, review);
    }
    return [...byGroup.values()].map((review, index) => (
      <span key={review.group.changesetId}>
        {reviewControl(
          review,
          `${label}${byGroup.size > 1 ? `（第 ${index + 1} 組）` : ""}`,
        )}
      </span>
    ));
  };

  const fieldReview = (path: string) => reviewIndex.byPath.get(path);

  const approvedTasksById = new Map(
    snapshot.approved_document.tasks.map((task) => [task.task_id, task]),
  );
  const approvedDutiesById = new Map(
    snapshot.approved_document.duties.map((duty) => [duty.duty_id, duty]),
  );
  const approvedOpksById = new Map(
    snapshot.approved_document.opks.map((item) => [item.item_id, item]),
  );
  const deletedDutyIds = new Set(
    reviewIndex.deletedEntities.flatMap((review) => {
      const parts = review.entityPath.split("/").filter(Boolean);
      return parts[0] === "duties" && parts[1] ? [parts[1]] : [];
    }),
  );

  const renderTaskGhost = (
    task: ApprovedJobDocumentView["tasks"][number],
    review: ReviewDecoration,
    location: "from" | "deleted",
  ) => {
    const formerItems = byDisplayOrder(
      snapshot.approved_document.opks.filter(
        (item) =>
          item.kind !== "attitude" && item.task_ids.includes(task.task_id),
      ),
    );
    return (
      <div
        key={`${location}:${task.task_id}:${review.actionId}`}
        data-review-operation={review.operation}
        data-review-location={location}
        data-task-id={task.task_id}
        className="rounded-2xl border border-rose-200 bg-rose-50/55 p-4"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold tracking-[0.12em] text-rose-600 uppercase">
              {location === "from" ? "原位置" : "AI 建議移除"}
            </p>
            <p className="mt-1 text-sm font-semibold text-rose-900">
              <del>{task.statement}</del>
            </p>
            {[task.frequency_text, task.responsibility_role]
              .filter(Boolean)
              .length ? (
              <p className="mt-1 text-xs text-rose-700/80">
                <del>
                  {[task.frequency_text, task.responsibility_role]
                    .filter(Boolean)
                    .join(" · ")}
                </del>
              </p>
            ) : null}
          </div>
          {reviewControl(
            review,
            `${location === "from" ? "任務原位置" : "任務"} ${task.statement}`,
          )}
        </div>
        {formerItems.length ? (
          <ul className="mt-3 space-y-1 border-t border-rose-200/70 pt-3 text-xs text-rose-800">
            {formerItems.map((item) => (
              <li key={item.item_id}>
                <del>
                  {OPKS_LABELS[item.kind]}：{item.text}
                </del>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  };

  const taskGhostsForDuty = (dutyId: string | null) => {
    const moved = reviewIndex.movedTasks.flatMap((review) => {
      if (review.fromDutyId !== dutyId || review.toDutyId === dutyId) return [];
      const task = approvedTasksById.get(review.taskId);
      return task ? [renderTaskGhost(task, review, "from")] : [];
    });
    const deleted = reviewIndex.deletedEntities.flatMap((review) => {
      const parts = review.entityPath.split("/").filter(Boolean);
      if (parts[0] !== "tasks" || !parts[1]) return [];
      const task = approvedTasksById.get(parts[1]);
      if (
        !task ||
        task.duty_id !== dutyId ||
        (task.duty_id !== null && deletedDutyIds.has(task.duty_id))
      ) {
        return [];
      }
      return [renderTaskGhost(task, review, "deleted")];
    });
    return [...moved, ...deleted];
  };

  const renderOpks = (task: Task) => {
    const taskItems = byDisplayOrder(
      values.opks.filter(
        (item) =>
          item.kind !== "attitude" && item.task_ids.includes(task.task_id),
      ),
    );
    const deletedTaskItems = reviewIndex.deletedEntities.flatMap((review) => {
      const parts = review.entityPath.split("/").filter(Boolean);
      if (parts[0] !== "opks" || !parts[1]) return [];
      const item = approvedOpksById.get(parts[1]);
      if (
        !item ||
        item.kind === "attitude" ||
        !item.task_ids.includes(task.task_id)
      ) {
        return [];
      }
      return [{ item, review }];
    });
    const kindCounts = new Map<OpksKind, number>();
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-semibold text-stone-500">O／P／K／S</p>
          <label className="text-xs text-stone-500">
            <span className="sr-only">新增 O／P／K／S</span>
            <select
              aria-label={`在${task.statement}新增 O／P／K／S`}
              disabled={controlsLocked}
              defaultValue=""
              className="rounded-lg border border-stone-200 bg-white px-2 py-1"
              onChange={(event) => {
                const kind = event.target.value as Exclude<
                  OpksKind,
                  "attitude"
                >;
                if (kind) {
                  void runCommand({
                    operation: "create_opks",
                    task_id: task.task_id,
                    kind,
                    text: `新增${OPKS_LABELS[kind]}`,
                  });
                  event.target.value = "";
                }
              }}
            >
              <option value="">＋ 新增</option>
              <option value="output">產出 O</option>
              <option value="indicator">績效指標 P</option>
              <option value="knowledge">知識 K</option>
              <option value="skill">技能 S</option>
            </select>
          </label>
        </div>
        {taskItems.length === 0 ? (
          <p className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-stone-500">
            這項任務尚未整理 O／P／K／S。
          </p>
        ) : (
          taskItems.map((item) => {
            const ordinal = (kindCounts.get(item.kind) ?? 0) + 1;
            kindCounts.set(item.kind, ordinal);
            const sameKind = taskItems.filter(
              (candidate) => candidate.kind === item.kind,
            );
            const sameKindIndex = sameKind.findIndex(
              (candidate) => candidate.item_id === item.item_id,
            );
            const shared = item.kind === "knowledge" || item.kind === "skill";
            const itemPath = `/opks/${item.item_id}`;
            const itemEntityReviews = reviewIndex.byEntity.get(itemPath) ?? [];
            const itemEntityReview = primaryEntityReview(itemEntityReviews);
            const itemTextReview = fieldReview(`${itemPath}/text`);
            const itemPlacementReview =
              itemEntityReview?.operation === "add" ||
              itemEntityReview?.operation === "move"
                ? itemEntityReview
                : undefined;
            return (
              <div
                key={item.item_id}
                data-review-operation={itemPlacementReview?.operation}
                className={`grid gap-2 rounded-xl border p-3 sm:grid-cols-[4.5rem_minmax(0,1fr)_auto] ${
                  itemPlacementReview
                    ? "border-emerald-200 bg-emerald-50/45"
                    : "border-stone-100 bg-stone-50/70"
                }`}
              >
                <span className="pt-2 text-xs font-semibold text-stone-500">
                  {
                    OPKS_SHORT_LABELS[
                      item.kind as Exclude<OpksKind, "attitude">
                    ]
                  }{" "}
                  {ordinal}
                </span>
                <ReviewFieldFrame
                  review={itemTextReview}
                  marker={reviewControl(
                    itemTextReview,
                    `${OPKS_LABELS[item.kind]} ${ordinal}`,
                  )}
                >
                  <input
                    aria-label={`${OPKS_LABELS[item.kind]} ${ordinal}`}
                    className="w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm read-only:bg-stone-50"
                    value={item.text}
                    readOnly={controlsLocked}
                    onChange={(event) =>
                      updateOpks(item.item_id, { text: event.target.value })
                    }
                    onBlur={requestFlush}
                  />
                </ReviewFieldFrame>
                <div className="flex items-center gap-1">
                  {reviewControls(
                    itemEntityReviews.filter(
                      (review) => review.path !== `${itemPath}/text`,
                    ),
                    `${OPKS_LABELS[item.kind]} ${ordinal}`,
                  )}
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    aria-label={`上移${OPKS_LABELS[item.kind]} ${ordinal}`}
                    disabled={controlsLocked || sameKindIndex === 0}
                    onClick={() =>
                      reorder(
                        "opks",
                        sameKind.map((candidate) => candidate.item_id),
                        sameKindIndex,
                        "up",
                        task.task_id,
                      )
                    }
                  >
                    <ChevronUp />
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    aria-label={`下移${OPKS_LABELS[item.kind]} ${ordinal}`}
                    disabled={
                      controlsLocked || sameKindIndex === sameKind.length - 1
                    }
                    onClick={() =>
                      reorder(
                        "opks",
                        sameKind.map((candidate) => candidate.item_id),
                        sameKindIndex,
                        "down",
                        task.task_id,
                      )
                    }
                  >
                    <ChevronDown />
                  </Button>
                  {shared ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      aria-label={`解除${item.text}與${task.statement}的連結`}
                      disabled={controlsLocked}
                      onClick={() =>
                        void runCommand({
                          operation: "unlink_shared_opks",
                          item_id: item.item_id,
                          task_id: task.task_id,
                        })
                      }
                    >
                      <Unlink />
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      aria-label={`刪除${OPKS_LABELS[item.kind]} ${ordinal}`}
                      disabled={controlsLocked}
                      onClick={() =>
                        void runCommand({
                          operation: "delete_owned_opks",
                          item_id: item.item_id,
                        })
                      }
                    >
                      <Trash2 />
                    </Button>
                  )}
                </div>
              </div>
            );
          })
        )}
        {deletedTaskItems.map(({ item, review }) => (
          <div
            key={`deleted-opks:${task.task_id}:${item.item_id}`}
            data-review-operation="delete"
            className="flex items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50/55 px-3 py-2"
          >
            <p className="text-sm text-rose-900">
              <span className="mr-2 text-xs font-semibold text-rose-600">
                {OPKS_LABELS[item.kind]}
              </span>
              <del>{item.text}</del>
            </p>
            {reviewControl(review, `${OPKS_LABELS[item.kind]} ${item.text}`)}
          </div>
        ))}
      </div>
    );
  };

  const renderTask = (task: Task, ordinal: number, siblingTasks: Task[]) => {
    const siblingIndex = siblingTasks.findIndex(
      (candidate) => candidate.task_id === task.task_id,
    );
    const taskPath = `/tasks/${task.task_id}`;
    const taskEntityReviews = reviewIndex.byEntity.get(taskPath) ?? [];
    const taskEntityReview = primaryEntityReview(taskEntityReviews);
    const taskPlacementReview =
      taskEntityReview?.operation === "add" ||
      taskEntityReview?.operation === "move"
        ? taskEntityReview
        : undefined;
    return (
      <div
        key={task.task_id}
        data-review-operation={taskPlacementReview?.operation}
        className={
          taskPlacementReview
            ? "rounded-2xl ring-2 ring-emerald-200 ring-offset-2"
            : undefined
        }
      >
        <CurrentDocumentSection
          id={`task-${task.task_id}`}
          ariaLabel={`任務 ${ordinal} ${task.statement}`}
          eyebrow={`任務 ${ordinal}`}
          title={task.statement}
          summary={[task.frequency_text, task.responsibility_role]
            .filter(Boolean)
            .join(" · ")}
          actions={
            <div className="flex items-center gap-1">
              {reviewControls(
                taskEntityReviews.filter(
                  (review) =>
                    review === taskPlacementReview ||
                    review.path === taskPath ||
                    review.path === `${taskPath}/display_order`,
                ),
                `任務 ${ordinal}`,
              )}
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-label={`上移任務 ${ordinal}`}
              disabled={controlsLocked || siblingIndex === 0}
              onClick={() =>
                reorder(
                  "task",
                  siblingTasks.map((item) => item.task_id),
                  siblingIndex,
                  "up",
                  task.duty_id,
                )
              }
            >
              <ChevronUp />
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-label={`下移任務 ${ordinal}`}
              disabled={
                controlsLocked || siblingIndex === siblingTasks.length - 1
              }
              onClick={() =>
                reorder(
                  "task",
                  siblingTasks.map((item) => item.task_id),
                  siblingIndex,
                  "down",
                  task.duty_id,
                )
              }
            >
              <ChevronDown />
            </Button>
            <DocumentLifecycleMenu
              label={`任務 ${ordinal} 操作`}
              disabled={controlsLocked}
              actions={[
                {
                  label: "刪除任務與其 O／P",
                  danger: true,
                  onSelect: () =>
                    void runCommand({
                      operation: "delete_task",
                      task_id: task.task_id,
                    }),
                },
              ]}
            />
            </div>
          }
        >
          <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField
              label={`任務 ${ordinal} 敘述`}
              value={task.statement}
              readOnly={controlsLocked}
              review={fieldReview(`${taskPath}/statement`)}
              reviewMarker={reviewControl(
                fieldReview(`${taskPath}/statement`),
                `任務 ${ordinal} 敘述`,
              )}
              onChange={(statement) => updateTask(task.task_id, { statement })}
              onBlur={requestFlush}
            />
            <TextField
              label={`任務 ${ordinal} 動作`}
              value={task.action}
              readOnly={controlsLocked}
              review={fieldReview(`${taskPath}/action`)}
              reviewMarker={reviewControl(
                fieldReview(`${taskPath}/action`),
                `任務 ${ordinal} 動作`,
              )}
              onChange={(action) => updateTask(task.task_id, { action })}
              onBlur={requestFlush}
            />
            <TextField
              label={`任務 ${ordinal} 對象`}
              value={task.object}
              readOnly={controlsLocked}
              review={fieldReview(`${taskPath}/object`)}
              reviewMarker={reviewControl(
                fieldReview(`${taskPath}/object`),
                `任務 ${ordinal} 對象`,
              )}
              onChange={(object) => updateTask(task.task_id, { object })}
              onBlur={requestFlush}
            />
            <TextField
              label={`任務 ${ordinal} 目的／結果`}
              value={task.purpose_result}
              readOnly={controlsLocked}
              review={fieldReview(`${taskPath}/purpose_result`)}
              reviewMarker={reviewControl(
                fieldReview(`${taskPath}/purpose_result`),
                `任務 ${ordinal} 目的／結果`,
              )}
              onChange={(purpose_result) =>
                updateTask(task.task_id, {
                  purpose_result: purpose_result || null,
                })
              }
              onBlur={requestFlush}
            />
            <TextField
              label={`任務 ${ordinal} 情境`}
              value={task.context}
              readOnly={controlsLocked}
              review={fieldReview(`${taskPath}/context`)}
              reviewMarker={reviewControl(
                fieldReview(`${taskPath}/context`),
                `任務 ${ordinal} 情境`,
              )}
              onChange={(context) =>
                updateTask(task.task_id, { context: context || null })
              }
              onBlur={requestFlush}
            />
            <TextField
              label={`任務 ${ordinal} 頻率`}
              value={task.frequency_text}
              readOnly={controlsLocked}
              review={fieldReview(`${taskPath}/frequency_text`)}
              reviewMarker={reviewControl(
                fieldReview(`${taskPath}/frequency_text`),
                `任務 ${ordinal} 頻率`,
              )}
              onChange={(frequency_text) =>
                updateTask(task.task_id, {
                  frequency_text: frequency_text || null,
                })
              }
              onBlur={requestFlush}
            />
            <ReviewFieldFrame
              review={fieldReview(`${taskPath}/responsibility_role`)}
              marker={reviewControl(
                fieldReview(`${taskPath}/responsibility_role`),
                `任務 ${ordinal} 責任角色`,
              )}
            >
              <label className="block text-xs font-medium text-stone-600">
                責任角色
                <select
                  aria-label={`任務 ${ordinal} 責任角色`}
                  className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm"
                  value={task.responsibility_role ?? ""}
                  disabled={controlsLocked}
                  onChange={(event) =>
                    updateTask(task.task_id, {
                      responsibility_role:
                        (event.target.value as Task["responsibility_role"]) ||
                        null,
                    })
                  }
                  onBlur={requestFlush}
                >
                  <option value="">未設定</option>
                  <option value="primary">主要負責</option>
                  <option value="shared">共同負責</option>
                  <option value="assist">協助</option>
                </select>
              </label>
            </ReviewFieldFrame>
            <ReviewFieldFrame
              review={fieldReview(`${taskPath}/competency_level`)}
              marker={reviewControl(
                fieldReview(`${taskPath}/competency_level`),
                `任務 ${ordinal} 能力級別 L`,
              )}
            >
              <label className="block text-xs font-medium text-stone-600">
                任務能力級別 L（員工填寫）
                <select
                  aria-label={`任務 ${ordinal} 能力級別 L`}
                  className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm"
                  value={task.competency_level ?? ""}
                  disabled={controlsLocked}
                  onChange={(event) =>
                    updateTask(task.task_id, {
                      competency_level: event.target.value
                        ? Number(event.target.value)
                        : null,
                    })
                  }
                  onBlur={requestFlush}
                >
                  <option value="">未設定</option>
                  {[1, 2, 3, 4, 5, 6].map((level) => (
                    <option key={level} value={level}>
                      L{level}
                    </option>
                  ))}
                </select>
              </label>
            </ReviewFieldFrame>
          </div>

          <label className="block text-xs font-medium text-stone-600">
            移動到
            <select
              aria-label={`移動任務 ${ordinal}`}
              className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm"
              value={task.duty_id ?? ""}
              disabled={controlsLocked}
              onChange={(event) =>
                void runCommand({
                  operation: "move_task",
                  task_id: task.task_id,
                  destination_duty_id: event.target.value || null,
                })
              }
            >
              <option value="">尚未歸屬</option>
              {orderedDuties.map((duty, index) => (
                <option key={duty.duty_id} value={duty.duty_id}>
                  職責 {index + 1}　{duty.statement}
                </option>
              ))}
            </select>
          </label>

          <ReviewFieldFrame
            review={fieldReview(`${taskPath}/enablers`)}
            marker={reviewControl(
              fieldReview(`${taskPath}/enablers`),
              `任務 ${ordinal} 工具／方法／促成條件`,
            )}
          >
            <div className="rounded-xl border border-stone-100 bg-stone-50 p-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold text-stone-600">
                工具／方法／促成條件
              </p>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={controlsLocked}
                onClick={() =>
                  updateTask(task.task_id, {
                    enablers: [
                      ...task.enablers,
                      { kind: "tool_system", name: "新工具或方法" },
                    ],
                  })
                }
              >
                <Plus /> 新增
              </Button>
            </div>
            <div className="mt-2 space-y-2">
              {task.enablers.map((enabler, index) => (
                <div
                  key={`${enabler.kind}-${index}`}
                  className="grid gap-2 sm:grid-cols-[9rem_minmax(0,1fr)_auto]"
                >
                  <select
                    aria-label={`促成條件 ${index + 1} 類型`}
                    value={enabler.kind}
                    disabled={controlsLocked}
                    className="rounded-lg border border-stone-200 bg-white px-2 py-2 text-sm"
                    onChange={(event) => {
                      const next = [...task.enablers];
                      next[index] = {
                        ...enabler,
                        kind: event.target.value as Enabler["kind"],
                      };
                      updateTask(task.task_id, { enablers: next });
                    }}
                    onBlur={requestFlush}
                  >
                    {Object.entries(ENABLER_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <input
                    aria-label={`促成條件 ${index + 1} 名稱`}
                    value={enabler.name}
                    readOnly={controlsLocked}
                    className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm read-only:bg-stone-50"
                    onChange={(event) => {
                      const next = [...task.enablers];
                      next[index] = { ...enabler, name: event.target.value };
                      updateTask(task.task_id, { enablers: next });
                    }}
                    onBlur={requestFlush}
                  />
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    aria-label={`刪除促成條件 ${index + 1}`}
                    disabled={controlsLocked}
                    onClick={() =>
                      updateTask(task.task_id, {
                        enablers: task.enablers.filter(
                          (_, itemIndex) => itemIndex !== index,
                        ),
                      })
                    }
                  >
                    <Trash2 />
                  </Button>
                </div>
              ))}
            </div>
            </div>
          </ReviewFieldFrame>
            {renderOpks(task)}
          </div>
        </CurrentDocumentSection>
      </div>
    );
  };

  return (
    <section aria-label="目前 JD 編輯器" className="space-y-4 pb-10">
      <div className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-stone-200 bg-stone-50/95 px-1 py-3 backdrop-blur">
        <div className="flex items-center gap-3">
          <span className="rounded-xl bg-blue-50 p-2 text-blue-700">
            <FilePenLine className="size-5" />
          </span>
          <div>
            <h2 className="text-base font-semibold">目前 JD</h2>
            <p className="text-xs text-stone-500">
              你與 AI 編輯同一份目前內容；AI 變更仍需另外審核。
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <p
            role="status"
            aria-live="polite"
            className="text-xs text-stone-500"
          >
            {saveError
              ? "尚未儲存"
              : documentDirty || commandMutation.isPending
                ? "儲存中…"
                : "已儲存"}
          </p>
          {saveError && !staleDraftAvailable ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={controlsLocked}
              onClick={requestFlush}
            >
              重試儲存
            </Button>
          ) : null}
          {undoToken ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              aria-label="復原上一個操作"
              disabled={controlsLocked}
              onClick={() =>
                void runCommand({ operation: "undo", undo_token: undoToken })
              }
            >
              <RotateCcw /> 復原
            </Button>
          ) : null}
        </div>
      </div>

      {mutationLocked ? (
        <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-950">
          AI 正在分析；完成後可繼續編輯。目前仍可閱讀、展開與選取文字。
        </div>
      ) : null}
      {saveError ? (
        <div
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900"
        >
          <span>
            {saveError}{" "}
            {staleDraftAvailable
              ? "伺服器版本已載入；剛才內容仍可取回。"
              : "你的欄位內容仍保留在畫面上。"}
          </span>
          {staleDraftAvailable ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="ml-3"
              disabled={controlsLocked}
              onClick={restoreStaleDraft}
            >
              取回剛才內容
            </Button>
          ) : null}
        </div>
      ) : null}

      <CurrentDocumentSection
        ariaLabel="職務表頭"
        eyebrow="職務資料"
        title={values.job_title || "尚未命名的職務"}
        summary="職類、行業、工作描述、L 與備註"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="職務名稱"
            value={values.job_title}
            readOnly={controlsLocked}
            review={fieldReview("/job_title")}
            reviewMarker={reviewControl(
              fieldReview("/job_title"),
              "職務名稱",
            )}
            onChange={(value) => patchHeader("job_title", value)}
            onBlur={requestFlush}
          />
          <TextField
            label="職類名稱"
            value={values.occupation_category_name}
            readOnly={controlsLocked}
            review={fieldReview("/occupation_category_name")}
            reviewMarker={reviewControl(
              fieldReview("/occupation_category_name"),
              "職類名稱",
            )}
            onChange={(value) => patchHeader("occupation_category_name", value)}
            onBlur={requestFlush}
          />
          <TextField
            label="職業名稱"
            value={values.occupation_name}
            readOnly={controlsLocked}
            review={fieldReview("/occupation_name")}
            reviewMarker={reviewControl(
              fieldReview("/occupation_name"),
              "職業名稱",
            )}
            onChange={(value) => patchHeader("occupation_name", value)}
            onBlur={requestFlush}
          />
          <TextField
            label="職業代碼"
            value={values.occupation_code}
            readOnly={controlsLocked}
            review={fieldReview("/occupation_code")}
            reviewMarker={reviewControl(
              fieldReview("/occupation_code"),
              "職業代碼",
            )}
            onChange={(value) => patchHeader("occupation_code", value)}
            onBlur={requestFlush}
          />
          <TextField
            label="行業名稱"
            value={values.industry_name}
            readOnly={controlsLocked}
            review={fieldReview("/industry_name")}
            reviewMarker={reviewControl(
              fieldReview("/industry_name"),
              "行業名稱",
            )}
            onChange={(value) => patchHeader("industry_name", value)}
            onBlur={requestFlush}
          />
          <TextField
            label="行業代碼"
            value={values.industry_code}
            readOnly={controlsLocked}
            review={fieldReview("/industry_code")}
            reviewMarker={reviewControl(
              fieldReview("/industry_code"),
              "行業代碼",
            )}
            onChange={(value) => patchHeader("industry_code", value)}
            onBlur={requestFlush}
          />
          <ReviewFieldFrame
            review={fieldReview("/competency_level")}
            marker={reviewControl(
              fieldReview("/competency_level"),
              "文件能力級別 L",
            )}
          >
            <label className="block text-xs font-medium text-stone-600">
              文件能力級別 L（員工填寫）
              <select
                aria-label="文件能力級別 L"
                className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm"
                value={values.competency_level ?? ""}
                disabled={controlsLocked}
                onChange={(event) =>
                  form.setFieldValue(
                    "competency_level",
                    event.target.value ? Number(event.target.value) : null,
                  )
                }
                onBlur={requestFlush}
              >
                <option value="">未設定</option>
                {[1, 2, 3, 4, 5, 6].map((level) => (
                  <option key={level} value={level}>
                    L{level}
                  </option>
                ))}
              </select>
            </label>
          </ReviewFieldFrame>
          <div className="sm:col-span-2">
            <TextField
              label="工作描述"
              value={values.work_description}
              multiline
              readOnly={controlsLocked}
              review={fieldReview("/work_description")}
              reviewMarker={reviewControl(
                fieldReview("/work_description"),
                "工作描述",
              )}
              onChange={(value) => patchHeader("work_description", value)}
              onBlur={requestFlush}
            />
          </div>
          <div className="sm:col-span-2">
            <TextField
              label="備註"
              value={values.notes}
              multiline
              readOnly={controlsLocked}
              review={fieldReview("/notes")}
              reviewMarker={reviewControl(fieldReview("/notes"), "備註")}
              onChange={(value) => patchHeader("notes", value)}
              onBlur={requestFlush}
            />
          </div>
        </div>
      </CurrentDocumentSection>

      <div className="flex items-center justify-between gap-3 pt-2">
        <div>
          <h2 className="text-sm font-semibold">職責與工作</h2>
          <p className="text-xs text-stone-500">
            畫面階層只協助閱讀，不限制 AI 分析順序。
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={controlsLocked}
          onClick={() =>
            void runCommand({ operation: "create_duty", name: "新職責" })
          }
        >
          <Plus /> 新增職責
        </Button>
      </div>

      {orderedDuties.map((duty, dutyIndex) => {
        const dutyTasks = orderedTasks.filter(
          (task) => task.duty_id === duty.duty_id,
        );
        const dutyPath = `/duties/${duty.duty_id}`;
        const dutyEntityReviews = reviewIndex.byEntity.get(dutyPath) ?? [];
        const dutyEntityReview = primaryEntityReview(dutyEntityReviews);
        const dutyPlacementReview =
          dutyEntityReview?.operation === "add" ? dutyEntityReview : undefined;
        const dutyTaskGhosts = taskGhostsForDuty(duty.duty_id);
        return (
          <div
            key={duty.duty_id}
            data-review-operation={dutyPlacementReview?.operation}
            className={
              dutyPlacementReview
                ? "rounded-2xl ring-2 ring-emerald-200 ring-offset-2"
                : undefined
            }
          >
            <CurrentDocumentSection
              id={`duty-${duty.duty_id}`}
              ariaLabel={`職責 ${dutyIndex + 1} ${duty.statement}`}
              eyebrow={`職責 ${dutyIndex + 1}`}
              title={duty.statement}
              summary={`${dutyTasks.length} 項任務`}
              actions={
                <div className="flex items-center gap-1">
                  {reviewControls(
                    dutyEntityReviews.filter(
                      (review) =>
                        review === dutyPlacementReview ||
                        review.path === dutyPath ||
                        review.path === `${dutyPath}/display_order`,
                    ),
                    `職責 ${dutyIndex + 1}`,
                  )}
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-label={`上移職責 ${dutyIndex + 1}`}
                  disabled={controlsLocked || dutyIndex === 0}
                  onClick={() =>
                    reorder(
                      "duty",
                      orderedDuties.map((item) => item.duty_id),
                      dutyIndex,
                      "up",
                      null,
                    )
                  }
                >
                  <ChevronUp />
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-label={`下移職責 ${dutyIndex + 1}`}
                  disabled={
                    controlsLocked || dutyIndex === orderedDuties.length - 1
                  }
                  onClick={() =>
                    reorder(
                      "duty",
                      orderedDuties.map((item) => item.duty_id),
                      dutyIndex,
                      "down",
                      null,
                    )
                  }
                >
                  <ChevronDown />
                </Button>
                <DocumentLifecycleMenu
                  label={`職責 ${dutyIndex + 1} 操作`}
                  disabled={controlsLocked}
                  actions={[
                    {
                      label: "解散職責（保留任務）",
                      onSelect: () =>
                        void runCommand({
                          operation: "dissolve_duty",
                          duty_id: duty.duty_id,
                        }),
                    },
                    {
                      label: "刪除職責與內容",
                      danger: true,
                      onSelect: () =>
                        void previewHighImpact(
                          {
                            operation: "cascade_delete_duty",
                            duty_id: duty.duty_id,
                            preview_digest: null,
                          },
                          {
                            title: "刪除這項職責與內容？",
                            description:
                              "這會刪除職責、其任務與任務專屬 O／P；共用 K／S 只解除關聯。",
                            confirmLabel: "確認刪除",
                          },
                        ),
                    },
                  ]}
                />
                </div>
              }
            >
              <div className="space-y-4">
                <TextField
                  label={`職責 ${dutyIndex + 1} 名稱`}
                  value={duty.statement}
                  readOnly={controlsLocked}
                  review={fieldReview(`${dutyPath}/statement`)}
                  reviewMarker={reviewControl(
                    fieldReview(`${dutyPath}/statement`),
                    `職責 ${dutyIndex + 1} 名稱`,
                  )}
                  onChange={(statement) =>
                    updateDuty(duty.duty_id, { statement })
                  }
                  onBlur={requestFlush}
                />
              <div className="flex justify-end">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={controlsLocked}
                  onClick={() =>
                    void runCommand({
                      operation: "create_task",
                      duty_id: duty.duty_id,
                      statement: "新工作任務",
                      action: "執行",
                      object: "待補充對象",
                      competency_level: null,
                    })
                  }
                >
                  <Plus /> 在職責 {dutyIndex + 1} 新增任務
                </Button>
              </div>
                <div className="space-y-3">
                  {dutyTasks.map((task, taskIndex) =>
                    renderTask(task, taskIndex + 1, dutyTasks),
                  )}
                  {dutyTaskGhosts}
                  {dutyTasks.length === 0 && dutyTaskGhosts.length === 0 ? (
                    <p className="rounded-xl border border-dashed border-stone-200 px-4 py-6 text-center text-sm text-stone-500">
                      這項職責尚未有任務。
                    </p>
                  ) : null}
                </div>
              </div>
            </CurrentDocumentSection>
          </div>
        );
      })}

      {reviewIndex.deletedEntities.flatMap((review) => {
        const parts = review.entityPath.split("/").filter(Boolean);
        if (parts[0] !== "duties" || !parts[1]) return [];
        const duty = approvedDutiesById.get(parts[1]);
        if (!duty) return [];
        const formerTasks = byDisplayOrder(
          snapshot.approved_document.tasks.filter(
            (task) => task.duty_id === duty.duty_id,
          ),
        );
        return [
          <div
            key={`deleted-duty:${duty.duty_id}`}
            data-review-operation="delete"
            className="rounded-2xl border border-rose-200 bg-rose-50/55 p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold tracking-[0.12em] text-rose-600 uppercase">
                  AI 建議移除職責
                </p>
                <p className="mt-1 text-sm font-semibold text-rose-900">
                  <del>{duty.statement}</del>
                </p>
              </div>
              {reviewControl(review, `職責 ${duty.statement}`)}
            </div>
            {formerTasks.length ? (
              <ul className="mt-3 space-y-2 border-t border-rose-200/70 pt-3">
                {formerTasks.map((task) => (
                  <li key={task.task_id} className="text-sm text-rose-800">
                    <del>{task.statement}</del>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>,
        ];
      })}

      <CurrentDocumentSection
        ariaLabel="尚未歸屬任務"
        eyebrow="尚未歸屬"
        title="尚未歸屬任務"
        summary="可先存在並持續補充，之後再移入合適職責"
      >
        <div className="space-y-3">
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={controlsLocked}
              onClick={() =>
                void runCommand({
                  operation: "create_task",
                  duty_id: null,
                  statement: "新工作任務",
                  action: "執行",
                  object: "待補充對象",
                  competency_level: null,
                })
              }
            >
              <Plus /> 新增未歸屬任務
            </Button>
          </div>
          {orderedTasks
            .filter((task) => task.duty_id === null)
            .map((task, index, tasks) => renderTask(task, index + 1, tasks))}
          {taskGhostsForDuty(null)}
        </div>
      </CurrentDocumentSection>

      <CurrentDocumentSection
        ariaLabel="文件層態度 A"
        eyebrow="文件層"
        title="態度 A"
        summary="不掛在單一 Task 下；目前由員工編輯"
      >
        <div className="space-y-2">
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={controlsLocked}
              onClick={() =>
                void runCommand({
                  operation: "create_attitude",
                  text: "新態度",
                })
              }
            >
              <Plus /> 新增態度 A
            </Button>
          </div>
          {attitudes.map((item, index) => {
            const itemPath = `/opks/${item.item_id}`;
            const itemEntityReviews = reviewIndex.byEntity.get(itemPath) ?? [];
            const itemEntityReview = primaryEntityReview(itemEntityReviews);
            const itemTextReview = fieldReview(`${itemPath}/text`);
            const itemPlacementReview =
              itemEntityReview?.operation === "add"
                ? itemEntityReview
                : undefined;
            return (
              <div
                key={item.item_id}
                data-review-operation={itemPlacementReview?.operation}
                className={`grid gap-2 rounded-xl p-2 sm:grid-cols-[4rem_minmax(0,1fr)_auto] ${
                  itemPlacementReview
                    ? "border border-emerald-200 bg-emerald-50/45"
                    : ""
                }`}
              >
                <span className="pt-2 text-xs font-semibold text-stone-500">
                  A {index + 1}
                </span>
                <ReviewFieldFrame
                  review={itemTextReview}
                  marker={reviewControl(
                    itemTextReview,
                    `態度 A ${index + 1}`,
                  )}
                >
                  <input
                    aria-label={`態度 A ${index + 1}`}
                    className="w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm read-only:bg-stone-50"
                    value={item.text}
                    readOnly={controlsLocked}
                    onChange={(event) =>
                      updateOpks(item.item_id, { text: event.target.value })
                    }
                    onBlur={requestFlush}
                  />
                </ReviewFieldFrame>
                <div className="flex items-center gap-1">
                  {reviewControls(
                    itemEntityReviews.filter(
                      (review) => review.path !== `${itemPath}/text`,
                    ),
                    `態度 A ${index + 1}`,
                  )}
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-label={`上移態度 A ${index + 1}`}
                  disabled={controlsLocked || index === 0}
                  onClick={() =>
                    reorder(
                      "opks",
                      attitudes.map((candidate) => candidate.item_id),
                      index,
                      "up",
                      null,
                    )
                  }
                >
                  <ChevronUp />
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-label={`下移態度 A ${index + 1}`}
                  disabled={controlsLocked || index === attitudes.length - 1}
                  onClick={() =>
                    reorder(
                      "opks",
                      attitudes.map((candidate) => candidate.item_id),
                      index,
                      "down",
                      null,
                    )
                  }
                >
                  <ChevronDown />
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-label={`刪除態度 A ${index + 1}`}
                  disabled={controlsLocked}
                  onClick={() =>
                    void runCommand({
                      operation: "delete_owned_opks",
                      item_id: item.item_id,
                    })
                  }
                >
                  <Trash2 />
                </Button>
                </div>
              </div>
            );
          })}
          {reviewIndex.deletedEntities.flatMap((review) => {
            const parts = review.entityPath.split("/").filter(Boolean);
            if (parts[0] !== "opks" || !parts[1]) return [];
            const item = approvedOpksById.get(parts[1]);
            if (!item || item.kind !== "attitude") return [];
            return [
              <div
                key={`deleted-attitude:${item.item_id}`}
                data-review-operation="delete"
                className="flex items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50/55 px-3 py-2"
              >
                <p className="text-sm text-rose-900">
                  <span className="mr-2 text-xs font-semibold">態度 A</span>
                  <del>{item.text}</del>
                </p>
                {reviewControl(review, `態度 A ${item.text}`)}
              </div>,
            ];
          })}
        </div>
      </CurrentDocumentSection>

      <CurrentDocumentSection
        ariaLabel="共用 K／S 管理"
        eyebrow="進階管理"
        title="共用 K／S 管理"
        summary="同一個 K／S 可被多個 Task 使用；解除連結不等於永久刪除"
        defaultOpen={false}
      >
        <div className="space-y-4">
          {unlinkedSharedItems.length ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs font-semibold text-amber-900">
                待重新連結 K／S
              </p>
              <p className="mt-1 text-xs text-amber-800/80">
                這些項目仍保留，但目前沒有連到任何任務。
              </p>
              <ul className="mt-2 space-y-1 text-sm">
                {unlinkedSharedItems.map((item) => (
                  <li key={item.item_id}>{item.text}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {sharedItems.map((item) => {
            const linkedTasks = orderedTasks.filter((task) =>
              item.task_ids.includes(task.task_id),
            );
            const availableTasks = orderedTasks.filter(
              (task) => !item.task_ids.includes(task.task_id),
            );
            const itemPath = `/opks/${item.item_id}`;
            const structuralReviews = (
              reviewIndex.byEntity.get(itemPath) ?? []
            ).filter((review) => review.path !== `${itemPath}/text`);
            return (
              <div
                key={item.item_id}
                className="rounded-xl border border-stone-200 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold text-stone-500">
                      {OPKS_LABELS[item.kind]}
                    </p>
                    <p className="mt-1 text-sm font-medium">{item.text}</p>
                    <p className="mt-1 text-xs text-stone-500">
                      {linkedTasks.length
                        ? `使用於：${linkedTasks.map((task) => task.statement).join("、")}`
                        : "目前未連結任何任務"}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    {reviewControls(
                      structuralReviews,
                      `${OPKS_LABELS[item.kind]} ${item.text}`,
                    )}
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      aria-label={`永久刪除${item.text}`}
                      disabled={controlsLocked}
                      onClick={() =>
                        void previewHighImpact(
                          {
                            operation: "delete_shared_opks",
                            item_id: item.item_id,
                            preview_digest: null,
                          },
                          {
                            title: `永久刪除「${item.text}」？`,
                            description:
                              "這會從所有任務移除同一個共用項目；若只是不屬於某項任務，請在該任務內解除連結。",
                            confirmLabel: "永久刪除",
                          },
                        )
                      }
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>
                {availableTasks.length ? (
                  <label className="mt-3 flex items-center gap-2 text-xs text-stone-500">
                    <Link2 className="size-4" />
                    <select
                      aria-label={`將${item.text}連結到任務`}
                      defaultValue=""
                      disabled={controlsLocked}
                      className="min-w-0 flex-1 rounded-lg border border-stone-200 bg-white px-2 py-1.5"
                      onChange={(event) => {
                        if (event.target.value) {
                          void runCommand({
                            operation: "link_shared_opks",
                            item_id: item.item_id,
                            task_id: event.target.value,
                          });
                          event.target.value = "";
                        }
                      }}
                    >
                      <option value="">連結到其他任務…</option>
                      {availableTasks.map((task) => (
                        <option key={task.task_id} value={task.task_id}>
                          {task.statement}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </div>
            );
          })}
        </div>
      </CurrentDocumentSection>

      <LifecycleConfirmationDialog
        confirmation={pendingConfirmation}
        pending={commandMutation.isPending}
        onCancel={() => setPendingConfirmation(null)}
        onConfirm={() => {
          if (pendingConfirmation) void runCommand(pendingConfirmation.command);
        }}
      />
    </section>
  );
});
