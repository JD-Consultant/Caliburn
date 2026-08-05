"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { JobAnalysisApiError, putJdHeader } from "@/lib/jobAnalysisApi";
import {
  COMPETENCY_LEVELS,
  fromJdHeaderView,
  isJdHeaderFormDirty,
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
  const [baseline, setBaseline] = useState<JdHeaderFormValue | null>(null);
  const [draft, setDraft] = useState<JdHeaderFormValue | null>(null);

  const saveMutation = useMutation({
    mutationFn: (variables: SaveVariables) =>
      putJdHeader(documentId, variables.value, variables.idempotencyKey),
    onSuccess: async () => {
      await Promise.all(
        jobAnalysisInvalidationKeys(documentId).map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      );
      setBaseline(null);
      setDraft(null);
    },
  });

  const dirty = Boolean(
    baseline && draft && isJdHeaderFormDirty(baseline, draft),
  );

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

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
  const editing = draft !== null;

  const startEdit = () => {
    saveMutation.reset();
    const value = fromJdHeaderView(header);
    setBaseline(value);
    setDraft(value);
  };
  const cancel = () => {
    if (dirty && !window.confirm("放棄尚未儲存的變更嗎？")) return;
    setBaseline(null);
    setDraft(null);
    saveMutation.reset();
  };
  const save = () => {
    if (!draft || !dirty) return;
    const value = toJdHeaderWrite(draft);
    const previous = saveMutation.variables;
    const sameFailedOperation =
      saveMutation.isError &&
      JSON.stringify(previous?.value) === JSON.stringify(value);
    saveMutation.mutate(
      sameFailedOperation
        ? previous!
        : { value, idempotencyKey: crypto.randomUUID() },
    );
  };

  const set = <K extends keyof JdHeaderFormValue>(
    key: K,
    next: JdHeaderFormValue[K],
  ) => setDraft((current) => (current ? { ...current, [key]: next } : current));

  return (
    <Card className="p-5">
      <UnsavedChangesGuard dirty={dirty} />
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold">職務說明書表頭</h2>
          <p className="text-sm text-muted-foreground">
            採 iCAP 職能基準欄位版型；未填的欄位只是提示，不會擋住訪談或儲存。
          </p>
        </div>
        {!editing ? (
          <Button variant="outline" onClick={startEdit}>
            <Pencil />
            編輯表頭
          </Button>
        ) : null}
      </div>

      <div className="mb-4">
        <ReadinessNotice readiness={document.data.readiness} />
      </div>

      {editing && draft ? (
        <form
          className="space-y-5"
          onSubmit={(event) => {
            event.preventDefault();
            save();
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              cancel();
            }
          }}
        >
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">職能基準名稱</span>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              value={draft.competencyName}
              onChange={(event) => set("competencyName", event.target.value)}
              placeholder="職類或職業擇一"
              autoFocus
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm font-medium">工作描述</span>
            <textarea
              className="min-h-24 w-full rounded-lg border bg-background px-3 py-2 text-sm"
              value={draft.workDescription}
              onChange={(event) => set("workDescription", event.target.value)}
              placeholder="這個職位主要替誰解決什麼問題"
            />
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">職類別</span>
              <input
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                value={draft.occupationCategoryName}
                onChange={(event) =>
                  set("occupationCategoryName", event.target.value)
                }
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
                <option value="">尚未選擇</option>
                {COMPETENCY_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    第 {level} 級
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">職業別</span>
              <input
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                value={draft.occupationName}
                onChange={(event) => set("occupationName", event.target.value)}
                placeholder="依中華民國職業標準分類"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">職業別代碼</span>
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
              <span className="text-sm font-medium">行業別</span>
              <input
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                value={draft.industryName}
                onChange={(event) => set("industryName", event.target.value)}
                placeholder="依中華民國行業統計分類"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">行業別代碼</span>
              <input
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                value={draft.industryCode}
                onChange={(event) => set("industryCode", event.target.value)}
                placeholder="尚未填寫"
              />
            </label>
          </div>

          <label className="block space-y-1.5">
            <span className="text-sm font-medium">說明與補充事項</span>
            <textarea
              className="min-h-20 w-full rounded-lg border bg-background px-3 py-2 text-sm"
              value={draft.notes}
              onChange={(event) => set("notes", event.target.value)}
              placeholder="有其他說明時才填"
            />
          </label>

          <p className="text-xs text-muted-foreground">
            職能基準代碼與職類別代碼由 iCAP 計畫執行單位配發，這裡不提供填寫。
          </p>

          {saveMutation.isError ? (
            <p className="text-sm text-destructive" role="alert">
              {errorText(saveMutation.error)}
            </p>
          ) : null}

          <div className="flex gap-2">
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
          </div>
        </form>
      ) : (
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div className="sm:col-span-2">
            <dt className="text-xs text-muted-foreground">職能基準名稱</dt>
            <dd>{header.competency_name ?? "尚未填寫"}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs text-muted-foreground">工作描述</dt>
            <dd className="whitespace-pre-wrap">
              {header.work_description ?? "尚未填寫"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">職類別</dt>
            <dd>{header.occupation_category_name ?? "尚未填寫"}</dd>
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
            <dt className="text-xs text-muted-foreground">職業別</dt>
            <dd>
              {header.occupation_name ?? "尚未填寫"}
              {header.occupation_code ? `（${header.occupation_code}）` : ""}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">行業別</dt>
            <dd>
              {header.industry_name ?? "尚未填寫"}
              {header.industry_code ? `（${header.industry_code}）` : ""}
            </dd>
          </div>
          {header.notes ? (
            <div className="sm:col-span-2">
              <dt className="text-xs text-muted-foreground">說明與補充事項</dt>
              <dd className="whitespace-pre-wrap">{header.notes}</dd>
            </div>
          ) : null}
        </dl>
      )}
    </Card>
  );
}
