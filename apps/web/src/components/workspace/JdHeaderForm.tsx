"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { JdHeaderView } from "@caliburn/job-analysis-contract";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { JobAnalysisApiError, putJdHeader } from "@/lib/jobAnalysisApi";
import {
  COMPETENCY_LEVELS,
  fromJdHeaderView,
  isJdHeaderFormDirty,
  shouldAdoptJdHeaderRefetch,
  type JdHeaderFormValue,
  toJdHeaderWrite,
} from "@/lib/jobAnalysisHeader";
import {
  documentQueryOptions,
  jobAnalysisInvalidationKeys,
} from "@/lib/jobAnalysisQueries";
import { ReadinessNotice } from "./ReadinessNotice";
import { UnsavedChangesGuard } from "./UnsavedChangesGuard";

function errorText(error: unknown) {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "操作失敗，請稍後再試";
}

type SaveVariables = {
  value: ReturnType<typeof toJdHeaderWrite>;
  idempotencyKey: string;
};

export function JdHeaderForm({
  documentId,
  onDirtyChange,
}: {
  documentId: string;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const document = useQuery(documentQueryOptions(documentId));
  const [editing, setEditing] = useState(false);
  const [baseline, setBaseline] = useState<JdHeaderFormValue | null>(null);
  const [draft, setDraft] = useState<JdHeaderFormValue | null>(null);
  const syncedHeader = useRef<JdHeaderView | null>(null);

  const dirty = Boolean(
    editing && baseline && draft && isJdHeaderFormDirty(baseline, draft),
  );

  useEffect(() => {
    const nextHeader = document.data?.jd_header;
    if (
      !nextHeader ||
      !shouldAdoptJdHeaderRefetch(
        editing,
        dirty,
        syncedHeader.current,
        nextHeader,
      )
    ) {
      return;
    }

    syncedHeader.current = nextHeader;
    const value = fromJdHeaderView(nextHeader);
    setBaseline(value);
    setDraft(value);
  }, [document.data?.jd_header, dirty, editing]);

  useEffect(() => {
    onDirtyChange?.(dirty);
    return () => onDirtyChange?.(false);
  }, [dirty, onDirtyChange]);

  const invalidate = async () => {
    await Promise.all(
      jobAnalysisInvalidationKeys(documentId).map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    );
  };

  const saveMutation = useMutation({
    mutationFn: (variables: SaveVariables) =>
      putJdHeader(documentId, variables.value, variables.idempotencyKey),
    onSuccess: async (header) => {
      await invalidate();
      const value = fromJdHeaderView(header);
      syncedHeader.current = header;
      setBaseline(value);
      setDraft(value);
      setEditing(false);
    },
  });

  if (document.isPending) {
    return <p className="text-sm text-muted-foreground">正在讀取表頭…</p>;
  }
  if (document.isError || !document.data) {
    return (
      <p className="text-sm text-destructive" role="alert">
        {errorText(document.error)}
      </p>
    );
  }

  const header = document.data.jd_header;
  const readiness = document.data.readiness;

  const startEdit = () => {
    if (saveMutation.isPending) return;
    saveMutation.reset();
    const value = fromJdHeaderView(header);
    syncedHeader.current = header;
    setBaseline(value);
    setDraft(value);
    setEditing(true);
  };

  const cancel = () => {
    if (saveMutation.isPending) return;
    if (dirty && !window.confirm("放棄尚未儲存的變更嗎？")) return;
    setEditing(false);
    syncedHeader.current = null;
    setBaseline(null);
    setDraft(null);
    saveMutation.reset();
  };

  const save = () => {
    if (!draft || !dirty || saveMutation.isPending) return;

    const value = toJdHeaderWrite(draft);
    const previous = saveMutation.variables;
    const sameFailedOperation =
      saveMutation.isError &&
      previous !== undefined &&
      JSON.stringify(previous.value) === JSON.stringify(value);
    const variables =
      sameFailedOperation && previous
        ? previous
        : { value, idempotencyKey: crypto.randomUUID() };
    saveMutation.mutate(variables);
  };

  const set = <K extends keyof JdHeaderFormValue>(
    key: K,
    value: JdHeaderFormValue[K],
  ) => {
    setDraft((current) => (current ? { ...current, [key]: value } : current));
  };

  return (
    <Card className="p-5">
      <UnsavedChangesGuard dirty={dirty} />
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold">職務說明書基本資料</h2>
          <p className="text-sm text-muted-foreground">
            可直接編輯 iCAP 版型欄位；缺漏提示不會阻擋儲存、訪談或匯出。
          </p>
        </div>
        {!editing ? (
          <Button variant="outline" onClick={startEdit}>
            <Pencil />
            編輯基本資料
          </Button>
        ) : null}
      </div>

      <ReadinessNotice readiness={readiness} />

      {editing && draft ? (
        <form
          className="space-y-5"
          onSubmit={(event) => {
            event.preventDefault();
            save();
          }}
          onKeyDown={(event) => {
            if (saveMutation.isPending) return;
            if (event.key === "Escape") {
              event.preventDefault();
              cancel();
            } else if (
              event.key === "Enter" &&
              (event.ctrlKey || event.metaKey)
            ) {
              event.preventDefault();
              save();
            }
          }}
        >
          <fieldset disabled={saveMutation.isPending} className="space-y-5">
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">職能基準名稱</span>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              value={draft.competencyName}
              onChange={(event) => set("competencyName", event.target.value)}
              placeholder="尚未填寫"
              autoFocus
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm font-medium">所屬類別</span>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              value={draft.occupationCategoryName}
              onChange={(event) =>
                set("occupationCategoryName", event.target.value)
              }
              placeholder="尚未填寫"
            />
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">職業名稱</span>
              <input
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                value={draft.occupationName}
                onChange={(event) => set("occupationName", event.target.value)}
                placeholder="尚未填寫"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">職業代碼</span>
              <input
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                value={draft.occupationCode}
                onChange={(event) => set("occupationCode", event.target.value)}
                placeholder="尚未填寫"
              />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">行業名稱</span>
              <input
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                value={draft.industryName}
                onChange={(event) => set("industryName", event.target.value)}
                placeholder="尚未填寫"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">行業代碼</span>
              <input
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                value={draft.industryCode}
                onChange={(event) => set("industryCode", event.target.value)}
                placeholder="尚未填寫"
              />
            </label>
          </div>

          <label className="block space-y-1.5">
            <span className="text-sm font-medium">工作描述</span>
            <textarea
              className="min-h-24 w-full rounded-lg border bg-background px-3 py-2 text-sm"
              value={draft.workDescription}
              onChange={(event) => set("workDescription", event.target.value)}
              placeholder="尚未填寫"
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm font-medium">基準級別</span>
            <select
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              value={draft.competencyLevel}
              onChange={(event) =>
                set(
                  "competencyLevel",
                  event.target.value as JdHeaderFormValue["competencyLevel"],
                )
              }
            >
              <option value="">尚未填寫</option>
              {COMPETENCY_LEVELS.map((level) => (
                <option key={level} value={level}>
                  第 {level} 級
                </option>
              ))}
            </select>
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm font-medium">說明與補充事項</span>
            <textarea
              className="min-h-20 w-full rounded-lg border bg-background px-3 py-2 text-sm"
              value={draft.notes}
              onChange={(event) => set("notes", event.target.value)}
              placeholder="尚未填寫"
            />
          </label>

          <p className="text-xs text-muted-foreground">
            職能基準代碼與職類別代碼由 iCAP 配發，本頁不提供輸入欄位。
          </p>
          </fieldset>

          {saveMutation.isError ? (
            <p className="text-sm text-destructive" role="alert">
              {errorText(saveMutation.error)}；內容已保留，可直接重試。
            </p>
          ) : null}

          <div className="flex items-center gap-2">
            <Button type="submit" disabled={!dirty || saveMutation.isPending}>
              {saveMutation.isPending ? "儲存中…" : "儲存"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={cancel}
              disabled={saveMutation.isPending}
            >
              取消
            </Button>
            <span className="text-xs text-muted-foreground">
              Ctrl/Cmd+Enter 儲存 · Esc 取消
            </span>
          </div>
        </form>
      ) : (
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-muted-foreground">職能基準名稱</dt>
            <dd>{header.competency_name ?? "尚未填寫"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">所屬類別</dt>
            <dd>{header.occupation_category_name ?? "尚未填寫"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">職業名稱</dt>
            <dd>{header.occupation_name ?? "尚未填寫"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">職業代碼</dt>
            <dd>{header.occupation_code ?? "尚未填寫"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">行業名稱</dt>
            <dd>{header.industry_name ?? "尚未填寫"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">行業代碼</dt>
            <dd>{header.industry_code ?? "尚未填寫"}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs text-muted-foreground">工作描述</dt>
            <dd className="whitespace-pre-wrap">
              {header.work_description ?? "尚未填寫"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">基準級別</dt>
            <dd>
              {header.competency_level === null
                ? "尚未填寫"
                : `第 ${header.competency_level} 級`}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">說明與補充事項</dt>
            <dd className="whitespace-pre-wrap">
              {header.notes ?? "尚未填寫"}
            </dd>
          </div>
        </dl>
      )}
    </Card>
  );
}
