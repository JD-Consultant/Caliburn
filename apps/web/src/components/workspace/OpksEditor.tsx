"use client";

import type {
  OpksItemView,
  OpksItemWrite,
} from "@caliburn/job-analysis-contract";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  addOpksItem,
  deleteOpksItem,
  editOpksItem,
  generateOpksProposals,
  JobAnalysisApiError,
} from "@/lib/jobAnalysisApi";
import {
  documentAttitudes,
  documentUnlinkedCompetencies,
  groupOpksByTask,
} from "@/lib/jobAnalysisOpks";
import {
  documentQueryOptions,
  jobAnalysisInvalidationKeys,
} from "@/lib/jobAnalysisQueries";
import { OpksItemForm } from "./OpksItemForm";
import { UnsavedChangesGuard } from "./UnsavedChangesGuard";

type ItemKind = OpksItemView["entity_kind"];
type GeneratedKind = Exclude<ItemKind, "attitude">;

const KIND_LABELS: Record<ItemKind, string> = {
  output: "工作產出",
  indicator: "行為指標",
  knowledge: "知識",
  skill: "技能",
  attitude: "態度",
};

const TASK_KINDS: GeneratedKind[] = [
  "output",
  "indicator",
  "knowledge",
  "skill",
];

type Editing = {
  mode: "add" | "edit";
  kind: ItemKind;
  taskId?: string;
  item?: OpksItemView;
  baseline: string;
  draft: string;
};

type SaveVariables = {
  mode: "add" | "edit";
  entityId?: string;
  value: OpksItemWrite;
  idempotencyKey: string;
};

function errorText(error: unknown) {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "操作失敗，請稍後再試";
}

export function OpksEditor({
  documentId,
  onDirtyChange,
}: {
  documentId: string;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const document = useQuery(documentQueryOptions(documentId));
  const [editing, setEditing] = useState<Editing | null>(null);

  const invalidate = async () => {
    await Promise.all(
      jobAnalysisInvalidationKeys(documentId).map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    );
  };

  const saveMutation = useMutation({
    mutationFn: (variables: SaveVariables) =>
      variables.mode === "add"
        ? addOpksItem(documentId, variables.value, variables.idempotencyKey)
        : editOpksItem(
            documentId,
            variables.entityId!,
            variables.value,
            variables.idempotencyKey,
          ),
    onSuccess: async () => {
      await invalidate();
      setEditing(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (variables: { entityId: string; idempotencyKey: string }) =>
      deleteOpksItem(documentId, variables.entityId, variables.idempotencyKey),
    onSuccess: invalidate,
  });

  const generationMutation = useMutation({
    mutationFn: (variables: { taskId: string; idempotencyKey: string }) =>
      generateOpksProposals(
        documentId,
        variables.taskId,
        variables.idempotencyKey,
      ),
    onSuccess: invalidate,
  });

  const dirty = Boolean(editing && editing.draft !== editing.baseline);
  useEffect(() => {
    onDirtyChange?.(dirty);
    return () => onDirtyChange?.(false);
  }, [dirty, onDirtyChange]);

  const startAdd = (kind: ItemKind, taskId?: string) => {
    saveMutation.reset();
    setEditing({ mode: "add", kind, taskId, baseline: "", draft: "" });
  };

  const startEdit = (item: OpksItemView, taskId?: string) => {
    saveMutation.reset();
    setEditing({
      mode: "edit",
      kind: item.entity_kind,
      taskId,
      item,
      baseline: item.text,
      draft: item.text,
    });
  };

  const cancel = () => {
    if (dirty && !window.confirm("放棄尚未儲存的變更嗎？")) return;
    setEditing(null);
    saveMutation.reset();
  };

  const save = () => {
    if (!editing?.draft.trim() || !dirty) return;
    const value: OpksItemWrite = {
      entity_kind: editing.kind,
      text: editing.draft.trim(),
      task_refs: editing.item
        ? editing.item.task_refs
        : editing.kind === "attitude"
          ? []
          : [editing.taskId!],
      indicator_refs: editing.item?.indicator_refs ?? [],
    };
    const previous = saveMutation.variables;
    const sameFailedOperation =
      saveMutation.isError &&
      previous?.mode === editing.mode &&
      previous.entityId === editing.item?.entity_id &&
      JSON.stringify(previous.value) === JSON.stringify(value);
    saveMutation.mutate(
      sameFailedOperation
        ? previous
        : {
            mode: editing.mode,
            entityId: editing.item?.entity_id,
            value,
            idempotencyKey: crypto.randomUUID(),
          },
    );
  };

  const remove = (item: OpksItemView) => {
    const shared =
      (item.entity_kind === "knowledge" || item.entity_kind === "skill") &&
      item.task_refs.length > 1;
    const message = shared
      ? "這一筆也連到其他工作；刪除會從整份文件移除。確定刪除嗎？"
      : "確定刪除這一筆職務內容嗎？";
    if (!window.confirm(message)) return;
    const previous = deleteMutation.variables;
    deleteMutation.mutate(
      deleteMutation.isError && previous?.entityId === item.entity_id
        ? previous
        : { entityId: item.entity_id, idempotencyKey: crypto.randomUUID() },
    );
  };

  const generate = (taskId: string) => {
    const previous = generationMutation.variables;
    generationMutation.mutate(
      generationMutation.isError && previous?.taskId === taskId
        ? previous
        : { taskId, idempotencyKey: crypto.randomUUID() },
    );
  };

  if (document.isPending) {
    return <p className="text-sm text-muted-foreground">正在讀取工作內容…</p>;
  }
  if (document.isError || !document.data) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {errorText(document.error)}
      </p>
    );
  }

  const groups = groupOpksByTask(document.data.tasks, document.data.opks_items);
  const attitudes = documentAttitudes(document.data.opks_items);
  const unlinkedCompetencies = documentUnlinkedCompetencies(
    document.data.opks_items,
  );
  const busy =
    saveMutation.isPending ||
    deleteMutation.isPending ||
    generationMutation.isPending;

  const formFor = (kind: ItemKind, taskId?: string, item?: OpksItemView) => {
    const matches =
      editing?.kind === kind &&
      editing.taskId === taskId &&
      (item
        ? editing.mode === "edit" && editing.item?.entity_id === item.entity_id
        : editing.mode === "add");
    if (!matches || !editing) return null;
    return (
      <OpksItemForm
        label={KIND_LABELS[kind]}
        value={editing.draft}
        onChange={(draft) => setEditing({ ...editing, draft })}
        onSave={save}
        onCancel={cancel}
        isSaving={saveMutation.isPending}
        error={saveMutation.isError ? errorText(saveMutation.error) : undefined}
      />
    );
  };

  return (
    <section className="space-y-4" aria-label="工作產出與職能內容">
      <UnsavedChangesGuard dirty={dirty} />
      <div>
        <h2 className="text-lg font-semibold">工作產出與職能內容</h2>
        <p className="text-sm text-muted-foreground">
          可自行編輯；AI 只會先提出建議，不會直接改入文件。
        </p>
      </div>

      {groups.map(({ task, items }) => (
        <Card key={task.task_id} className="space-y-4 p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="font-semibold">{task.statement}</h3>
              <p className="text-xs text-muted-foreground">這項工作的 O/P/K/S</p>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={busy || editing !== null}
              onClick={() => generate(task.task_id)}
            >
              <Sparkles />
              {generationMutation.isPending &&
              generationMutation.variables?.taskId === task.task_id
                ? "產生中…"
                : "產生建議"}
            </Button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {TASK_KINDS.map((kind) => {
              const values = items.filter((item) => item.entity_kind === kind);
              return (
                <div key={kind} className="space-y-2 rounded-lg border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-medium">{KIND_LABELS[kind]}</h4>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`新增${KIND_LABELS[kind]}`}
                      disabled={busy || editing !== null}
                      onClick={() => startAdd(kind, task.task_id)}
                    >
                      <Plus />
                    </Button>
                  </div>
                  {values.length === 0 ? (
                    <p className="text-sm text-muted-foreground">尚未填寫</p>
                  ) : (
                    <ul className="space-y-2">
                      {values.map((item) => (
                        <li key={item.entity_id} className="space-y-2">
                          <div className="flex items-start gap-2 text-sm">
                            <span className="min-w-0 flex-1">{item.text}</span>
                            <Button
                              size="icon"
                              variant="ghost"
                              aria-label={`編輯${KIND_LABELS[kind]}`}
                              disabled={busy || editing !== null}
                              onClick={() => startEdit(item, task.task_id)}
                            >
                              <Pencil />
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              aria-label={`刪除${KIND_LABELS[kind]}`}
                              disabled={busy || editing !== null}
                              onClick={() => remove(item)}
                            >
                              <Trash2 />
                            </Button>
                          </div>
                          {formFor(kind, task.task_id, item)}
                        </li>
                      ))}
                    </ul>
                  )}
                  {formFor(kind, task.task_id)}
                </div>
              );
            })}
          </div>

          {generationMutation.isSuccess &&
          generationMutation.variables?.taskId === task.task_id ? (
            <p role="status" className="text-sm text-muted-foreground">
              {generationMutation.data.outcome === "proposed"
                ? `已建立 ${generationMutation.data.proposal_ids.length} 項待確認建議。`
                : "目前沒有足夠依據產生新建議。"}
            </p>
          ) : null}
          {generationMutation.isError &&
          generationMutation.variables?.taskId === task.task_id ? (
            <p role="alert" className="text-sm text-destructive">
              {errorText(generationMutation.error)}
            </p>
          ) : null}
        </Card>
      ))}

      {unlinkedCompetencies.length ? (
        <Card className="space-y-3 p-5">
          <div>
            <h3 className="font-semibold">尚未連結的知識與技能</h3>
            <p className="text-xs text-muted-foreground">
              原工作被移除後仍保留在文件層；可修改或刪除。
            </p>
          </div>
          <ul className="space-y-2">
            {unlinkedCompetencies.map((item) => (
              <li key={item.entity_id} className="space-y-2">
                <div className="flex items-start gap-2 text-sm">
                  <span className="min-w-0 flex-1">
                    {KIND_LABELS[item.entity_kind]}：{item.text}
                  </span>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`編輯${KIND_LABELS[item.entity_kind]}`}
                    disabled={busy || editing !== null}
                    onClick={() => startEdit(item)}
                  >
                    <Pencil />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`刪除${KIND_LABELS[item.entity_kind]}`}
                    disabled={busy || editing !== null}
                    onClick={() => remove(item)}
                  >
                    <Trash2 />
                  </Button>
                </div>
                {formFor(item.entity_kind, undefined, item)}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card className="space-y-3 p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold">文件層態度</h3>
            <p className="text-xs text-muted-foreground">
              第一版只由你手動填寫，AI 不會自動產生。
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            disabled={busy || editing !== null}
            onClick={() => startAdd("attitude")}
          >
            <Plus />
            新增態度
          </Button>
        </div>
        {attitudes.length === 0 ? (
          <p className="text-sm text-muted-foreground">尚未填寫</p>
        ) : (
          <ul className="space-y-2">
            {attitudes.map((item) => (
              <li key={item.entity_id} className="space-y-2">
                <div className="flex items-start gap-2 text-sm">
                  <span className="min-w-0 flex-1">{item.text}</span>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label="編輯態度"
                    disabled={busy || editing !== null}
                    onClick={() => startEdit(item)}
                  >
                    <Pencil />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label="刪除態度"
                    disabled={busy || editing !== null}
                    onClick={() => remove(item)}
                  >
                    <Trash2 />
                  </Button>
                </div>
                {formFor("attitude", undefined, item)}
              </li>
            ))}
          </ul>
        )}
        {formFor("attitude")}
      </Card>

      {deleteMutation.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {errorText(deleteMutation.error)}
        </p>
      ) : null}
    </section>
  );
}
