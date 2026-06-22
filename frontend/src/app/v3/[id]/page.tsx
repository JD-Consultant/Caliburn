"use client";

// D27 文件即工作台。表格優先：一進來就是（可能空的）職務說明書表格，頂部
// 〔選職類〕〔選任務〕入口。所有編輯（選職類/選任務/改名/增刪/拖拉/填格）→ PATCH
// draft（自動儲存）。續做＝重開自動載 draft。finalize 產正式版本。不碰 CopilotKit。
import { use, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronLeft, Download, FileCheck2, Layers, ListChecks } from "lucide-react";
import { useProfile } from "@/hooks/useProfiles";
import { useDocument, useFinalizeDocument, useKsaPool, usePatchDocument } from "@/hooks/useDocument";
import { getDocumentExport } from "@/lib/api";
import { downloadJson } from "@/lib/download";
import { JobDocTable, type CellTarget } from "@/components/interview/v3/JobDocTable";
import { CellFillerPanel } from "@/components/interview/v3/CellFillerPanel";
import { AiTaskPanel } from "@/components/interview/v3/AiTaskPanel";
import { OccupationPicker } from "@/components/interview/v3/OccupationPicker";
import { TaskCuratePanel } from "@/components/interview/v3/TaskCuratePanel";
import { completion, ensureIds } from "@/lib/ocsDoc";
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
  // 補上穩定 id（拖拉用）；memo 讓 id 在重繪間穩定，編輯時 clone 會保留。
  const doc: OcsDocument | undefined = useMemo(() => ensureIds(envelope?.content), [envelope]);
  const status = envelope?.status ?? "none";
  const hasOccupations = !!doc?.ocs_profile?.ocs_code;
  const { data: pool } = useKsaPool(id, hasOccupations);

  const patch = usePatchDocument(id);
  const finalize = useFinalizeDocument(id);

  const [target, setTarget] = useState<CellTarget | null>(null);
  const [starTarget, setStarTarget] = useState<{ unitIdx: number; taskIdx: number } | null>(null);
  const [showOcc, setShowOcc] = useState(false);
  const [showTasks, setShowTasks] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const persist = (next: OcsDocument, after?: () => void) => {
    setError(null);
    patch.mutate(next, {
      onSuccess: () => {
        setSavedAt(new Date().toLocaleTimeString("zh-TW"));
        after?.();
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

  const exportJson = async () => {
    setError(null);
    try {
      const data = await getDocumentExport(id);
      const occ = data.ocs_profile?.ocs_name?.occupation_name || profile?.job_title || "職務說明書";
      downloadJson(`${occ}-職能基準.json`, data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "匯出失敗");
    }
  };

  const pct = doc ? Math.round(completion(doc) * 100) : 0;

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b bg-background px-6 py-3">
        <Link href="/dashboard" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ChevronLeft className="h-4 w-4" />
          職務檔案
        </Link>
        <span className="text-sm font-semibold">{profile?.job_title ?? "載入中…"}</span>
        {status === "final" ? (
          <Badge className="bg-emerald-600 text-xs hover:bg-emerald-600">已產生正式版本 v{envelope?.version}</Badge>
        ) : status === "draft" ? (
          <Badge variant="secondary" className="text-xs">草稿（自動儲存）</Badge>
        ) : null}

        <div className="ml-auto flex flex-wrap items-center gap-2">
          {savedAt ? <span className="text-xs text-muted-foreground">✓ 已自動儲存 {savedAt}</span> : null}
          <Button size="sm" variant="outline" className="gap-1" onClick={() => setShowOcc(true)}>
            <Layers className="h-4 w-4" />
            選職類
          </Button>
          <Button size="sm" variant="outline" className="gap-1" disabled={!hasOccupations} onClick={() => setShowTasks(true)}>
            <ListChecks className="h-4 w-4" />
            選任務
          </Button>
          <Button size="sm" variant="outline" className="gap-1" onClick={exportJson} disabled={status === "none"}>
            <Download className="h-4 w-4" />
            匯出 JSON
          </Button>
          <Button size="sm" className="gap-1" onClick={runFinalize} disabled={finalize.isPending || status === "none"}>
            <FileCheck2 className="h-4 w-4" />
            {finalize.isPending ? "產生中…" : "產生正式版本"}
          </Button>
        </div>
      </header>

      {error ? (
        <div className="flex items-center justify-between gap-3 border-b border-destructive/30 bg-destructive/10 px-6 py-2 text-sm text-destructive">
          <span className="truncate">出了點問題：{error}</span>
          <button className="shrink-0 underline" onClick={() => setError(null)}>關閉</button>
        </div>
      ) : null}

      <main className="mx-auto max-w-5xl px-6 py-6">
        {isLoading || !doc ? (
          <div className="h-40 animate-pulse rounded-xl bg-muted" />
        ) : (
          <div className="flex flex-col gap-6 md:flex-row">
            <aside className="md:w-48 md:shrink-0">
              <div className="rounded-lg border bg-background p-4 md:sticky md:top-6">
                <p className="text-xs text-muted-foreground">完成度</p>
                <p className="mb-2 text-2xl font-semibold tabular-nums">{pct}%</p>
                <Progress value={pct} className="h-2" />
                <p className="mt-3 text-xs text-muted-foreground">
                  〔選職類〕→〔選任務〕帶入任務；點空格填寫，變更自動儲存。
                </p>
              </div>
            </aside>
            <div className="min-w-0 flex-1">
              <JobDocTable
                document={doc}
                onCell={setTarget}
                onStar={(unitIdx, taskIdx) => setStarTarget({ unitIdx, taskIdx })}
                onChange={(d) => persist(d)}
              />
            </div>
          </div>
        )}
      </main>

      {target && doc ? (
        <CellFillerPanel
          key={targetKey(target)}
          document={doc}
          target={target}
          pool={pool ?? EMPTY_POOL}
          saving={patch.isPending}
          onSave={(next) => persist(next, () => setTarget(null))}
          onClose={() => setTarget(null)}
        />
      ) : null}

      {starTarget && doc ? (
        <AiTaskPanel
          key={`star-${starTarget.unitIdx}-${starTarget.taskIdx}`}
          document={doc}
          profileId={id}
          unitIdx={starTarget.unitIdx}
          taskIdx={starTarget.taskIdx}
          saving={patch.isPending}
          onApply={(next) => persist(next, () => setStarTarget(null))}
          onClose={() => setStarTarget(null)}
        />
      ) : null}

      {showOcc ? (
        <OccupationPicker
          profileId={id}
          defaultQuery={profile?.job_summary || profile?.job_title || ""}
          onClose={() => setShowOcc(false)}
          onError={setError}
        />
      ) : null}

      {showTasks ? (
        <TaskCuratePanel
          profileId={id}
          currentDoc={doc}
          onClose={() => setShowTasks(false)}
          onError={setError}
        />
      ) : null}
    </div>
  );
}
