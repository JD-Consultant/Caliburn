"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowLeft, ArrowUp, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  addDuty,
  deleteDuty,
  editDuty,
  JobAnalysisApiError,
  reorderDuties,
} from "@/lib/jobAnalysisApi";
import {
  emptyDutyForm,
  fromDutyView,
  isDutyFormDirty,
  toDutyOrderWrite,
  toDutyWrite,
  type DutyFormValue,
} from "@/lib/jobAnalysisDuties";
import {
  documentQueryOptions,
  jobAnalysisInvalidationKeys,
} from "@/lib/jobAnalysisQueries";
import { GuardedLink, UnsavedChangesGuard } from "./UnsavedChangesGuard";

type SaveVariables = {
  mode: "add" | "edit";
  dutyId?: string;
  value: ReturnType<typeof toDutyWrite>;
  idempotencyKey: string;
};

function errorText(error: unknown) {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "操作失敗，請稍後再試";
}

export function DutyEditor({
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
  const [editingDutyId, setEditingDutyId] = useState<string | "new" | null>(null);
  const [baseline, setBaseline] = useState<DutyFormValue | null>(null);
  const [draft, setDraft] = useState<DutyFormValue | null>(null);

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
        ? addDuty(documentId, variables.value, variables.idempotencyKey)
        : editDuty(
            documentId,
            variables.dutyId!,
            variables.value,
            variables.idempotencyKey,
          ),
    onSuccess: async () => {
      await invalidate();
      setEditingDutyId(null);
      setBaseline(null);
      setDraft(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (variables: { dutyId: string; idempotencyKey: string }) =>
      deleteDuty(documentId, variables.dutyId, variables.idempotencyKey),
    onSuccess: invalidate,
  });

  const reorderMutation = useMutation({
    mutationFn: (variables: { dutyIds: string[]; idempotencyKey: string }) =>
      reorderDuties(documentId, variables.dutyIds, variables.idempotencyKey),
    onSuccess: invalidate,
  });

  const dirty = Boolean(
    baseline && draft && isDutyFormDirty(baseline, draft),
  );

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  const startNew = () => {
    saveMutation.reset();
    const value = emptyDutyForm();
    setEditingDutyId("new");
    setBaseline(value);
    setDraft(value);
  };

  const startEdit = (dutyId: string) => {
    const duty = document.data?.duties.find((item) => item.duty_id === dutyId);
    if (!duty) return;
    saveMutation.reset();
    const value = fromDutyView(duty);
    setEditingDutyId(dutyId);
    setBaseline(value);
    setDraft(value);
  };

  const cancel = () => {
    if (dirty && !window.confirm("放棄尚未儲存的變更嗎？")) return;
    setEditingDutyId(null);
    setBaseline(null);
    setDraft(null);
    saveMutation.reset();
  };

  const save = () => {
    if (!draft || !draft.statement.trim() || !dirty) return;
    const value = toDutyWrite(draft);
    const mode = editingDutyId === "new" ? "add" : "edit";
    const dutyId = mode === "edit" ? editingDutyId ?? undefined : undefined;
    const previous = saveMutation.variables;
    const sameFailedOperation =
      saveMutation.isError &&
      previous?.mode === mode &&
      previous.dutyId === dutyId &&
      JSON.stringify(previous.value) === JSON.stringify(value);
    saveMutation.mutate(
      sameFailedOperation
        ? previous
        : { mode, dutyId, value, idempotencyKey: crypto.randomUUID() },
    );
  };

  const remove = (dutyId: string) => {
    if (!window.confirm("刪除主要職責後，所屬工作會保留但變成未分組。確定嗎？")) {
      return;
    }
    const previous = deleteMutation.variables;
    deleteMutation.mutate(
      deleteMutation.isError && previous?.dutyId === dutyId
        ? previous
        : { dutyId, idempotencyKey: crypto.randomUUID() },
    );
  };

  const move = (index: number, offset: -1 | 1) => {
    if (!document.data) return;
    const duties = [...document.data.duties];
    const target = index + offset;
    if (target < 0 || target >= duties.length) return;
    [duties[index], duties[target]] = [duties[target], duties[index]];
    const body = toDutyOrderWrite(duties);
    const previous = reorderMutation.variables;
    reorderMutation.mutate(
      reorderMutation.isError &&
        JSON.stringify(previous?.dutyIds) ===
          JSON.stringify(body.ordered_duty_ids)
        ? previous!
        : {
            dutyIds: body.ordered_duty_ids,
            idempotencyKey: crypto.randomUUID(),
          },
    );
  };

  if (document.isPending) {
    return <p className="text-sm text-muted-foreground">正在讀取主要職責…</p>;
  }
  if (document.isError || !document.data) {
    return (
      <p className="text-sm text-destructive" role="alert">
        {errorText(document.error)}
      </p>
    );
  }

  const busy =
    saveMutation.isPending || deleteMutation.isPending || reorderMutation.isPending;
  const duties = document.data.duties;

  return (
    <div className={embedded ? "" : "min-h-screen bg-muted/30"}>
      <UnsavedChangesGuard dirty={dirty} />
      {!embedded ? (
        <header className="border-b bg-background">
          <div className="mx-auto flex max-w-5xl items-center gap-4 px-6 py-5">
            <GuardedLink
              dirty={dirty}
              href="/workspace"
              className="rounded-lg p-2 hover:bg-muted"
              aria-label="返回文件庫"
            >
              <ArrowLeft />
            </GuardedLink>
            <h1 className="min-w-0 flex-1 truncate text-xl font-semibold">
              主要職責
            </h1>
            <Button disabled={busy || editingDutyId !== null} onClick={startNew}>
              <Plus />
              新增主要職責
            </Button>
          </div>
        </header>
      ) : (
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">主要職責</h2>
            <p className="text-sm text-muted-foreground">
              由員工建立與調整；不會由 AI 自動套用。
            </p>
          </div>
          <Button disabled={busy || editingDutyId !== null} onClick={startNew}>
            <Plus />
            新增主要職責
          </Button>
        </div>
      )}

      <main className={embedded ? "space-y-3" : "mx-auto max-w-5xl space-y-3 px-6 py-8"}>
        {editingDutyId === "new" && draft ? (
          <Card className="p-5">
            <h3 className="mb-3 text-base font-semibold">新增主要職責</h3>
            <DutyForm
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

        {duties.map((duty, index) => (
          <Card key={duty.duty_id} className="p-4">
            {editingDutyId === duty.duty_id && draft ? (
              <DutyForm
                value={draft}
                onChange={setDraft}
                onSave={save}
                onCancel={cancel}
                isSaving={saveMutation.isPending}
                canSave={dirty}
                error={saveMutation.isError ? errorText(saveMutation.error) : undefined}
              />
            ) : (
              <div className="flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground">主要職責 {index + 1}</p>
                  <h3 className="font-medium">{duty.statement}</h3>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="主要職責上移"
                  disabled={busy || index === 0 || editingDutyId !== null}
                  onClick={() => move(index, -1)}
                >
                  <ArrowUp />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="主要職責下移"
                  disabled={busy || index === duties.length - 1 || editingDutyId !== null}
                  onClick={() => move(index, 1)}
                >
                  <ArrowDown />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="編輯主要職責"
                  disabled={busy || editingDutyId !== null}
                  onClick={() => startEdit(duty.duty_id)}
                >
                  <Pencil />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="刪除主要職責"
                  disabled={busy || editingDutyId !== null}
                  onClick={() => remove(duty.duty_id)}
                >
                  <Trash2 />
                </Button>
              </div>
            )}
          </Card>
        ))}

        {!duties.length ? (
          <div className="rounded-xl border border-dashed px-6 py-8 text-center">
            <p className="font-medium">尚未建立主要職責</p>
            <p className="mt-1 text-sm text-muted-foreground">
              可先保留工作未分組，之後由員工建立主要職責。
            </p>
          </div>
        ) : null}

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

function DutyForm({
  value,
  onChange,
  onSave,
  onCancel,
  isSaving,
  canSave,
  error,
}: {
  value: DutyFormValue;
  onChange: (value: DutyFormValue) => void;
  onSave: () => void;
  onCancel: () => void;
  isSaving: boolean;
  canSave: boolean;
  error?: string;
}) {
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
          event.preventDefault();
          onSave();
        } else if (event.key === "Escape") {
          event.preventDefault();
          onCancel();
        }
      }}
    >
      <label className="block space-y-1.5">
        <span className="text-sm font-medium">主要職責敘述</span>
        <textarea
          className="min-h-20 w-full rounded-lg border bg-background px-3 py-2 text-sm"
          value={value.statement}
          onChange={(event) => onChange({ statement: event.target.value })}
          placeholder="例如：維持門市日常營運"
          autoFocus
        />
      </label>
      <div aria-live="polite" className="min-h-5 text-sm text-destructive">
        {error}
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={!value.statement.trim() || !canSave || isSaving}>
          {isSaving ? "儲存中…" : "儲存"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          取消
        </Button>
        <span className="self-center text-xs text-muted-foreground">
          Ctrl/Cmd+Enter 儲存 · Esc 取消
        </span>
      </div>
    </form>
  );
}
