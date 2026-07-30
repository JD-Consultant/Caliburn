"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowLeft, ArrowUp, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  addTask,
  deleteTask,
  editTask,
  JobAnalysisApiError,
  reorderTasks,
} from "@/lib/jobAnalysisApi";
import {
  emptyTaskForm,
  fromTaskView,
  isTaskFormDirty,
  type TaskFormValue,
  toTaskWrite,
} from "@/lib/jobAnalysisForm";
import {
  documentQueryOptions,
  jobAnalysisInvalidationKeys,
} from "@/lib/jobAnalysisQueries";
import { TaskForm } from "./TaskForm";
import { GuardedLink, UnsavedChangesGuard } from "./UnsavedChangesGuard";

type SaveVariables = {
  mode: "add" | "edit";
  taskId?: string;
  value: ReturnType<typeof toTaskWrite>;
  idempotencyKey: string;
};

function errorText(error: unknown) {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "操作失敗，請稍後再試";
}

export function TaskEditor({
  documentId,
  embedded = false,
  onDirtyChange,
}: {
  documentId: string;
  embedded?: boolean;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const document = useQuery(documentQueryOptions(documentId));
  const [editingTaskId, setEditingTaskId] = useState<string | "new" | null>(null);
  const [baseline, setBaseline] = useState<TaskFormValue | null>(null);
  const [draft, setDraft] = useState<TaskFormValue | null>(null);

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
        ? addTask(documentId, variables.value, variables.idempotencyKey)
        : editTask(
            documentId,
            variables.taskId!,
            variables.value,
            variables.idempotencyKey,
          ),
    onSuccess: async () => {
      await invalidate();
      setEditingTaskId(null);
      setBaseline(null);
      setDraft(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (variables: { taskId: string; idempotencyKey: string }) =>
      deleteTask(documentId, variables.taskId, variables.idempotencyKey),
    onSuccess: invalidate,
  });

  const reorderMutation = useMutation({
    mutationFn: (variables: { orderedTaskIds: string[]; idempotencyKey: string }) =>
      reorderTasks(documentId, variables.orderedTaskIds, variables.idempotencyKey),
    onSuccess: invalidate,
  });

  const dirty = Boolean(
    baseline && draft && isTaskFormDirty(baseline, draft),
  );

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  const startNew = () => {
    saveMutation.reset();
    const value = emptyTaskForm();
    setEditingTaskId("new");
    setBaseline(value);
    setDraft(value);
  };
  const startEdit = (taskId: string) => {
    const task = document.data?.tasks.find((item) => item.task_id === taskId);
    if (!task) return;
    saveMutation.reset();
    const value = fromTaskView(task);
    setEditingTaskId(taskId);
    setBaseline(value);
    setDraft(value);
  };
  const cancel = () => {
    if (dirty && !window.confirm("放棄尚未儲存的變更嗎？")) return;
    setEditingTaskId(null);
    setBaseline(null);
    setDraft(null);
    saveMutation.reset();
  };
  const save = () => {
    if (!draft || !draft.statement.trim() || !dirty) return;
    const value = toTaskWrite(draft);
    const mode = editingTaskId === "new" ? "add" : "edit";
    const taskId = mode === "edit" ? editingTaskId ?? undefined : undefined;
    const previous = saveMutation.variables;
    const sameFailedOperation =
      saveMutation.isError &&
      previous?.mode === mode &&
      previous.taskId === taskId &&
      JSON.stringify(previous.value) === JSON.stringify(value);
    saveMutation.mutate(
      sameFailedOperation
        ? previous
        : { mode, taskId, value, idempotencyKey: crypto.randomUUID() },
    );
  };

  const remove = (taskId: string) => {
    if (!window.confirm("確定刪除這項工作嗎？")) return;
    const previous = deleteMutation.variables;
    deleteMutation.mutate(
      deleteMutation.isError && previous?.taskId === taskId
        ? previous
        : { taskId, idempotencyKey: crypto.randomUUID() },
    );
  };

  const move = (index: number, offset: -1 | 1) => {
    if (!document.data) return;
    const next = [...document.data.tasks];
    const target = index + offset;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    const orderedTaskIds = next.map((task) => task.task_id);
    const previous = reorderMutation.variables;
    reorderMutation.mutate(
      reorderMutation.isError &&
        JSON.stringify(previous?.orderedTaskIds) === JSON.stringify(orderedTaskIds)
        ? previous!
        : { orderedTaskIds, idempotencyKey: crypto.randomUUID() },
    );
  };

  if (document.isPending) {
    return <p className="p-8 text-sm text-muted-foreground">正在讀取文件…</p>;
  }
  if (document.isError || !document.data) {
    return (
      <p className="p-8 text-sm text-destructive" role="alert">
        {errorText(document.error)}
      </p>
    );
  }

  const busy =
    saveMutation.isPending || deleteMutation.isPending || reorderMutation.isPending;

  return (
    <div className={embedded ? "" : "min-h-screen bg-muted/30"}>
      <UnsavedChangesGuard dirty={dirty} />
      {!embedded ? <header className="border-b bg-background">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-6 py-5">
          <GuardedLink
            dirty={dirty}
            href="/workspace"
            className="rounded-lg p-2 hover:bg-muted"
            aria-label="返回文件庫"
          >
            <ArrowLeft />
          </GuardedLink>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-xl font-semibold">{document.data.title}</h1>
            <p className="text-xs text-muted-foreground">
              {document.data.tasks.length} 項工作
            </p>
          </div>
          <Button disabled={busy || editingTaskId !== null} onClick={startNew}>
            <Plus />
            新增工作
          </Button>
        </div>
      </header> : (
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">目前文件</h2>
            <p className="text-sm text-muted-foreground">
              {document.data.tasks.length} 項工作；可直接新增或修改。
            </p>
          </div>
          <Button disabled={busy || editingTaskId !== null} onClick={startNew}>
            <Plus />
            新增工作
          </Button>
        </div>
      )}

      <main className={embedded ? "space-y-4" : "mx-auto max-w-5xl space-y-4 px-6 py-8"}>
        {editingTaskId === "new" && draft ? (
          <Card className="p-5">
            <h2 className="text-base font-semibold">新增工作</h2>
            <TaskForm
              value={draft}
              onChange={setDraft}
              onSave={save}
              onCancel={cancel}
              isSaving={saveMutation.isPending}
              canSave={dirty}
              error={saveMutation.isError ? errorText(saveMutation.error) : undefined}
            />
          </Card>
        ) : null}

        {document.data.tasks.length === 0 && editingTaskId !== "new" ? (
          <div className="rounded-xl border border-dashed px-6 py-14 text-center">
            <p className="font-medium">尚未加入工作</p>
            <p className="mt-1 text-sm text-muted-foreground">
              只知道工作名稱也可以先新增，細節之後再補。
            </p>
          </div>
        ) : null}

        {document.data.tasks.map((task, index) => (
          <Card key={task.task_id} className="p-5">
            {editingTaskId === task.task_id && draft ? (
              <TaskForm
                value={draft}
                onChange={setDraft}
                onSave={save}
                onCancel={cancel}
                isSaving={saveMutation.isPending}
                canSave={dirty}
                error={saveMutation.isError ? errorText(saveMutation.error) : undefined}
              />
            ) : (
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <h2 className="text-base font-semibold">{task.statement}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {task.purpose_result ?? "目的／結果尚未填寫"}
                    </p>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="上移"
                      disabled={busy || index === 0 || editingTaskId !== null}
                      onClick={() => move(index, -1)}
                    >
                      <ArrowUp />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="下移"
                      disabled={
                        busy ||
                        index === document.data.tasks.length - 1 ||
                        editingTaskId !== null
                      }
                      onClick={() => move(index, 1)}
                    >
                      <ArrowDown />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="編輯工作"
                      disabled={busy || editingTaskId !== null}
                      onClick={() => startEdit(task.task_id)}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="刪除工作"
                      disabled={busy || editingTaskId !== null}
                      onClick={() => remove(task.task_id)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>
                <dl className="grid gap-3 text-sm sm:grid-cols-3">
                  <div>
                    <dt className="text-xs text-muted-foreground">情境／條件</dt>
                    <dd>{task.context ?? "尚未填寫"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">頻率</dt>
                    <dd>{task.frequency_text ?? "尚未填寫"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">責任角色</dt>
                    <dd>
                      {task.responsibility_role === "primary"
                        ? "主要負責"
                        : task.responsibility_role === "shared"
                          ? "共同負責"
                          : task.responsibility_role === "assist"
                            ? "協助"
                            : "尚未填寫"}
                    </dd>
                  </div>
                </dl>
                <div className="text-sm">
                  <p className="text-xs text-muted-foreground">工具／方法／知識／技能</p>
                  <p>
                    {task.enablers.length
                      ? task.enablers.map((item) => item.name).join("、")
                      : "尚未填寫"}
                  </p>
                </div>
              </div>
            )}
          </Card>
        ))}

        <div aria-live="polite" className="min-h-5 text-sm text-destructive">
          {deleteMutation.isError
            ? errorText(deleteMutation.error)
            : reorderMutation.isError
              ? errorText(reorderMutation.error)
              : undefined}
        </div>
      </main>
    </div>
  );
}
