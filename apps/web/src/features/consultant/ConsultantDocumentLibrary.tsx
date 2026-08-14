"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BriefcaseBusiness, ChevronRight, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  createConsultantDocument,
  deleteConsultantDocument,
  JobAnalysisApiError,
} from "@/shared/api/jobAnalysisApi";
import {
  consultantDocumentListQueryOptions,
  jobAnalysisKeys,
} from "@/shared/query/jobAnalysisQueries";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

function errorText(error: unknown): string {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "操作失敗，請稍後再試";
}

export function ConsultantDocumentLibrary() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const documents = useQuery(consultantDocumentListQueryOptions());
  const [newTitle, setNewTitle] = useState("");

  const createMutation = useMutation({
    mutationFn: (operation: { title: string; idempotencyKey: string }) =>
      createConsultantDocument(operation.title, operation.idempotencyKey),
    onSuccess: async (document) => {
      await queryClient.invalidateQueries({
        queryKey: jobAnalysisKeys.consultantDocuments,
      });
      setNewTitle("");
      router.push(`/workspace/${document.document_id}`);
    },
  });
  const deleteMutation = useMutation({
    mutationFn: deleteConsultantDocument,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: jobAnalysisKeys.consultantDocuments,
      });
    },
  });

  const create = () => {
    const title = newTitle.trim();
    if (!title || createMutation.isPending) return;
    const previous = createMutation.variables;
    const retry = createMutation.isError && previous?.title === title;
    createMutation.mutate(
      retry
        ? previous
        : { title, idempotencyKey: crypto.randomUUID() },
    );
  };

  return (
    <div className="min-h-screen bg-stone-50 text-stone-950">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-5">
          <div className="rounded-xl bg-stone-950 p-2 text-white">
            <BriefcaseBusiness className="size-5" />
          </div>
          <div>
            <p className="text-lg font-semibold">Caliburn</p>
            <p className="text-xs text-stone-500">AI 職務分析顧問</p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10">
        <div className="mb-8 max-w-2xl">
          <p className="mb-2 text-xs font-semibold tracking-[0.18em] text-amber-700 uppercase">
            本機工作區
          </p>
          <h1 className="text-3xl font-semibold tracking-tight">你的職務分析</h1>
          <p className="mt-3 text-sm leading-6 text-stone-600">
            建立新職務或回到先前訪談。關閉頁面不會結束訪談；下次開啟同一份文件會接續原本的理解、缺口與待確認變更。
          </p>
        </div>

        <Card className="mb-8 border-stone-200 bg-white p-5 shadow-sm">
          <label htmlFor="new-consultant-document" className="text-sm font-medium">
            你目前的職位或職務名稱
          </label>
          <p className="-mt-2 text-xs text-stone-500">
            先用暫定名稱即可，正式文件內容之後仍可修改。
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              id="new-consultant-document"
              className="min-w-0 flex-1 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
              placeholder="例如：採購專員"
              value={newTitle}
              onChange={(event) => setNewTitle(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") create();
              }}
            />
            <Button
              className="gap-2"
              disabled={!newTitle.trim() || createMutation.isPending}
              onClick={create}
            >
              <Plus />
              {createMutation.isPending ? "建立中…" : "開始分析"}
            </Button>
          </div>
          {createMutation.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {errorText(createMutation.error)}；可直接重試。
            </p>
          ) : null}
        </Card>

        {documents.isPending ? (
          <p className="text-sm text-stone-500">正在讀取文件…</p>
        ) : documents.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {errorText(documents.error)}
          </p>
        ) : documents.data.documents.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-stone-300 bg-white px-6 py-14 text-center">
            <p className="font-medium">目前還沒有職務分析</p>
            <p className="mt-1 text-sm text-stone-500">
              輸入暫定職務名稱，顧問會先協助盤點工作。
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {documents.data.documents.map((document) => (
              <Card
                key={document.document_id}
                className="border-stone-200 bg-white p-5 shadow-sm"
              >
                <div className="flex items-center gap-4">
                  <div className="min-w-0 flex-1">
                    <h2 className="truncate text-base font-semibold">{document.title}</h2>
                    <p className="mt-1 text-xs text-stone-500">
                      更新於 {new Date(document.updated_at).toLocaleString("zh-TW")}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`刪除「${document.title}」`}
                    disabled={deleteMutation.isPending}
                    onClick={() => {
                      if (window.confirm(`確定刪除「${document.title}」？此操作無法復原。`)) {
                        deleteMutation.mutate(document.document_id);
                      }
                    }}
                  >
                    <Trash2 />
                  </Button>
                  <Link
                    href={`/workspace/${document.document_id}`}
                    className="inline-flex h-8 items-center gap-1 rounded-lg bg-stone-950 px-3 text-sm font-medium text-white hover:bg-stone-800"
                  >
                    繼續
                    <ChevronRight />
                  </Link>
                </div>
              </Card>
            ))}
            {deleteMutation.isError ? (
              <p role="alert" className="text-sm text-destructive">
                {errorText(deleteMutation.error)}
              </p>
            ) : null}
          </div>
        )}
      </main>
    </div>
  );
}
