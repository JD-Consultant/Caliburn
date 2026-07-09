"use client";

// D27 文件即工作台。表格優先：一進來就是（可能空的）職務說明書表格，頂部
// 〔選職類〕〔選任務〕入口。所有編輯（選職類/選任務/改名/增刪/拖拉/填格）→ PATCH
// draft（自動儲存）。續做＝重開自動載 draft。finalize 產正式版本。不碰 CopilotKit。
import { use, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ChevronLeft, Download, FileCheck2, Layers, MessageCircle, X } from "lucide-react";
import { useProfile } from "@/hooks/useProfiles";
import { useAutosaveDocument, useDocument, useFinalizeDocument } from "@/hooks/useDocument";
import { useKnowledge } from "@/hooks/useKnowledge";
import { getDocumentExport } from "@/lib/api";
import { downloadJson } from "@/lib/download";
import { JobDocTable, type CellTarget } from "@/components/interview/JobDocTable";
import { CellFillerPanel } from "@/components/interview/CellFillerPanel";
import { OccupationPicker } from "@/components/interview/OccupationPicker";
import { UnitPickerMenu } from "@/components/interview/UnitPickerMenu";
import { ConflictDialog } from "@/components/interview/ConflictDialog";
import { CurationDialog } from "@/components/interview/CurationDialog";
import { InterviewPanel } from "@/components/interview/InterviewPanel";
import { completion, ensureIds } from "@/lib/ocsDoc";
import { interviewCuration } from "@/lib/api";
import type { OcsDocument, OpenPickerWidget, PickerPrecheckItem } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

function targetKey(t: CellTarget): string {
  return `${t.kind}-${t.unitIdx}-${t.taskIdx}`;
}

export default function V3Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: profile } = useProfile(id);
  const { data: envelope, isLoading } = useDocument(id);
  // 補上穩定 id（拖拉用）；memo 讓 id 在重繪間穩定，編輯時 clone 會保留。
  const doc: OcsDocument | undefined = useMemo(() => ensureIds(envelope?.content), [envelope]);
  const status = envelope?.status ?? "none";
  const hasOccupations = !!doc?.ocs_profile?.ocs_code;
  // 知識包(ADR 0021):選職責下拉的資料源(表格內選單各自訂閱同一 query)。
  const { data: pack } = useKnowledge(id, hasOccupations);

  const {
    status: saveStatus,
    commit,
    flush,
    loadLatest,
    overwriteWithLocal,
    conflictBusy,
  } = useAutosaveDocument(id);
  const finalize = useFinalizeDocument(id);

  // flush on unmount (lint-clean: update ref in effect, cleanup calls it)
  const flushRef = useRef(flush);
  useEffect(() => { flushRef.current = flush; });
  useEffect(() => () => { flushRef.current(); }, []);

  const [target, setTarget] = useState<CellTarget | null>(null);
  const [showOcc, setShowOcc] = useState(false);
  const [showInterview, setShowInterview] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 0028 D1:訪談引擎 widget 指令 → 開**同一批**編輯器 pickers(同 UI、入口不同)
  // D9:任務盤清單=前端 pack;後端只給 AI 疊加層(precheck)
  const [aiOccQuery, setAiOccQuery] = useState<string | null>(null);
  const [curation, setCuration] = useState<PickerPrecheckItem[] | null>(null);
  const onWidget = (w: OpenPickerWidget) => {
    if (w.picker === "occupation") {
      setAiOccQuery(w.query ?? "");
      setShowOcc(true);
    } else if (w.picker === "task") {
      setCuration(w.precheck ?? []);
    }
  };
  // D8 P1a:選完職類**立刻**鋪任務盤(零打字)——訪談開著才觸發;
  // 盤在前端(D9),端點只拿 AI 預勾:失敗/無 active 也照開全盤(fail-open)
  const onOccupationsApplied = async () => {
    if (!showInterview) return;
    try {
      const res = await interviewCuration(id);
      setCuration(res.precheck);
    } catch {
      setCuration([]);
    }
  };

  const persist = (next: OcsDocument, after?: () => void) => {
    setError(null);
    commit(next);
    after?.();
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
          {saveStatus === "saving" ? (
            <span className="text-xs text-muted-foreground">儲存中…</span>
          ) : saveStatus === "saved" ? (
            <span className="text-xs text-muted-foreground">✓ 已自動儲存</span>
          ) : saveStatus === "unsaved" ? (
            <span className="text-xs text-muted-foreground">尚未儲存</span>
          ) : saveStatus === "conflict" ? (
            <span className="text-xs text-destructive">⚠ 存檔衝突</span>
          ) : null}
          <Button size="sm" variant="outline" className="gap-1" onClick={() => setShowOcc(true)}>
            <Layers className="h-4 w-4" />
            選職類
          </Button>
          {/* 訪談面板(ADR 0020 混合載體:文件常駐、面板在側;引擎 ADR 0023) */}
          <Button
            size="sm"
            variant={showInterview ? "default" : "outline"}
            className="gap-1"
            onClick={() => setShowInterview((v) => !v)}
            // v2(ADR 0027 §9.3):空白也可起跑——顧問開場引導選職類,不再要求先選職類;
            // 只禁已定稿(final)。手動〔選職類〕仍在(平行路徑)。
            disabled={status === "final"}
          >
            <MessageCircle className="h-4 w-4" />
            AI 訪談
          </Button>
          {/* 選職責(獨立選單窗)：勾＝空職責入表格，任務再從職責列「選任務」挑 */}
          <UnitPickerMenu document={doc} pack={pack} disabled={!hasOccupations || !doc} onChange={(d) => persist(d)} />
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
          <div className="flex flex-col gap-6">
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
                profileId={id}
                onCell={setTarget}
                onChange={(d) => persist(d)}
              />
            </div>
          </div>
          </div>
        )}
      </main>

      {target && doc ? (
        <CellFillerPanel
          key={targetKey(target)}
          document={doc}
          target={target}
          profileId={id}
          onSave={(next) => persist(next)}
          onClose={() => setTarget(null)}
        />
      ) : null}


      {showOcc ? (
        <OccupationPicker
          profileId={id}
          defaultQuery={aiOccQuery ?? (profile?.job_summary || profile?.job_title || "")}
          autoSearch={aiOccQuery != null}
          onApplied={onOccupationsApplied}
          onClose={() => { setShowOcc(false); setAiOccQuery(null); }}
          onError={setError}
        />
      ) : null}

      {/* 0028 D1/D4 + D9:AI 任務盤(盤=pack 全量、AI 疊 precheck+引文;
          寫入走 addFromPool→persist 同一路);key=payload 換 → 重掛重置勾選 */}
      {curation && doc ? (
        <CurationDialog
          key={curation.map((x) => x.key).join("|")}
          precheck={curation}
          document={doc}
          pack={pack}
          onApply={(next) => persist(next)}
          onClose={() => setCuration(null)}
        />
      ) : null}

      {saveStatus === "conflict" ? (
        <ConflictDialog
          busy={conflictBusy}
          onLoadLatest={() => void loadLatest()}
          onOverwrite={overwriteWithLocal}
        />
      ) : null}

      {/* 訪談側欄:文件常駐主畫面、面板疊右側(可收);寫入全走 persist 同一條 PATCH */}
      {showInterview ? (
        <aside className="fixed inset-y-0 right-0 z-40 flex w-full max-w-md flex-col border-l bg-background shadow-xl">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-sm font-medium">AI 訪談顧問</span>
            <div className="flex items-center gap-2">
              <Link
                href={`/documents/${id}/interview`}
                className="text-xs text-muted-foreground underline hover:text-foreground"
              >
                訪談紀錄
              </Link>
              <Button size="icon" variant="ghost" onClick={() => setShowInterview(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="min-h-0 flex-1">
            <InterviewPanel
              profileId={id}
              doc={doc}
              onApplyDoc={(next) => persist(next)}
              onWidget={onWidget}
            />
          </div>
        </aside>
      ) : null}

    </div>
  );
}
