"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";

import { consultationQueryOptions } from "@/lib/jobAnalysisQueries";
import { ConsultationPanel } from "./ConsultationPanel";
import { JdHeaderForm } from "./JdHeaderForm";
import { OpksEditor } from "./OpksEditor";
import { TaskEditor } from "./TaskEditor";
import { GuardedLink } from "./UnsavedChangesGuard";

export function ConsultationWorkspace({ documentId }: { documentId: string }) {
  const consultation = useQuery(consultationQueryOptions(documentId));
  const [headerDraftDirty, setHeaderDraftDirty] = useState(false);
  const [taskDraftDirty, setTaskDraftDirty] = useState(false);
  const [opksDraftDirty, setOpksDraftDirty] = useState(false);
  const dirty = headerDraftDirty || taskDraftDirty || opksDraftDirty;

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-6 py-5">
          <GuardedLink
            dirty={dirty}
            href="/workspace"
            className="rounded-lg p-2 hover:bg-muted"
            aria-label="返回文件庫"
          >
            <ArrowLeft />
          </GuardedLink>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-xl font-semibold">
              {consultation.data?.document.title ?? "職務分析"}
            </h1>
            <p className="text-xs text-muted-foreground">
              AI 顧問訪談與目前文件
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-8 px-6 py-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <ConsultationPanel documentId={documentId} />
        <div className="space-y-8">
          <JdHeaderForm
            documentId={documentId}
            onDirtyChange={setHeaderDraftDirty}
          />
          <TaskEditor
            documentId={documentId}
            embedded
            onDirtyChange={setTaskDraftDirty}
          />
          <OpksEditor
            documentId={documentId}
            onDirtyChange={setOpksDraftDirty}
          />
        </div>
      </main>
    </div>
  );
}
