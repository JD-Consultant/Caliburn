"use client";

// D27 文件即工作台（T8 + T10）。取代舊的 interrupt 訪談頁。純 REST/PATCH，不碰
// CopilotKit。status=none → SeedPanel；否則 → 左 rail（狀態/完成度）+ 右 JobDocTable，
// 點格開 CellFillerPanel、儲存即 PATCH（自動儲存），可 finalize 產正式版本。
// 續做＝重開自動載入 draft 文件。
import { use, useState } from "react";
import Link from "next/link";
import { ChevronLeft, FileCheck2 } from "lucide-react";
import { useProfile } from "@/hooks/useProfiles";
import { useDocument, useFinalizeDocument, useKsaPool, usePatchDocument } from "@/hooks/useDocument";
import { JobDocTable, type CellTarget } from "@/components/interview/v3/JobDocTable";
import { CellFillerPanel } from "@/components/interview/v3/CellFillerPanel";
import { SeedPanel } from "@/components/interview/v3/SeedPanel";
import { completion } from "@/lib/ocsDoc";
import type { KsaPool, OcsDocument } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

const EMPTY_POOL: KsaPool = { knowledge: [], skills: [], attitudes: [] };

function targetKey(t: CellTarget): string {
  return t.kind === "a" ? "a" : `${t.kind}-${t.unitIdx}-${t.taskIdx}`;
}

export default function V3Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: profile } = useProfile(id);
  const { data: envelope, isLoading } = useDocument(id);
  const status = envelope?.status ?? "none";
  const { data: pool } = useKsaPool(id, status !== "none");

  const patch = usePatchDocument(id);
  const finalize = useFinalizeDocument(id);

  const [target, setTarget] = useState<CellTarget | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const doc: OcsDocument | undefined = envelope?.content;

  const saveCell = (next: OcsDocument) => {
    setError(null);
    patch.mutate(next, {
      onSuccess: () => {
        setSavedAt(new Date().toLocaleTimeString("zh-TW"));
        setTarget(null);
      },
      onError: (e: unknown) => setError(e instanceof Error ? e.message : "儲存失敗"),
    });
  };

  const runFinalize = () => {
    setError(null);
    finalize.mutate(undefined, {
      onError: (e: unknown) => setError(e instanceof Error ? e.message : "產生正式版本失敗"),
    });
  };

  const pct = doc ? Math.round(completion(doc) * 100) : 0;

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b bg-background px-6 py-3">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" />
          職務檔案
        </Link>
        <span className="text-sm font-semibold">{profile?.job_title ?? "載入中…"}</span>
        {status === "final" ? (
          <Badge className="bg-emerald-600 text-xs hover:bg-emerald-600">已產生正式版本 v{envelope?.version}</Badge>
        ) : status === "draft" ? (
          <Badge variant="secondary" className="text-xs">草稿（自動儲存）</Badge>
        ) : null}
        <div className="ml-auto flex items-center gap-3">
          {savedAt ? (
            <span className="text-xs text-muted-foreground">✓ 已自動儲存 {savedAt}</span>
          ) : null}
          {status !== "none" ? (
            <Button size="sm" className="gap-1" onClick={runFinalize} disabled={finalize.isPending}>
              <FileCheck2 className="h-4 w-4" />
              {finalize.isPending ? "產生中…" : "產生正式版本"}
            </Button>
          ) : null}
        </div>
      </header>

      {error ? (
        <div className="flex items-center justify-between gap-3 border-b border-destructive/30 bg-destructive/10 px-6 py-2 text-sm text-destructive">
          <span className="truncate">出了點問題：{error}</span>
          <button className="shrink-0 underline" onClick={() => setError(null)}>
            關閉
          </button>
        </div>
      ) : null}

      <main className="mx-auto max-w-5xl px-6 py-6">
        {isLoading ? (
          <div className="h-40 animate-pulse rounded-xl bg-muted" />
        ) : status === "none" ? (
          <SeedPanel profileId={id} defaultQuery={profile?.job_summary || profile?.job_title || ""} onError={setError} />
        ) : doc ? (
          <div className="flex flex-col gap-6 md:flex-row">
            {/* 左 rail：完成度 */}
            <aside className="md:w-48 md:shrink-0">
              <div className="rounded-lg border bg-background p-4 md:sticky md:top-6">
                <p className="text-xs text-muted-foreground">完成度</p>
                <p className="mb-2 text-2xl font-semibold tabular-nums">{pct}%</p>
                <Progress value={pct} className="h-2" />
                <p className="mt-3 text-xs text-muted-foreground">
                  點任一空格填寫；變更會自動儲存。填齊後可「產生正式版本」。
                </p>
              </div>
            </aside>

            {/* 右：工作台主表 */}
            <div className="min-w-0 flex-1">
              <JobDocTable document={doc} onCell={setTarget} />
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">找不到文件。</p>
        )}
      </main>

      {target && doc ? (
        <CellFillerPanel
          key={targetKey(target)}
          document={doc}
          target={target}
          pool={pool ?? EMPTY_POOL}
          saving={patch.isPending}
          onSave={saveCell}
          onClose={() => setTarget(null)}
        />
      ) : null}
    </div>
  );
}
