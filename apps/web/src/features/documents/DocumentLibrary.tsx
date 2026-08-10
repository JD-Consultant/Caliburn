"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BriefcaseBusiness, ChevronRight, Pencil, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import {
  createDocument,
  JobAnalysisApiError,
  putDocument,
} from "@/shared/api/jobAnalysisApi";
import {
  documentListQueryOptions,
  jobAnalysisKeys,
} from "@/shared/query/jobAnalysisQueries";

function errorText(error: unknown): string {
  return error instanceof JobAnalysisApiError
    ? error.message
    : "操作失敗，請稍後再試";
}

export function DocumentLibrary() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const documents = useQuery(documentListQueryOptions());
  const [newTitle, setNewTitle] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");

  const createMutation = useMutation({
    mutationFn: (title: string) => createDocument(title),
    onSuccess: async (document) => {
      await queryClient.invalidateQueries({ queryKey: jobAnalysisKeys.documents });
      setNewTitle("");
      router.push(`/workspace/${document.document_id}`);
    },
  });
  const renameMutation = useMutation({
    mutationFn: ({ documentId, title }: { documentId: string; title: string }) =>
      putDocument(documentId, title),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: jobAnalysisKeys.documents });
      setEditingId(null);
    },
  });

  const create = () => {
    if (createMutation.isPending) return;
    const title = newTitle.trim();
    if (title) createMutation.mutate(title);
  };
  const rename = () => {
    if (renameMutation.isPending) return;
    const title = editingTitle.trim();
    if (editingId && title) {
      renameMutation.mutate({ documentId: editingId, title });
    }
  };

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-5">
          <div className="rounded-xl bg-primary p-2 text-primary-foreground">
            <BriefcaseBusiness className="size-5" />
          </div>
          <div>
            <p className="text-lg font-semibold">Caliburn</p>
            <p className="text-xs text-muted-foreground">本機職務說明書工作區</p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10">
        <div className="mb-8 max-w-2xl">
          <h1 className="text-3xl font-semibold tracking-tight">職務說明書</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            建立或重新開啟保存在這台電腦上的職務說明書。
          </p>
        </div>

        <Card className="mb-8 p-5">
          <label htmlFor="new-document-title" className="text-sm font-medium">
            建立新文件
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              id="new-document-title"
              className="min-w-0 flex-1 rounded-lg border bg-background px-3 py-2 text-sm"
              placeholder="職務名稱，例如：門市營運專員"
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
              {createMutation.isPending ? "建立中…" : "建立文件"}
            </Button>
          </div>
          {createMutation.isError ? (
            <p className="text-sm text-destructive" role="alert">
              {errorText(createMutation.error)}
            </p>
          ) : null}
        </Card>

        {documents.isPending ? (
          <p className="text-sm text-muted-foreground">正在讀取文件…</p>
        ) : documents.isError ? (
          <p className="text-sm text-destructive" role="alert">
            {errorText(documents.error)}
          </p>
        ) : documents.data.length === 0 ? (
          <div className="rounded-xl border border-dashed px-6 py-14 text-center">
            <p className="font-medium">目前還沒有文件</p>
            <p className="mt-1 text-sm text-muted-foreground">
              輸入職務名稱即可開始，其他內容可以之後慢慢補。
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {documents.data.map((document) => (
              <Card key={document.document_id} className="p-5">
                {editingId === document.document_id ? (
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                    <label className="sr-only" htmlFor={`title-${document.document_id}`}>
                      職務名稱
                    </label>
                    <input
                      id={`title-${document.document_id}`}
                      className="min-w-0 flex-1 rounded-lg border bg-background px-3 py-2 text-sm"
                      value={editingTitle}
                      onChange={(event) => setEditingTitle(event.target.value)}
                      autoFocus
                    />
                    <div className="flex gap-2">
                      <Button
                        disabled={!editingTitle.trim() || renameMutation.isPending}
                        onClick={rename}
                      >
                        儲存名稱
                      </Button>
                      <Button variant="ghost" onClick={() => setEditingId(null)}>
                        取消
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-4">
                    <div className="min-w-0 flex-1">
                      <h2 className="truncate text-base font-semibold">{document.title}</h2>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {document.task_count} 項工作 · 更新於{" "}
                        {new Date(document.updated_at).toLocaleString("zh-TW")}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`修改「${document.title}」名稱`}
                      onClick={() => {
                        renameMutation.reset();
                        setEditingId(document.document_id);
                        setEditingTitle(document.title);
                      }}
                    >
                      <Pencil />
                    </Button>
                    <Link
                      href={`/workspace/${document.document_id}`}
                      className="inline-flex h-8 items-center gap-1 rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/80"
                    >
                      開啟
                      <ChevronRight />
                    </Link>
                  </div>
                )}
                {editingId === document.document_id && renameMutation.isError ? (
                  <p className="text-sm text-destructive" role="alert">
                    {errorText(renameMutation.error)}
                  </p>
                ) : null}
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
