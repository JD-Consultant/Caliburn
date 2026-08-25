"use client";

import type {
  ApprovedJobDocumentWrite,
  ConsultantSnapshotView,
} from "@caliburn/job-analysis-contract";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Save } from "lucide-react";
import { useEffect, useState } from "react";

import {
  editCurrentDocument,
  JobAnalysisApiError,
} from "@/shared/api/jobAnalysisApi";
import {
  cacheConsultantSnapshot,
  refreshConsultantQueries,
} from "@/shared/query/jobAnalysisQueries";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { toApprovedDocumentWrite } from "./consultantWorkspaceModel";
import { CurrentDocumentOutline } from "./CurrentDocumentOutline";

type OpksDraft = ApprovedJobDocumentWrite["opks"][number];
type DocumentDraftState = {
  draft: ApprovedJobDocumentWrite;
  baselineRevision: number;
  baselineWorkspaceGeneration: number;
  baselineWorkspaceDigest: string;
};

const DRAFT_STORAGE_VERSION = 2;

function draftStorageKey(documentId: string): string {
  return `caliburn:consultant-document-draft:${documentId}`;
}

function readStoredDraft(documentId: string): DocumentDraftState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(draftStorageKey(documentId));
    if (!raw) return null;
    const value = JSON.parse(raw) as {
      version?: unknown;
      baselineRevision?: unknown;
      baselineWorkspaceGeneration?: unknown;
      baselineWorkspaceDigest?: unknown;
      draft?: unknown;
    };
    if (
      value.version !== DRAFT_STORAGE_VERSION ||
      !Number.isInteger(value.baselineRevision) ||
      !Number.isInteger(value.baselineWorkspaceGeneration) ||
      typeof value.baselineWorkspaceDigest !== "string" ||
      typeof value.draft !== "object" ||
      value.draft === null
    ) {
      window.localStorage.removeItem(draftStorageKey(documentId));
      return null;
    }
    const draft = value.draft as Partial<ApprovedJobDocumentWrite>;
    if (
      draft.document_id !== documentId ||
      !Array.isArray(draft.duties) ||
      !Array.isArray(draft.tasks) ||
      !Array.isArray(draft.opks)
    ) {
      window.localStorage.removeItem(draftStorageKey(documentId));
      return null;
    }
    return {
      draft: draft as ApprovedJobDocumentWrite,
      baselineRevision: value.baselineRevision as number,
      baselineWorkspaceGeneration: value.baselineWorkspaceGeneration as number,
      baselineWorkspaceDigest: value.baselineWorkspaceDigest,
    };
  } catch {
    window.localStorage.removeItem(draftStorageKey(documentId));
    return null;
  }
}

function optionalText(value: string | null): string | null {
  const normalized = value?.trim() ?? "";
  return normalized || null;
}

function normalizedDocument(
  value: ApprovedJobDocumentWrite,
): ApprovedJobDocumentWrite {
  const opksOrder = new Map<OpksDraft["kind"], number>();
  return {
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
      const displayOrder = opksOrder.get(item.kind) ?? 0;
      opksOrder.set(item.kind, displayOrder + 1);
      return {
        ...item,
        text: item.text.trim(),
        display_order: displayOrder,
      };
    }),
  };
}

function errorText(error: unknown): string {
  if (error instanceof JobAnalysisApiError && error.status === 409) {
    return "目前 JD 已在背景更新";
  }
  return error instanceof JobAnalysisApiError
    ? error.message
    : "目前 JD 無法儲存，請稍後再試";
}

function TextField({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: string | null;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  const className =
    "mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-stone-500";
  return (
    <label className="block text-xs font-medium text-stone-600">
      {label}
      {multiline ? (
        <textarea
          aria-label={label}
          className={`${className} min-h-24 leading-6`}
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : (
        <input
          aria-label={label}
          className={className}
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  );
}

export function CurrentDocumentEditor({
  documentId,
  snapshot,
  onDirtyChange,
}: {
  documentId: string;
  snapshot: ConsultantSnapshotView;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [draftState, setDraftState] = useState<DocumentDraftState | null>(() =>
    readStoredDraft(documentId),
  );
  const [serverConflict, setServerConflict] = useState(false);
  const currentDocument = snapshot.current_document;
  const workspaceGeneration = snapshot.document_review.workspace_generation;
  const workspaceDigest = snapshot.document_review.workspace_digest;
  const draft = draftState?.draft ?? toApprovedDocumentWrite(currentDocument);
  const baselineRevision = draftState?.baselineRevision ?? snapshot.revision;
  const baselineWorkspaceGeneration =
    draftState?.baselineWorkspaceGeneration ?? workspaceGeneration;
  const baselineWorkspaceDigest =
    draftState?.baselineWorkspaceDigest ?? workspaceDigest;
  const dirty = draftState !== null;
  const conflict =
    dirty && (serverConflict || snapshot.revision > baselineRevision);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (draftState === null) {
      window.localStorage.removeItem(draftStorageKey(documentId));
      return;
    }
    window.localStorage.setItem(
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
      workspaceGeneration: number;
      workspaceDigest: string;
    }) =>
      editCurrentDocument(
        documentId,
        operation.idempotencyKey,
        operation.expectedRevision,
        operation.workspaceGeneration,
        operation.workspaceDigest,
        operation.document,
      ),
    onSuccess: async (result) => {
      cacheConsultantSnapshot(queryClient, documentId, result);
      setDraftState(null);
      setServerConflict(false);
      await refreshConsultantQueries(queryClient, documentId);
    },
    onError: async (error) => {
      if (error instanceof JobAnalysisApiError && error.status === 409) {
        setServerConflict(true);
        await refreshConsultantQueries(queryClient, documentId);
      }
    },
  });

  const change = (
    update: (document: ApprovedJobDocumentWrite) => ApprovedJobDocumentWrite,
  ) => {
    setServerConflict(false);
    setDraftState((current) => ({
      draft: update(current?.draft ?? toApprovedDocumentWrite(currentDocument)),
      baselineRevision: current?.baselineRevision ?? snapshot.revision,
      baselineWorkspaceGeneration:
        current?.baselineWorkspaceGeneration ?? workspaceGeneration,
      baselineWorkspaceDigest:
        current?.baselineWorkspaceDigest ?? workspaceDigest,
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
  ) => change((document) => ({ ...document, [field]: value }));

  const save = () => {
    const document = normalizedDocument(draft);
    if (!dirty || conflict || mutation.isPending) return;
    const previous = mutation.variables;
    const retry =
      mutation.isError &&
      previous?.expectedRevision === baselineRevision &&
      previous.workspaceGeneration === baselineWorkspaceGeneration &&
      previous.workspaceDigest === baselineWorkspaceDigest &&
      JSON.stringify(previous.document) === JSON.stringify(document);
    mutation.mutate(
      retry
        ? previous
        : {
            document,
            expectedRevision: baselineRevision,
            workspaceGeneration: baselineWorkspaceGeneration,
            workspaceDigest: baselineWorkspaceDigest,
            idempotencyKey: crypto.randomUUID(),
          },
    );
  };

  const reload = () => {
    setDraftState(null);
    setServerConflict(false);
    mutation.reset();
    void refreshConsultantQueries(queryClient, documentId);
  };

  return (
    <section aria-label="目前 JD 編輯器" className="space-y-5">
      <Card className="border-stone-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.16em] text-stone-500 uppercase">
              唯一主要工作面
            </p>
            <h2 className="mt-1 text-2xl font-semibold">目前 JD</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-stone-600">
              這裡是你與顧問共同延續的目前成果。AI 變更在接受前仍不會進入匯出版本。
            </p>
          </div>
          <div className="rounded-full bg-stone-100 px-3 py-1.5 text-xs text-stone-600">
            待審 AI 變更 {snapshot.document_review.unresolved_action_count} 項
          </div>
        </div>

        <div className="mt-6 grid gap-4 border-t border-stone-100 pt-5 sm:grid-cols-2">
          <TextField
            label="職務名稱"
            value={draft.job_title}
            onChange={(value) => patchHeader("job_title", value)}
          />
          <TextField
            label="職類名稱"
            value={draft.occupation_category_name}
            onChange={(value) => patchHeader("occupation_category_name", value)}
          />
          <TextField
            label="職業名稱"
            value={draft.occupation_name}
            onChange={(value) => patchHeader("occupation_name", value)}
          />
          <TextField
            label="職業分類代碼"
            value={draft.occupation_code}
            onChange={(value) => patchHeader("occupation_code", value)}
          />
          <TextField
            label="行業名稱"
            value={draft.industry_name}
            onChange={(value) => patchHeader("industry_name", value)}
          />
          <TextField
            label="行業分類代碼"
            value={draft.industry_code}
            onChange={(value) => patchHeader("industry_code", value)}
          />
          <div className="sm:col-span-2">
            <TextField
              label="工作描述"
              value={draft.work_description}
              onChange={(value) => patchHeader("work_description", value)}
              multiline
            />
          </div>
          <div className="sm:col-span-2">
            <TextField
              label="備註"
              value={draft.notes}
              onChange={(value) => patchHeader("notes", value)}
              multiline
            />
          </div>
        </div>

        <div className="mt-6 border-t border-stone-100 pt-5">
          <CurrentDocumentOutline document={draft} onChange={change} />
        </div>

        {dirty ? (
          <p className="mt-5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-950">
            若你修改的是待審 AI 內容，儲存會把你實際修改的部分與維持該內容完整所需的關聯一起視為修改後接受；其他待審變更不受影響。實際範圍由伺服器依目前 JD 計算，畫面不自行猜測。
          </p>
        ) : null}

        {conflict ? (
          <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <div>
                <p className="font-semibold">目前 JD 已在背景更新</p>
                <p className="mt-1 leading-6">
                  為避免覆蓋你的輸入，草稿仍保留在這裡。重新載入後可從最新內容重新編輯。
                </p>
              </div>
            </div>
            <Button className="mt-3" variant="outline" onClick={reload}>
              重新載入並捨棄草稿
            </Button>
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-stone-100 pt-4">
          <p className="text-xs text-stone-500">
            {dirty ? "有未儲存的員工修改" : "目前 JD 已同步"}
          </p>
          <div className="flex gap-2">
            {dirty ? (
              <Button variant="ghost" onClick={reload}>
                取消修改
              </Button>
            ) : null}
            <Button disabled={!dirty || conflict || mutation.isPending} onClick={save}>
              <Save />
              {mutation.isPending ? "儲存中…" : "儲存目前 JD"}
            </Button>
          </div>
        </div>

        {mutation.isError ? (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {errorText(mutation.error)}；草稿仍保留。
          </p>
        ) : null}
      </Card>
    </section>
  );
}
