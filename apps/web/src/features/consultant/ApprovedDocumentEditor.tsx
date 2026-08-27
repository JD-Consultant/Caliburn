"use client";

import type {
  ApprovedJobDocumentWrite,
  ConsultantSnapshotView,
} from "@caliburn/job-analysis-contract";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, FilePenLine, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import {
  editApprovedDocument,
  JobAnalysisApiError,
} from "@/shared/api/jobAnalysisApi";
import {
  cacheConsultantSnapshot,
  refreshConsultantQueries,
} from "@/shared/query/jobAnalysisQueries";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import {
  pruneApprovedDocumentRelations,
  toApprovedDocumentWrite,
} from "./consultantWorkspaceModel";

type TaskDraft = ApprovedJobDocumentWrite["tasks"][number];
type OpksDraft = ApprovedJobDocumentWrite["opks"][number];
type EnablerDraft = TaskDraft["enablers"][number];
type DocumentDraftState = {
  draft: ApprovedJobDocumentWrite;
  baselineRevision: number;
};

const DRAFT_STORAGE_VERSION = 1;

function draftStorageKey(documentId: string): string {
  return `caliburn:consultant-document-draft:${documentId}`;
}

function readStoredDraft(documentId: string): DocumentDraftState | null {
  try {
    const raw = localStorage.getItem(draftStorageKey(documentId));
    if (!raw) return null;
    const value = JSON.parse(raw) as {
      version?: unknown;
      baselineRevision?: unknown;
      draft?: unknown;
    };
    if (
      value.version !== DRAFT_STORAGE_VERSION ||
      !Number.isInteger(value.baselineRevision) ||
      typeof value.draft !== "object" ||
      value.draft === null
    ) {
      localStorage.removeItem(draftStorageKey(documentId));
      return null;
    }
    const draft = value.draft as Partial<ApprovedJobDocumentWrite>;
    if (
      draft.document_id !== documentId ||
      !Array.isArray(draft.duties) ||
      !Array.isArray(draft.tasks) ||
      !Array.isArray(draft.opks)
    ) {
      localStorage.removeItem(draftStorageKey(documentId));
      return null;
    }
    return {
      draft: draft as ApprovedJobDocumentWrite,
      baselineRevision: value.baselineRevision as number,
    };
  } catch {
    localStorage.removeItem(draftStorageKey(documentId));
    return null;
  }
}

const opksLabels: Record<OpksDraft["kind"], string> = {
  output: "產出 O",
  indicator: "績效指標 P",
  knowledge: "知識 K",
  skill: "技能 S",
  attitude: "態度 A（員工直接編輯）",
};

const enablerLabels: Record<EnablerDraft["kind"], string> = {
  tool_system: "工具／系統",
  method: "方法",
  knowledge: "知識",
  skill: "技能",
  other: "其他",
};

function optionalText(value: string | null): string | null {
  const normalized = value?.trim() ?? "";
  return normalized || null;
}

function normalizedDocument(
  value: ApprovedJobDocumentWrite,
): ApprovedJobDocumentWrite {
  const opksOrder = new Map<OpksDraft["kind"], number>();
  const normalized = {
    ...value,
    job_title: optionalText(value.job_title),
    occupation_category_name: optionalText(value.occupation_category_name),
    occupation_name: optionalText(value.occupation_name),
    occupation_code: optionalText(value.occupation_code),
    industry_name: optionalText(value.industry_name),
    industry_code: optionalText(value.industry_code),
    work_description: optionalText(value.work_description),
    notes: optionalText(value.notes),
    duties: value.duties.map((duty, index) => ({
      ...duty,
      statement: duty.statement.trim(),
      display_order: index,
    })),
    tasks: value.tasks.map((task, index) => ({
      ...task,
      statement: task.statement.trim(),
      action: task.action.trim(),
      object: task.object.trim(),
      purpose_result: optionalText(task.purpose_result),
      context: optionalText(task.context),
      frequency_text: optionalText(task.frequency_text),
      responsibility_role: task.responsibility_role || null,
      enablers: task.enablers
        .map((item) => ({ ...item, name: item.name.trim() }))
        .filter((item) => item.name),
      display_order: index,
    })),
    opks: value.opks.map((item) => {
      const order = opksOrder.get(item.kind) ?? 0;
      opksOrder.set(item.kind, order + 1);
      return {
        ...item,
        text: item.text.trim(),
        display_order: order,
      };
    }),
  };
  return pruneApprovedDocumentRelations(normalized);
}

function validationMessage(value: ApprovedJobDocumentWrite): string | null {
  if (value.duties.some((item) => !item.statement.trim())) {
    return "每項職責都需要名稱。";
  }
  if (
    value.tasks.some(
      (item) =>
        !item.statement.trim() || !item.action.trim() || !item.object.trim(),
    )
  ) {
    return "每項工作都需要工作敘述、動作與對象。";
  }
  if (value.opks.some((item) => !item.text.trim())) {
    return "每項 O／P／K／S／A 都需要內容。";
  }
  if (
    value.opks.some(
      (item) =>
        ["output", "indicator"].includes(item.kind) &&
        item.task_ids.length !== 1,
    )
  ) {
    return "每項 O 與 P 必須連到一項工作。";
  }
  return null;
}

function errorText(error: unknown): string {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "正式文件無法儲存，請稍後再試";
}

function Field({
  label,
  value,
  onChange,
  multiline = false,
  readOnly = false,
}: {
  label: string;
  value: string | null;
  onChange: (value: string) => void;
  multiline?: boolean;
  readOnly?: boolean;
}) {
  const common = {
    value: value ?? "",
    onChange: (
      event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
    ) => onChange(event.target.value),
    readOnly,
    className:
      "mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm",
  };
  return (
    <label className="block text-xs font-medium text-stone-600">
      {label}
      {multiline ? (
        <textarea {...common} className={`${common.className} min-h-24`} />
      ) : (
        <input {...common} />
      )}
    </label>
  );
}

export function ApprovedDocumentEditor({
  documentId,
  snapshot,
  onDirtyChange,
  mutationLocked = false,
}: {
  documentId: string;
  snapshot: ConsultantSnapshotView;
  onDirtyChange: (dirty: boolean) => void;
  mutationLocked?: boolean;
}) {
  const queryClient = useQueryClient();
  const [draftState, setDraftState] = useState<DocumentDraftState | null>(() =>
    readStoredDraft(documentId),
  );
  const [validationError, setValidationError] = useState<string | null>(null);
  const draft =
    draftState?.draft ?? toApprovedDocumentWrite(snapshot.approved_document);
  const baselineRevision = draftState?.baselineRevision ?? snapshot.revision;
  const dirty = draftState !== null;
  const conflict = dirty && snapshot.revision > baselineRevision;

  useEffect(() => {
    if (draftState === null) {
      localStorage.removeItem(draftStorageKey(documentId));
      return;
    }
    localStorage.setItem(
      draftStorageKey(documentId),
      JSON.stringify({ version: DRAFT_STORAGE_VERSION, ...draftState }),
    );
  }, [documentId, draftState]);

  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);

  const mutation = useMutation({
    mutationFn: (operation: {
      document: ApprovedJobDocumentWrite;
      idempotencyKey: string;
      expectedRevision: number;
    }) =>
      editApprovedDocument(
        documentId,
        operation.idempotencyKey,
        operation.expectedRevision,
        operation.document,
      ),
    onSuccess: async (result) => {
      cacheConsultantSnapshot(queryClient, documentId, result);
      setDraftState(null);
      setValidationError(null);
      await refreshConsultantQueries(queryClient, documentId);
    },
    onError: async (error) => {
      if (error instanceof JobAnalysisApiError && error.status === 409) {
        await refreshConsultantQueries(queryClient, documentId);
      }
    },
  });

  const change = (
    update: (draft: ApprovedJobDocumentWrite) => ApprovedJobDocumentWrite,
  ) => {
    if (mutationLocked) return;
    setDraftState((current) => ({
      draft: update(
        current?.draft ?? toApprovedDocumentWrite(snapshot.approved_document),
      ),
      baselineRevision: current?.baselineRevision ?? snapshot.revision,
    }));
  };
  const patchHeader = (
    field: keyof Pick<
      ApprovedJobDocumentWrite,
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
  ) => change((draft) => ({ ...draft, [field]: value }));

  const save = () => {
    const document = normalizedDocument(draft);
    const invalid = validationMessage(document);
    setValidationError(invalid);
    if (invalid || conflict || mutationLocked || mutation.isPending) return;
    const previous = mutation.variables;
    const retry =
      mutation.isError &&
      previous?.expectedRevision === baselineRevision &&
      JSON.stringify(previous.document) === JSON.stringify(document);
    mutation.mutate(
      retry
        ? previous
        : {
            document,
            expectedRevision: baselineRevision,
            idempotencyKey: crypto.randomUUID(),
          },
    );
  };

  const addDuty = () =>
    change((draft) => ({
      ...draft,
      duties: [
        ...draft.duties,
        {
          duty_id: crypto.randomUUID(),
          statement: "新職責",
          display_order: draft.duties.length,
        },
      ],
    }));
  const deleteDuty = (dutyId: string) =>
    change((draft) => ({
      ...draft,
      duties: draft.duties
        .filter((item) => item.duty_id !== dutyId)
        .map((item, index) => ({ ...item, display_order: index })),
      tasks: draft.tasks.map((task) =>
        task.duty_id === dutyId ? { ...task, duty_id: null } : task,
      ),
    }));
  const addTask = () =>
    change((draft) => ({
      ...draft,
      tasks: [
        ...draft.tasks,
        {
          task_id: crypto.randomUUID(),
          duty_id: null,
          statement: "新工作",
          action: "執行",
          object: "待補充對象",
          purpose_result: null,
          context: null,
          frequency_text: null,
          responsibility_role: null,
          enablers: [],
          display_order: draft.tasks.length,
          competency_level: null,
        },
      ],
    }));
  const deleteTask = (taskId: string) =>
    change((draft) => ({
      ...draft,
      tasks: draft.tasks
        .filter((item) => item.task_id !== taskId)
        .map((item, index) => ({ ...item, display_order: index })),
      opks: draft.opks
        .filter(
          (item) =>
            !(
              ["output", "indicator"].includes(item.kind) &&
              item.task_ids.includes(taskId)
            ),
        )
        .map((item) => ({
          ...item,
          task_ids: item.task_ids.filter((id) => id !== taskId),
        })),
    }));
  const addOpks = (kind: OpksDraft["kind"]) => {
    if (mutationLocked) return;
    if (["output", "indicator"].includes(kind) && !draft.tasks.length) {
      setValidationError("請先建立工作，才能新增 O 或 P。");
      return;
    }
    change((draft) => ({
      ...draft,
      opks: [
        ...draft.opks,
        {
          item_id: crypto.randomUUID(),
          kind,
          text: `新增${opksLabels[kind]}`,
          display_order: draft.opks.filter((item) => item.kind === kind).length,
          task_ids:
            kind === "output" || kind === "indicator"
              ? [draft.tasks[0].task_id]
              : [],
          indicator_ids: [],
        },
      ],
    }));
  };

  return (
    <section aria-label="目前正式職務說明書">
      <Card className="border-emerald-200 bg-emerald-50/40 p-5 shadow-sm">
        <details>
          <summary className="cursor-pointer list-none">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-emerald-100 p-2 text-emerald-800">
                <FilePenLine className="size-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold tracking-[0.16em] text-emerald-800 uppercase">
                  員工核准內容
                </p>
                <h2 className="mt-1 text-lg font-semibold">
                  目前正式職務說明書
                </h2>
                <p className="text-xs text-stone-600">
                  你可直接編輯；自己的修改不需要再經 AI 審核。
                </p>
              </div>
              <ChevronDown className="size-5 text-stone-500" />
            </div>
          </summary>

          <fieldset disabled={mutationLocked} className="contents">
            <div className="mt-5 space-y-6 border-t border-emerald-200 pt-5">
              {conflict ? (
                <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
                  <p className="font-semibold">正式內容已在背景更新</p>
                  <p className="mt-1">
                    為避免覆蓋你的未儲存草稿，畫面沒有自動替換。請重新載入後再編輯。
                  </p>
                  <Button
                    className="mt-3"
                    variant="outline"
                    disabled={mutationLocked}
                    onClick={() => setDraftState(null)}
                  >
                    捨棄草稿並載入最新正式內容
                  </Button>
                </div>
              ) : null}

              <fieldset className="grid gap-4 sm:grid-cols-2">
                <legend className="col-span-full text-sm font-semibold">
                  基本資料
                </legend>
                <Field
                  readOnly={mutationLocked}
                  label="職務名稱"
                  value={draft.job_title}
                  onChange={(value) => patchHeader("job_title", value)}
                />
                <label className="block text-xs font-medium text-stone-600">
                  能力級別（目前僅員工直接編輯）
                  <select
                    className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                    value={draft.competency_level ?? ""}
                    onChange={(event) =>
                      change((value) => ({
                        ...value,
                        competency_level: event.target.value
                          ? Number(event.target.value)
                          : null,
                      }))
                    }
                  >
                    <option value="">未填</option>
                    {[1, 2, 3, 4, 5, 6].map((level) => (
                      <option key={level} value={level}>
                        {level}
                      </option>
                    ))}
                  </select>
                </label>
                <Field
                  label="職類名稱"
                  value={draft.occupation_category_name}
                  onChange={(value) =>
                    patchHeader("occupation_category_name", value)
                  }
                />
                <Field
                  label="職業名稱"
                  value={draft.occupation_name}
                  onChange={(value) => patchHeader("occupation_name", value)}
                />
                <Field
                  label="員工填寫的職業分類代碼"
                  value={draft.occupation_code}
                  onChange={(value) => patchHeader("occupation_code", value)}
                />
                <Field
                  label="行業名稱"
                  value={draft.industry_name}
                  onChange={(value) => patchHeader("industry_name", value)}
                />
                <Field
                  label="員工填寫的行業分類代碼"
                  value={draft.industry_code}
                  onChange={(value) => patchHeader("industry_code", value)}
                />
                <div className="sm:col-span-2">
                  <Field
                    multiline
                    label="工作描述"
                    value={draft.work_description}
                    onChange={(value) => patchHeader("work_description", value)}
                  />
                </div>
                <div className="sm:col-span-2">
                  <Field
                    multiline
                    label="備註"
                    value={draft.notes}
                    onChange={(value) => patchHeader("notes", value)}
                  />
                </div>
              </fieldset>

              <div>
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold">主要職責 Duty</h3>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={mutationLocked}
                    onClick={addDuty}
                  >
                    <Plus />
                    新增職責
                  </Button>
                </div>
                <div className="mt-3 space-y-2">
                  {draft.duties.map((duty, index) => (
                    <div
                      id={`duty-${duty.duty_id}`}
                      key={duty.duty_id}
                      className="flex gap-2 scroll-mt-24"
                    >
                      <input
                        aria-label={`職責 ${index + 1}`}
                        className="min-w-0 flex-1 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                        value={duty.statement}
                        onChange={(event) =>
                          change((value) => ({
                            ...value,
                            duties: value.duties.map((item) =>
                              item.duty_id === duty.duty_id
                                ? { ...item, statement: event.target.value }
                                : item,
                            ),
                          }))
                        }
                      />
                      <Button
                        disabled={mutationLocked}
                        variant="ghost"
                        size="icon"
                        aria-label="刪除職責"
                        onClick={() => deleteDuty(duty.duty_id)}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold">工作 Task</h3>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={mutationLocked}
                    onClick={addTask}
                  >
                    <Plus />
                    新增工作
                  </Button>
                </div>
                <div className="mt-3 space-y-4">
                  {draft.tasks.map((task, index) => (
                    <div
                      id={`task-${task.task_id}`}
                      key={task.task_id}
                      className="scroll-mt-24 rounded-xl border border-stone-200 bg-white p-4"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold">
                          工作 {index + 1}
                        </p>
                        <Button
                          disabled={mutationLocked}
                          variant="ghost"
                          size="icon"
                          aria-label="刪除工作"
                          onClick={() => deleteTask(task.task_id)}
                        >
                          <Trash2 />
                        </Button>
                      </div>
                      <div className="mt-3 grid gap-3 sm:grid-cols-2">
                        {(
                          [
                            "statement",
                            "action",
                            "object",
                            "purpose_result",
                            "context",
                            "frequency_text",
                          ] as const
                        ).map((field) => (
                          <Field
                            key={field}
                            readOnly={mutationLocked}
                            label={
                              {
                                statement: "工作敘述",
                                action: "動作",
                                object: "對象",
                                purpose_result: "目的／結果",
                                context: "情境",
                                frequency_text: "頻率",
                              }[field]
                            }
                            value={task[field]}
                            onChange={(next) =>
                              change((value) => ({
                                ...value,
                                tasks: value.tasks.map((item) =>
                                  item.task_id === task.task_id
                                    ? { ...item, [field]: next }
                                    : item,
                                ),
                              }))
                            }
                          />
                        ))}
                        <label className="block text-xs font-medium text-stone-600">
                          所屬職責（可先不分組）
                          <select
                            className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                            value={task.duty_id ?? ""}
                            onChange={(event) =>
                              change((value) => ({
                                ...value,
                                tasks: value.tasks.map((item) =>
                                  item.task_id === task.task_id
                                    ? {
                                        ...item,
                                        duty_id: event.target.value || null,
                                      }
                                    : item,
                                ),
                              }))
                            }
                          >
                            <option value="">尚未分組</option>
                            {draft.duties.map((duty) => (
                              <option key={duty.duty_id} value={duty.duty_id}>
                                {duty.statement}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="block text-xs font-medium text-stone-600">
                          責任角色
                          <select
                            className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                            value={task.responsibility_role ?? ""}
                            onChange={(event) =>
                              change((value) => ({
                                ...value,
                                tasks: value.tasks.map((item) =>
                                  item.task_id === task.task_id
                                    ? {
                                        ...item,
                                        responsibility_role: (event.target
                                          .value ||
                                          null) as TaskDraft["responsibility_role"],
                                      }
                                    : item,
                                ),
                              }))
                            }
                          >
                            <option value="">未填</option>
                            <option value="primary">主要負責</option>
                            <option value="shared">共同負責</option>
                            <option value="assist">協助</option>
                          </select>
                        </label>
                        <label className="block text-xs font-medium text-stone-600">
                          工作能力級別（目前僅員工直接編輯）
                          <select
                            className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                            value={task.competency_level ?? ""}
                            onChange={(event) =>
                              change((value) => ({
                                ...value,
                                tasks: value.tasks.map((item) =>
                                  item.task_id === task.task_id
                                    ? {
                                        ...item,
                                        competency_level: event.target.value
                                          ? Number(event.target.value)
                                          : null,
                                      }
                                    : item,
                                ),
                              }))
                            }
                          >
                            <option value="">未填</option>
                            {[1, 2, 3, 4, 5, 6].map((level) => (
                              <option key={level} value={level}>
                                {level}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                      <div className="mt-4">
                        <div className="flex items-center justify-between">
                          <p className="text-xs font-medium text-stone-600">
                            工具／方法／其他促成條件
                          </p>
                          <Button
                            size="xs"
                            variant="ghost"
                            disabled={mutationLocked}
                            onClick={() =>
                              change((value) => ({
                                ...value,
                                tasks: value.tasks.map((item) =>
                                  item.task_id === task.task_id
                                    ? {
                                        ...item,
                                        enablers: [
                                          ...item.enablers,
                                          { kind: "other", name: "" },
                                        ],
                                      }
                                    : item,
                                ),
                              }))
                            }
                          >
                            <Plus />
                            新增
                          </Button>
                        </div>
                        {task.enablers.map((enabler, enablerIndex) => (
                          <div
                            key={`${task.task_id}-${enablerIndex}`}
                            className="mt-2 flex gap-2"
                          >
                            <select
                              className="rounded-lg border border-stone-300 bg-white px-2 py-2 text-xs"
                              value={enabler.kind}
                              onChange={(event) =>
                                change((value) => ({
                                  ...value,
                                  tasks: value.tasks.map((item) =>
                                    item.task_id === task.task_id
                                      ? {
                                          ...item,
                                          enablers: item.enablers.map(
                                            (entry, i) =>
                                              i === enablerIndex
                                                ? {
                                                    ...entry,
                                                    kind: event.target
                                                      .value as EnablerDraft["kind"],
                                                  }
                                                : entry,
                                          ),
                                        }
                                      : item,
                                  ),
                                }))
                              }
                            >
                              {Object.entries(enablerLabels).map(
                                ([kind, label]) => (
                                  <option key={kind} value={kind}>
                                    {label}
                                  </option>
                                ),
                              )}
                            </select>
                            <input
                              className="min-w-0 flex-1 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                              value={enabler.name}
                              onChange={(event) =>
                                change((value) => ({
                                  ...value,
                                  tasks: value.tasks.map((item) =>
                                    item.task_id === task.task_id
                                      ? {
                                          ...item,
                                          enablers: item.enablers.map(
                                            (entry, i) =>
                                              i === enablerIndex
                                                ? {
                                                    ...entry,
                                                    name: event.target.value,
                                                  }
                                                : entry,
                                          ),
                                        }
                                      : item,
                                  ),
                                }))
                              }
                            />
                            <Button
                              disabled={mutationLocked}
                              variant="ghost"
                              size="icon"
                              aria-label="刪除促成條件"
                              onClick={() =>
                                change((value) => ({
                                  ...value,
                                  tasks: value.tasks.map((item) =>
                                    item.task_id === task.task_id
                                      ? {
                                          ...item,
                                          enablers: item.enablers.filter(
                                            (_, i) => i !== enablerIndex,
                                          ),
                                        }
                                      : item,
                                  ),
                                }))
                              }
                            >
                              <Trash2 />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold">O／P／K／S／A</h3>
                  <div className="flex flex-wrap gap-1">
                    {(Object.keys(opksLabels) as OpksDraft["kind"][]).map(
                      (kind) => (
                        <Button
                          key={kind}
                          size="xs"
                          variant="outline"
                          disabled={mutationLocked}
                          onClick={() => addOpks(kind)}
                        >
                          <Plus />
                          {opksLabels[kind]}
                        </Button>
                      ),
                    )}
                  </div>
                </div>
                <p className="mt-2 text-xs text-stone-500">
                  LLM 第一版只提 O／P／K／S；A 仍可由你直接填寫。
                </p>
                <div className="mt-3 space-y-3">
                  {draft.opks.map((item) => (
                    <div
                      key={item.item_id}
                      className="rounded-xl border border-stone-200 bg-white p-4"
                    >
                      <div className="flex gap-2">
                        <select
                          className="rounded-lg border border-stone-300 bg-white px-2 py-2 text-xs"
                          value={item.kind}
                          onChange={(event) => {
                            const kind = event.target
                              .value as OpksDraft["kind"];
                            change((value) => ({
                              ...value,
                              opks: value.opks.map((entry) =>
                                entry.item_id === item.item_id
                                  ? {
                                      ...entry,
                                      kind,
                                      task_ids:
                                        kind === "attitude"
                                          ? []
                                          : ["output", "indicator"].includes(
                                                kind,
                                              )
                                            ? value.tasks[0]
                                              ? [value.tasks[0].task_id]
                                              : []
                                            : entry.task_ids,
                                      indicator_ids: [
                                        "knowledge",
                                        "skill",
                                      ].includes(kind)
                                        ? entry.indicator_ids
                                        : [],
                                    }
                                  : entry,
                              ),
                            }));
                          }}
                        >
                          {Object.entries(opksLabels).map(([kind, label]) => (
                            <option key={kind} value={kind}>
                              {label}
                            </option>
                          ))}
                        </select>
                        <input
                          className="min-w-0 flex-1 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                          value={item.text}
                          onChange={(event) =>
                            change((value) => ({
                              ...value,
                              opks: value.opks.map((entry) =>
                                entry.item_id === item.item_id
                                  ? { ...entry, text: event.target.value }
                                  : entry,
                              ),
                            }))
                          }
                        />
                        <Button
                          disabled={mutationLocked}
                          variant="ghost"
                          size="icon"
                          aria-label="刪除職能內容"
                          onClick={() =>
                            change((value) => ({
                              ...value,
                              opks: value.opks.filter(
                                (entry) => entry.item_id !== item.item_id,
                              ),
                            }))
                          }
                        >
                          <Trash2 />
                        </Button>
                      </div>
                      {item.kind !== "attitude" ? (
                        <div className="mt-3">
                          <p className="text-xs font-medium text-stone-600">
                            連結工作
                          </p>
                          {item.kind === "output" ||
                          item.kind === "indicator" ? (
                            <select
                              className="mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                              value={item.task_ids[0] ?? ""}
                              onChange={(event) =>
                                change((value) => ({
                                  ...value,
                                  opks: value.opks.map((entry) =>
                                    entry.item_id === item.item_id
                                      ? {
                                          ...entry,
                                          task_ids: event.target.value
                                            ? [event.target.value]
                                            : [],
                                        }
                                      : entry,
                                  ),
                                }))
                              }
                            >
                              <option value="">選擇工作</option>
                              {draft.tasks.map((task) => (
                                <option key={task.task_id} value={task.task_id}>
                                  {task.statement}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <div className="mt-1 flex flex-wrap gap-3">
                              {draft.tasks.map((task) => (
                                <label
                                  key={task.task_id}
                                  className="flex items-center gap-1.5 text-xs"
                                >
                                  <input
                                    type="checkbox"
                                    checked={item.task_ids.includes(
                                      task.task_id,
                                    )}
                                    onChange={(event) =>
                                      change((value) => ({
                                        ...value,
                                        opks: value.opks.map((entry) =>
                                          entry.item_id === item.item_id
                                            ? {
                                                ...entry,
                                                task_ids: event.target.checked
                                                  ? [
                                                      ...entry.task_ids,
                                                      task.task_id,
                                                    ]
                                                  : entry.task_ids.filter(
                                                      (id) =>
                                                        id !== task.task_id,
                                                    ),
                                              }
                                            : entry,
                                        ),
                                      }))
                                    }
                                  />
                                  {task.statement}
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                      ) : null}
                      {["knowledge", "skill"].includes(item.kind) &&
                      draft.opks.some((entry) => entry.kind === "indicator") ? (
                        <div className="mt-3">
                          <p className="text-xs font-medium text-stone-600">
                            關聯績效指標（選填）
                          </p>
                          <div className="mt-1 flex flex-wrap gap-3">
                            {draft.opks
                              .filter((entry) => entry.kind === "indicator")
                              .map((indicator) => (
                                <label
                                  key={indicator.item_id}
                                  className="flex items-center gap-1.5 text-xs"
                                >
                                  <input
                                    type="checkbox"
                                    checked={item.indicator_ids.includes(
                                      indicator.item_id,
                                    )}
                                    onChange={(event) =>
                                      change((value) => ({
                                        ...value,
                                        opks: value.opks.map((entry) =>
                                          entry.item_id === item.item_id
                                            ? {
                                                ...entry,
                                                indicator_ids: event.target
                                                  .checked
                                                  ? [
                                                      ...entry.indicator_ids,
                                                      indicator.item_id,
                                                    ]
                                                  : entry.indicator_ids.filter(
                                                      (id) =>
                                                        id !==
                                                        indicator.item_id,
                                                    ),
                                              }
                                            : entry,
                                        ),
                                      }))
                                    }
                                  />
                                  {indicator.text}
                                </label>
                              ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>

              <div className="sticky bottom-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-stone-200 bg-white/95 p-3 shadow-lg backdrop-blur">
                <p className="text-xs text-stone-500">
                  {dirty ? "有未儲存的員工修改" : "已同步最新正式內容"}
                </p>
                <div className="flex gap-2">
                  {dirty ? (
                    <Button
                      variant="ghost"
                      disabled={mutationLocked}
                      onClick={() => setDraftState(null)}
                    >
                      取消修改
                    </Button>
                  ) : null}
                  <Button
                    disabled={
                      mutationLocked || !dirty || conflict || mutation.isPending
                    }
                    onClick={save}
                  >
                    <Save />
                    {mutation.isPending ? "儲存中…" : "儲存正式文件"}
                  </Button>
                </div>
              </div>
              {validationError ? (
                <p role="alert" className="text-sm text-destructive">
                  {validationError}
                </p>
              ) : null}
              {mutation.isError ? (
                <p role="alert" className="text-sm text-destructive">
                  {errorText(mutation.error)}；草稿仍保留。
                </p>
              ) : null}
            </div>
          </fieldset>
        </details>
      </Card>
    </section>
  );
}
