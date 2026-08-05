"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Check, Pencil, Plus, Trash2, X } from "lucide-react";
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
  documentQueryOptions,
  jobAnalysisInvalidationKeys,
} from "@/lib/jobAnalysisQueries";
import { UnsavedChangesGuard } from "./UnsavedChangesGuard";

type SaveVariables = {
  mode: "add" | "edit";
  dutyId?: string;
  statement: string;
  idempotencyKey: string;
};

function errorText(error: unknown) {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "操作失敗，請稍後再試";
}

/**
 * 主要職責的編輯器。沿用 Task／表頭同一條慣例：明確儲存、沒有 autosave、
 * 失敗重試沿用同一把 `Idempotency-Key`。
 *
 * **不顯示 `T1`／`T1.1`**——那是匯出版面位置碼，不是畫面上的 identity（ADR 0052 決定 10）。
 */
export function DutyEditor({
  documentId,
  onDirtyChange,
}: {
  documentId: string;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const document = useQuery(documentQueryOptions(documentId));
  const [editingDutyId, setEditingDutyId] = useState<string | "new" | null>(null);
  const [baseline, setBaseline] = useState("");
  const [draft, setDraft] = useState("");

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
        ? addDuty(
            documentId,
            { statement: variables.statement },
            variables.idempotencyKey,
          )
        : editDuty(
            documentId,
            variables.dutyId!,
            { statement: variables.statement },
            variables.idempotencyKey,
          ),
    onSuccess: async () => {
      await invalidate();
      setEditingDutyId(null);
      setBaseline("");
      setDraft("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (variables: { dutyId: string; idempotencyKey: string }) =>
      deleteDuty(documentId, variables.dutyId, variables.idempotencyKey),
    onSuccess: invalidate,
  });

  const reorderMutation = useMutation({
    mutationFn: (variables: { orderedDutyIds: string[]; idempotencyKey: string }) =>
      reorderDuties(documentId, variables.orderedDutyIds, variables.idempotencyKey),
    onSuccess: invalidate,
  });

  const dirty = editingDutyId !== null && draft.trim() !== baseline.trim();

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  const startNew = () => {
    saveMutation.reset();
    setEditingDutyId("new");
    setBaseline("");
    setDraft("");
  };

  const startEdit = (dutyId: string, statement: string) => {
    saveMutation.reset();
    setEditingDutyId(dutyId);
    setBaseline(statement);
    setDraft(statement);
  };

  const cancel = () => {
    if (dirty && !window.confirm("放棄尚未儲存的變更嗎？")) return;
    setEditingDutyId(null);
    setBaseline("");
    setDraft("");
    saveMutation.reset();
  };

  const save = () => {
    const statement = draft.trim();
    if (!statement || !dirty) return;
    const mode = editingDutyId === "new" ? "add" : "edit";
    const dutyId = mode === "edit" ? (editingDutyId ?? undefined) : undefined;
    const previous = saveMutation.variables;
    const sameFailedOperation =
      saveMutation.isError &&
      previous?.mode === mode &&
      previous.dutyId === dutyId &&
      previous.statement === statement;
    saveMutation.mutate(
      sameFailedOperation
        ? previous
        : { mode, dutyId, statement, idempotencyKey: crypto.randomUUID() },
    );
  };

  const remove = (dutyId: string) => {
    if (
      !window.confirm(
        "確定刪除這項主要職責嗎？底下的工作任務會保留，但會變成尚未歸入職責。",
      )
    ) {
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
    const next = [...document.data.duties];
    const target = index + offset;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    const orderedDutyIds = next.map((duty) => duty.duty_id);
    const previous = reorderMutation.variables;
    reorderMutation.mutate(
      reorderMutation.isError &&
        JSON.stringify(previous?.orderedDutyIds) === JSON.stringify(orderedDutyIds)
        ? previous!
        : { orderedDutyIds, idempotencyKey: crypto.randomUUID() },
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

  const duties = document.data.duties;
  const busy =
    saveMutation.isPending || deleteMutation.isPending || reorderMutation.isPending;

  const statementField = (autoFocus: boolean) => (
    <div className="flex items-start gap-2">
      <input
        className="min-w-0 flex-1 rounded-lg border bg-background px-3 py-2 text-sm"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            save();
          } else if (event.key === "Escape") {
            event.preventDefault();
            cancel();
          }
        }}
        placeholder="例如：維運門市營運系統"
        aria-label="主要職責敘述"
        autoFocus={autoFocus}
      />
      <Button
        size="icon"
        aria-label="儲存主要職責"
        disabled={!draft.trim() || !dirty || saveMutation.isPending}
        onClick={save}
      >
        <Check />
      </Button>
      <Button variant="ghost" size="icon" aria-label="取消" onClick={cancel}>
        <X />
      </Button>
    </div>
  );

  return (
    <section className="space-y-4">
      <UnsavedChangesGuard dirty={dirty} />
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">主要職責</h2>
          <p className="text-sm text-muted-foreground">
            先分出幾項主要職責，再把工作任務歸進去。
          </p>
        </div>
        <Button disabled={busy || editingDutyId !== null} onClick={startNew}>
          <Plus />
          新增主要職責
        </Button>
      </div>

      {editingDutyId === "new" ? (
        <Card className="p-4">{statementField(true)}</Card>
      ) : null}

      {duties.length === 0 && editingDutyId !== "new" ? (
        <div className="rounded-xl border border-dashed px-6 py-10 text-center">
          <p className="font-medium">尚未加入主要職責</p>
          <p className="mt-1 text-sm text-muted-foreground">
            工作任務可以先寫，之後再歸入職責。
          </p>
        </div>
      ) : null}

      {duties.map((duty, index) => (
        <Card key={duty.duty_id} className="p-4">
          {editingDutyId === duty.duty_id ? (
            statementField(true)
          ) : (
            <div className="flex items-start gap-3">
              <p className="min-w-0 flex-1 text-sm font-medium">{duty.statement}</p>
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="上移"
                  disabled={busy || index === 0 || editingDutyId !== null}
                  onClick={() => move(index, -1)}
                >
                  <ArrowUp />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="下移"
                  disabled={
                    busy || index === duties.length - 1 || editingDutyId !== null
                  }
                  onClick={() => move(index, 1)}
                >
                  <ArrowDown />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="編輯主要職責"
                  disabled={busy || editingDutyId !== null}
                  onClick={() => startEdit(duty.duty_id, duty.statement)}
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
            </div>
          )}
        </Card>
      ))}

      <div aria-live="polite" className="min-h-5 text-sm text-destructive">
        {saveMutation.isError
          ? errorText(saveMutation.error)
          : deleteMutation.isError
            ? errorText(deleteMutation.error)
            : reorderMutation.isError
              ? errorText(reorderMutation.error)
              : undefined}
      </div>
    </section>
  );
}
