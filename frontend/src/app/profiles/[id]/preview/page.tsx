"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useProfile } from "@/hooks/useProfiles";
import { exportDocument, freezeDocument } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  ArrowLeft,
  BriefcaseIcon,
  Download,
  FileJson,
  FileSpreadsheet,
  FileText,
  Loader2,
  ChevronDown,
  ChevronRight,
  Star,
} from "lucide-react";
import type { OcsDocument, BehaviorIndicator, KsaItem, EvidenceRef } from "@/types";
import { SourceBadge } from "@/components/preview/SourceBadge";

type ExportFormat = "docx" | "pdf" | "xlsx" | "json";

const SOURCE_COLOR: Record<string, string> = {
  icap_official: "bg-blue-100 text-blue-700",
  company_defined: "bg-orange-100 text-orange-700",
};
const SOURCE_LABEL: Record<string, string> = {
  icap_official: "iCAP",
  company_defined: "企業",
};

export default function PreviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: profile, isLoading } = useProfile(id);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [freezing, setFreezing] = useState(false);
  const qc = useQueryClient();
  const isFrozen = profile?.stage === "preview";

  const handleExport = async (format: ExportFormat) => {
    setExporting(format);
    try {
      await exportDocument(id, format);
    } catch (e) {
      alert(`匯出失敗：${e}`);
    } finally {
      setExporting(null);
    }
  };

  const handleFreeze = async () => {
    if (isFrozen || freezing) return;
    setFreezing(true);
    try {
      await freezeDocument(id);
      await qc.invalidateQueries({ queryKey: ["profile", id] });
    } catch (e) {
      alert(`凍結失敗：${e}`);
    } finally {
      setFreezing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-muted-foreground text-sm">載入中...</div>
      </div>
    );
  }

  const state = profile?.graph_state;
  const ocs = state?.ocs_document as OcsDocument | undefined;
  const candidates = state?.icap_candidates ?? [];
  const behaviorIndicators = (state?.behavior_indicators ?? []) as BehaviorIndicator[];
  const ksaItems = (state?.ksa_items ?? []) as KsaItem[];
  const extractedTasks = (state?.extracted_tasks ?? []) as ExtractedTask[];

  const ocsProfile = ocs?.ocs_profile;
  const ocsUnits = ocs?.ocs_content?.ocu_units ?? [];
  const attitudes = ocs?.ocs_attitude?.attitudes ?? [];

  const taskMap = new Map(extractedTasks.map((t) => [t.task_name, t]));

  const ExportBtn = ({
    format,
    icon: Icon,
    label,
    variant = "outline",
  }: {
    format: ExportFormat;
    icon: React.ElementType;
    label: string;
    variant?: "outline" | "default";
  }) => (
    <Button
      size="sm"
      variant={variant}
      className="gap-1.5"
      onClick={() => handleExport(format)}
      disabled={!!exporting}
    >
      {exporting === format ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : (
        <Icon className="w-3.5 h-3.5" />
      )}
      {label}
    </Button>
  );

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <header className="border-b px-4 py-3 flex items-center gap-3 shrink-0">
        <Link href={`/profiles/${id}`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <BriefcaseIcon className="w-4 h-4 text-blue-600" />
        <div className="flex-1 min-w-0">
          <h1 className="font-semibold text-sm truncate">{profile?.job_title}</h1>
          <p className="text-xs text-muted-foreground">
            {profile?.department}
            {ocsProfile?.ocs_code && (
              <span className="ml-2 font-mono text-blue-600">{ocsProfile.ocs_code}</span>
            )}
          </p>
        </div>
        <div className="flex gap-1.5 shrink-0 flex-wrap justify-end items-center">
          <ExportBtn format="json"  icon={FileJson}        label="JSON"  />
          <ExportBtn format="xlsx"  icon={FileSpreadsheet} label="Excel" />
          <ExportBtn format="docx"  icon={FileText}        label="DOCX"  />
          <ExportBtn format="pdf"   icon={Download}        label="PDF"   variant="default" />
          <Button
            size="sm"
            variant={isFrozen ? "secondary" : "outline"}
            className="gap-1.5 border-emerald-400 text-emerald-700 hover:bg-emerald-50 dark:text-emerald-300 dark:border-emerald-700"
            onClick={handleFreeze}
            disabled={isFrozen || freezing}
          >
            {freezing ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <span className="text-base leading-none">{isFrozen ? "✓" : "🔒"}</span>
            )}
            {isFrozen ? "已定版" : "定版"}
          </Button>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">

          {/* Title block */}
          <div>
            <h2 className="text-2xl font-bold">{profile?.job_title}</h2>
            <p className="text-muted-foreground">{profile?.department}</p>
            {ocsProfile?.ocs_code && (
              <span className="inline-block mt-1 text-xs font-mono bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                OCS {ocsProfile.ocs_code}
              </span>
            )}
            {profile?.job_summary && (
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {profile.job_summary}
              </p>
            )}
          </div>

          {/* iCAP candidates */}
          {candidates.length > 0 && (
            <section>
              <h3 className="text-base font-semibold mb-3">iCAP 對應職能基準</h3>
              <div className="flex flex-wrap gap-2">
                {candidates.map((c) => (
                  <span
                    key={c.icap_id}
                    className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm"
                  >
                    <span className="font-semibold">{Math.round(c.similarity * 100)}%</span>
                    {c.icap_title}
                    <Badge variant="secondary" className="text-xs">{c.recommendation}</Badge>
                  </span>
                ))}
              </div>
            </section>
          )}

          {/* Behavior Indicators (primary content when OCS not yet generated or as supplement) */}
          {behaviorIndicators.length > 0 && !ocsUnits.length && (
            <>
              <Separator />
              <section className="space-y-4">
                <h3 className="text-base font-semibold">行為指標（{behaviorIndicators.length} 個任務）</h3>
                <div className="space-y-4">
                  {behaviorIndicators.map((ind) => (
                    <BehaviorIndicatorCard
                      key={ind.task_name}
                      indicator={ind}
                      task={taskMap.get(ind.task_name)}
                    />
                  ))}
                </div>
              </section>
            </>
          )}

          {/* KSA */}
          {ksaItems.length > 0 && (
            <>
              <Separator />
              <section>
                <h3 className="text-base font-semibold mb-4">知識、技能與態度（KSA）</h3>
                <KsaSection items={ksaItems} />
              </section>
            </>
          )}

          <Separator />

          {/* OCU units */}
          {ocsUnits.length > 0 ? (
            <section className="space-y-8">
              <h3 className="text-base font-semibold">職能單元與工作任務</h3>

              {ocsUnits.map((unit) => (
                <div key={unit.ocu_code} className="space-y-4">
                  {/* Unit header */}
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono bg-blue-600 text-white px-2 py-0.5 rounded">
                      {unit.ocu_code}
                    </span>
                    <h4 className="font-semibold text-blue-800">{unit.ocu_name}</h4>
                  </div>

                  {/* Tasks */}
                  {unit.tasks.map((task) => {
                    const tc = task.task_codes[0] ?? {};
                    return (
                      <div
                        key={tc.code}
                        className="ml-4 rounded-xl border p-5 space-y-4"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                            {tc.code}
                          </span>
                          <h5 className="font-semibold">{tc.name}</h5>
                        </div>

                        {task.competency_blocks.map((block, bi) => (
                          <div key={bi} className="space-y-3">
                            <div className="text-xs text-muted-foreground">
                              職能等級 {block.competency_level}
                            </div>

                            {/* P indicators */}
                            {block.indicators.map((ind) => (
                              <div key={ind.code}>
                                <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                                  <span className="text-xs font-mono bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">
                                    {ind.code}
                                  </span>
                                  <span className="text-xs font-medium text-muted-foreground">行為指標</span>
                                  {(ind.display_labels ?? (ind.display_label ? [ind.display_label] : [])).map((l) => (
                                    <SourceBadge key={l} label={l} />
                                  ))}
                                </div>
                                <p className="text-sm bg-muted/50 rounded-lg px-3 py-2 leading-relaxed">
                                  {ind.text}
                                </p>
                                {ind.evidence_refs?.length ? (
                                  <EvidenceRefs refs={ind.evidence_refs as EvidenceRef[]} />
                                ) : null}
                              </div>
                            ))}

                            {/* O outputs */}
                            {block.outputs.length > 0 && (
                              <div>
                                <p className="text-xs font-medium text-muted-foreground mb-1.5">工作產出</p>
                                <div className="flex flex-wrap gap-1.5">
                                  {block.outputs.map((out) => (
                                    <span
                                      key={out.code}
                                      className="inline-flex items-center gap-1 text-xs border rounded-full px-2 py-0.5"
                                    >
                                      <span className="font-mono text-green-700">{out.code}</span>
                                      {out.name}
                                      {(out.display_labels ?? (out.display_label ? [out.display_label] : [])).map((l) => (
                                        <SourceBadge key={l} label={l} />
                                      ))}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* K knowledge */}
                            {block.knowledge.length > 0 && (
                              <div>
                                <p className="text-xs font-medium text-muted-foreground mb-1.5">知識 Knowledge</p>
                                <KsaList items={block.knowledge} />
                              </div>
                            )}

                            {/* S skills */}
                            {block.skills.length > 0 && (
                              <div>
                                <p className="text-xs font-medium text-muted-foreground mb-1.5">技能 Skill</p>
                                <KsaList items={block.skills} />
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    );
                  })}
                </div>
              ))}
            </section>
          ) : (
            /* Fallback: flat task list if ocs_document not yet generated */
            <FlatTaskFallback state={state} />
          )}

          {/* Attitudes */}
          {attitudes.length > 0 && (
            <>
              <Separator />
              <section>
                <h3 className="text-base font-semibold mb-3">工作態度 Attitude</h3>
                <ul className="space-y-2">
                  {attitudes.map((a) => (
                    <li key={a.code} className="flex items-start gap-2 text-sm">
                      <span className="font-mono text-xs text-muted-foreground mt-0.5 shrink-0">{a.code}</span>
                      <span className="flex-1">{a.name}</span>
                      <div className="flex items-center gap-1 shrink-0">
                        {(a.display_labels ?? (a.display_label ? [a.display_label] : [])).map((l) => (
                          <SourceBadge key={l} label={l} />
                        ))}
                        <IcapBadge sourceType={a.source_type} icapRef={a.icap_ref} />
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            </>
          )}

        </div>
      </ScrollArea>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function KsaList({ items }: { items: Array<{ code: string; name: string; source_type?: string; icap_ref?: string }> }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item) => (
        <li key={item.code} className="flex items-start gap-2 text-sm">
          <span className="font-mono text-xs text-muted-foreground mt-0.5 shrink-0">{item.code}</span>
          <span className="flex-1">{item.name}</span>
          <IcapBadge sourceType={item.source_type} icapRef={item.icap_ref} />
        </li>
      ))}
    </ul>
  );
}

function IcapBadge({ sourceType, icapRef }: { sourceType?: string; icapRef?: string }) {
  const colorClass = SOURCE_COLOR[sourceType ?? ""] ?? "bg-gray-100 text-gray-600";
  const label = SOURCE_LABEL[sourceType ?? ""] ?? sourceType ?? "";
  return (
    <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded font-medium ${colorClass}`}>
      {label}
      {icapRef && <span className="ml-1 font-mono opacity-75">← {icapRef}</span>}
    </span>
  );
}

// ── Evidence refs inline expand ───────────────────────────────────────────────

const EVIDENCE_SOURCE_LABEL: Record<string, string> = {
  interview_quote: "訪談引用",
  star_slot: "STAR 槽位",
  five_w2h_field: "5W2H 欄位",
  icap_reference: "iCAP 參考",
  manual_edit: "手動編輯",
};

function EvidenceRefs({ refs }: { refs: EvidenceRef[] }) {
  const [open, setOpen] = useState(false);
  if (!refs.length) return null;
  return (
    <div className="mt-1.5">
      <button
        onClick={() => setOpen(!open)}
        className="text-[10px] text-blue-600 hover:text-blue-800 flex items-center gap-0.5 transition-colors"
      >
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        {refs.length} 條來源依據
      </button>
      {open && (
        <ul className="mt-1 space-y-1 pl-3 border-l-2 border-blue-200 dark:border-blue-800">
          {refs.map((r, i) => (
            <li key={i} className="text-[10px] text-muted-foreground leading-relaxed">
              <span className="font-medium text-foreground/70">
                {EVIDENCE_SOURCE_LABEL[r.source_type] ?? r.source_type}
              </span>
              {r.field && ` · ${r.field}`}
              {r.quote && (
                <span className="block italic mt-0.5 line-clamp-2">「{r.quote}」</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Behavior Indicator Card ───────────────────────────────────────────────────

function QualityBadge({ score }: { score?: number }) {
  if (score === undefined) return null;
  const pct = Math.round(score * 100);
  if (pct >= 85)
    return <Badge className="text-[10px] bg-emerald-100 text-emerald-700 border border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300">高品質 {pct}%</Badge>;
  if (pct >= 60)
    return <Badge className="text-[10px] bg-blue-100 text-blue-700 border border-blue-200 dark:bg-blue-950 dark:text-blue-300">通過 {pct}%</Badge>;
  return <Badge variant="outline" className="text-[10px] text-muted-foreground">接受 {pct}%</Badge>;
}

function BehaviorIndicatorCard({
  indicator,
  task,
}: {
  indicator: BehaviorIndicator;
  task?: ExtractedTask;
}) {
  const [starOpen, setStarOpen] = useState(false);
  const hasStarCase = !!(task?.star_case?.situation || task?.star_case?.action);

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="p-5 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <h4 className="font-semibold">{indicator.task_name}</h4>
          <QualityBadge score={indicator.quality_score} />
        </div>

        {indicator.indicator_5w2h && (
          <div>
            <p className="text-[10px] font-medium text-muted-foreground mb-1.5 uppercase tracking-wide">
              5W2H 版（職務說明書）
            </p>
            <p className="text-sm bg-muted/50 rounded-lg px-3 py-2 leading-relaxed">
              {indicator.indicator_5w2h}
            </p>
          </div>
        )}

        {indicator.indicator_abcd && (
          <div>
            <p className="text-[10px] font-medium text-muted-foreground mb-1.5 uppercase tracking-wide">
              ABCD 版（評核語言）
            </p>
            <p className="text-sm text-foreground/80 leading-relaxed">
              {indicator.indicator_abcd}
            </p>
          </div>
        )}

        {hasStarCase && (
          <button
            className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 transition-colors"
            onClick={() => setStarOpen(!starOpen)}
          >
            {starOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            <Star className="w-3 h-3" />
            STAR 真實案例
          </button>
        )}
      </div>

      {starOpen && task?.star_case && (
        <div className="border-t px-5 pb-5 pt-3 bg-muted/30 space-y-3">
          {(
            [
              ["S 情境", task.star_case.situation],
              ["T 目標", task.star_case.task],
              ["A 行動", task.star_case.action],
              ["R 結果", task.star_case.result],
            ] as [string, string | undefined][]
          )
            .filter(([, v]) => !!v)
            .map(([label, value]) => (
              <div key={label}>
                <p className="text-[10px] text-muted-foreground font-medium mb-0.5">{label}</p>
                <p className="text-xs text-foreground/80 leading-relaxed">{value}</p>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

// ── KSA Section ───────────────────────────────────────────────────────────────

function KsaSection({ items }: { items: KsaItem[] }) {
  const groups = {
    K: items.filter((i) => i.ksa_type === "K"),
    S: items.filter((i) => i.ksa_type === "S"),
    A: items.filter((i) => i.ksa_type === "A"),
  };
  const meta = {
    K: { label: "知識 Knowledge", cls: "bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-950 dark:text-blue-300" },
    S: { label: "技能 Skills", cls: "bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-950 dark:text-emerald-300" },
    A: { label: "態度 Attitudes", cls: "bg-violet-50 text-violet-700 border-violet-100 dark:bg-violet-950 dark:text-violet-300" },
  };
  return (
    <div className="grid grid-cols-3 gap-4">
      {(["K", "S", "A"] as const).map((type) => (
        <div key={type} className="rounded-lg border bg-card overflow-hidden">
          <div className={`px-3 py-2 border-b text-xs font-semibold ${meta[type].cls}`}>
            {meta[type].label}
          </div>
          <ul className="p-3 space-y-1.5">
            {groups[type].length === 0 ? (
              <li className="text-xs text-muted-foreground">—</li>
            ) : (
              groups[type].map((item, i) => (
                <li key={i} className="flex items-start gap-1.5 text-xs">
                  <span className="text-muted-foreground shrink-0 mt-0.5">•</span>
                  <div className="flex-1">
                    {item.content}
                    {item.source_type === "icap_official" && (
                      <span className="ml-1 inline-block">
                        <SourceBadge label="[iCAP參考]" />
                      </span>
                    )}
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>
      ))}
    </div>
  );
}

// ── FlatTaskFallback (when neither OCS doc nor behavior_indicators yet) ───────

function FlatTaskFallback({ state }: { state: Record<string, unknown> | undefined }) {
  const tasks = (state?.extracted_tasks as ExtractedTask[]) ?? [];
  if (!tasks.length) return null;
  return (
    <section>
      <h3 className="text-base font-semibold mb-4">已萃取任務</h3>
      <div className="space-y-3">
        {tasks.map((task) => (
          <div key={task.task_name} className="rounded-xl border p-4">
            <h4 className="font-semibold text-sm">{task.task_name}</h4>
            {task.description && (
              <p className="text-xs text-muted-foreground mt-1">{task.description}</p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

// ── Local-only types ──────────────────────────────────────────────────────────

interface ExtractedTask {
  task_name: string;
  description?: string;
  star_case?: {
    situation?: string;
    task?: string;
    action?: string;
    result?: string;
  };
}
