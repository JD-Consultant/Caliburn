"use client";

import { cn } from "@/lib/utils";
import type { Task, Stage, BehaviorIndicator, KsaItem, IcapCandidate, OcsDocument, JobProfile } from "@/types";

interface Props {
  profile: JobProfile;
  tasks: Task[];
  indicators: BehaviorIndicator[];
  ksaItems: KsaItem[];
  stage: Stage;
  currentTaskIndex: number;
  candidates: IcapCandidate[];
  ocsDocument?: OcsDocument;
}

// ── Skeleton ────────────────────────────────────────────────────────────────

function Sk({ w = "full", dim = false }: { w?: "full" | "3/4" | "2/3" | "1/2" | "1/3"; dim?: boolean }) {
  const widths = { full: "w-full", "3/4": "w-3/4", "2/3": "w-2/3", "1/2": "w-1/2", "1/3": "w-1/3" };
  return <div className={cn("h-2 rounded animate-pulse my-0.5", dim ? "bg-muted/25" : "bg-muted/50", widths[w])} />;
}

// ── Building the row data ────────────────────────────────────────────────────

interface DocRow {
  ocuCode: string;
  ocuName: string;
  ocuRowSpan: number;  // how many task rows this OCU spans
  taskCode: string;
  taskName: string;
  outputs: string[];
  indicatorTexts: string[];
  hasQualityWarning: boolean;
  level: number;
  knowledge: string[];
  skills: string[];
  isActive: boolean;
  isDone: boolean;
  isPending: boolean;
  isFirst: boolean; // first task in its OCU
}

function buildRows(
  tasks: Task[],
  indicators: BehaviorIndicator[],
  ksaItems: KsaItem[],
  stage: Stage,
  currentTaskIndex: number,
  ocsDocument?: OcsDocument,
): DocRow[] {
  const isPerTask = ["star", "five_w2h", "indicator"].includes(stage);
  const kList = ksaItems.filter((k) => k.ksa_type === "K").map((k) => k.content);
  const sList = ksaItems.filter((k) => k.ksa_type === "S").map((k) => k.content);

  // Use OCS document if available
  if (ocsDocument?.ocs_content?.ocu_units) {
    const rows: DocRow[] = [];
    ocsDocument.ocs_content.ocu_units.forEach((unit) => {
      unit.tasks.forEach((t, ti) => {
        const tc = t.task_codes[0] ?? { code: "?", name: "?" };
        const block = t.competency_blocks[0] ?? { indicators: [], outputs: [], knowledge: [], skills: [], competency_level: 3 };
        rows.push({
          ocuCode: unit.ocu_code,
          ocuName: unit.ocu_name,
          ocuRowSpan: unit.tasks.length,
          taskCode: tc.code,
          taskName: tc.name,
          outputs: block.outputs.map((o) => o.name),
          indicatorTexts: block.indicators.map((p) => p.text),
          hasQualityWarning: false,
          level: block.competency_level,
          knowledge: block.knowledge.map((k) => k.name),
          skills: block.skills.map((s) => s.name),
          isActive: false,
          isDone: true,
          isPending: false,
          isFirst: ti === 0,
        });
      });
    });
    return rows;
  }

  // Build from in-progress data — group tasks 2 per OCU
  const TASKS_PER_UNIT = 2;
  const rows: DocRow[] = [];
  tasks.forEach((t, i) => {
    const unitIdx = Math.floor(i / TASKS_PER_UNIT);
    const unitTaskIdx = i % TASKS_PER_UNIT;
    const unitSize = Math.min(TASKS_PER_UNIT, tasks.length - unitIdx * TASKS_PER_UNIT);

    const taskInds = indicators.filter((b) => b.task_name === t.task_name);
    const ind = taskInds[0];
    const isDone = !!ind;
    const isActive = isPerTask && i === currentTaskIndex;
    const isPending = isPerTask && i > currentTaskIndex && !isDone;
    const hasQualityWarning = taskInds.some((b) => b.quality_status === "force_accepted");

    // Spread K/S across tasks
    const kSlice = kList.slice(i * 2, i * 2 + 3);
    const sSlice = sList.slice(i * 2, i * 2 + 3);

    rows.push({
      ocuCode: `T${unitIdx + 1}`,
      ocuName: tasks
        .slice(unitIdx * TASKS_PER_UNIT, (unitIdx + 1) * TASKS_PER_UNIT)
        .map((tt) => tt.task_name.slice(0, 5))
        .join("與") + "管理",
      ocuRowSpan: unitSize,
      taskCode: `T${unitIdx + 1}.${unitTaskIdx + 1}`,
      taskName: t.task_name,
      outputs: t.outputs ?? [],
      indicatorTexts: ind?.indicator_5w2h ? [ind.indicator_5w2h] : [],
      hasQualityWarning,
      level: 3,
      knowledge: kSlice,
      skills: sSlice,
      isActive,
      isDone,
      isPending,
      isFirst: unitTaskIdx === 0,
    });
  });
  return rows;
}

// ── Cell styles ──────────────────────────────────────────────────────────────

const tdBase = "border border-gray-300 dark:border-gray-700 px-2 py-1.5 text-[10px] align-top";
const thBase = "border border-gray-300 dark:border-gray-700 px-2 py-1.5 text-[10px] font-semibold bg-gray-100 dark:bg-gray-800 text-center";

// ── Main component ──────────────────────────────────────────────────────────

export function LiveDocPanel({ profile, tasks, indicators, ksaItems, stage, currentTaskIndex, candidates, ocsDocument }: Props) {
  const rows = buildRows(tasks, indicators, ksaItems, stage, currentTaskIndex, ocsDocument);
  const attitudes = ksaItems.filter((k) => k.ksa_type === "A");
  const topCandidate = candidates[0];
  const ocsCode = ocsDocument?.ocs_profile?.ocs_code ?? topCandidate?.ocs_code ?? "—";
  const level = topCandidate?.confidence === "high" ? 4 : 3;
  const isPreview = stage === "preview";

  // Track which OCU rows have been rendered (for rowSpan)
  const renderedOcu = new Set<string>();

  return (
    <div className="flex-1 border-l flex flex-col bg-white dark:bg-background min-w-0 min-h-0 text-[10px]">
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto">
        <div className="px-4 py-3 min-w-[560px]">

          {/* Doc title */}
          <h2 className="text-sm font-bold text-center mb-3 text-gray-800 dark:text-gray-100">
            {profile.job_title} 職能基準
          </h2>

          {/* Version / header table */}
          <table className="w-full border-collapse mb-3 text-[10px]">
            <tbody>
              <tr>
                <td className={cn(thBase, "w-28 text-left")}>職能基準代碼</td>
                <td className={cn(tdBase, "w-40 font-mono")}>{ocsCode}</td>
                <td className={cn(thBase, "w-20 text-left")}>基準等級</td>
                <td className={cn(tdBase, "w-8 text-center")}>{level}</td>
                <td className={cn(thBase, "w-20 text-left")}>狀態</td>
                <td className={cn(tdBase)}>
                  <span className={cn(
                    "px-1.5 py-0.5 rounded text-[9px] font-medium",
                    isPreview ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                  )}>
                    {isPreview ? "草稿完成" : "建構中"}
                  </span>
                </td>
              </tr>
              <tr>
                <td className={cn(thBase, "text-left")}>職能基準名稱</td>
                <td className={cn(tdBase, "font-semibold")} colSpan={2}>{profile.job_title}</td>
                <td className={cn(thBase, "text-left")}>部門</td>
                <td className={cn(tdBase)} colSpan={2}>{profile.department || "—"}</td>
              </tr>
              {topCandidate && (
                <tr>
                  <td className={cn(thBase, "text-left")}>iCAP 對應</td>
                  <td className={cn(tdBase)} colSpan={5}>
                    {topCandidate.icap_title}（相似度 {Math.round(topCandidate.similarity * 100)}%・{topCandidate.confidence === "high" ? "高信心" : topCandidate.confidence === "medium" ? "中信心" : "低信心"}）
                  </td>
                </tr>
              )}
              {profile.job_summary && (
                <tr>
                  <td className={cn(thBase, "text-left")}>工作描述</td>
                  <td className={cn(tdBase)} colSpan={5}>{profile.job_summary}</td>
                </tr>
              )}
            </tbody>
          </table>

          {/* Main competency table */}
          <table className="w-full border-collapse text-[10px]">
            <thead>
              <tr className="bg-gray-200 dark:bg-gray-700">
                <th className={cn(thBase, "w-16")}>主要職責</th>
                <th className={cn(thBase, "w-20")}>工作任務</th>
                <th className={cn(thBase, "w-20")}>工作產出</th>
                <th className={cn(thBase, "w-36")}>行為指標</th>
                <th className={cn(thBase, "w-8")}>職能<br/>級別</th>
                <th className={cn(thBase)}>職能內涵<br/>(K=knowledge 知識)</th>
                <th className={cn(thBase)}>職能內涵<br/>(S=skills 技能)</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                // Full skeleton
                [1, 2, 3, 4].map((i) => (
                  <tr key={i}>
                    {i % 2 === 1 && (
                      <td className={cn(tdBase, "bg-gray-50 dark:bg-gray-800/50")} rowSpan={2}>
                        <Sk w="2/3" dim /><Sk w="1/2" dim />
                      </td>
                    )}
                    <td className={cn(tdBase)}>
                      <span className="text-gray-400 dark:text-gray-600 font-mono">T{Math.ceil(i / 2)}.{i % 2 === 1 ? 1 : 2}</span>
                      <Sk w="3/4" dim />
                    </td>
                    <td className={cn(tdBase)}><Sk w="2/3" dim /></td>
                    <td className={cn(tdBase)}><Sk dim /><Sk w="3/4" dim /></td>
                    <td className={cn(tdBase, "text-center text-gray-300")}>—</td>
                    <td className={cn(tdBase)}><Sk w="3/4" dim /><Sk w="1/2" dim /></td>
                    <td className={cn(tdBase)}><Sk w="3/4" dim /><Sk w="1/2" dim /></td>
                  </tr>
                ))
              ) : (
                rows.map((row, ri) => {
                  const showOcu = !renderedOcu.has(row.ocuCode);
                  if (showOcu) renderedOcu.add(row.ocuCode);

                  return (
                    <tr
                      key={row.taskCode}
                      className={cn(
                        row.isActive && "bg-blue-50/60 dark:bg-blue-950/20",
                        row.isDone && !row.isActive && "bg-white dark:bg-background",
                        row.isPending && "opacity-50",
                      )}
                    >
                      {/* OCU cell — only rendered for first task in unit */}
                      {showOcu && (
                        <td
                          className={cn(tdBase, "bg-gray-50 dark:bg-gray-800/50 font-medium text-center")}
                          rowSpan={row.ocuRowSpan}
                        >
                          <div className="font-mono text-[9px] text-blue-600 dark:text-blue-400 mb-1">{row.ocuCode}</div>
                          <div className="text-[10px] leading-tight">{row.ocuName}</div>
                        </td>
                      )}

                      {/* Task */}
                      <td className={cn(tdBase)}>
                        <div className="font-mono text-[9px] text-blue-600 dark:text-blue-400">{row.taskCode}</div>
                        <div className={cn(
                          "leading-tight",
                          row.isActive && "text-blue-700 dark:text-blue-300 font-medium",
                          row.isPending && "text-muted-foreground",
                        )}>
                          {row.taskName}
                        </div>
                      </td>

                      {/* Outputs */}
                      <td className={cn(tdBase)}>
                        {row.outputs.length > 0 ? (
                          row.outputs.map((o, oi) => (
                            <div key={oi} className="leading-tight mb-0.5">
                              <span className="font-mono text-[8px] text-gray-400 mr-1">
                                O{row.taskCode.slice(1)}.{oi + 1}
                              </span>
                              {o}
                            </div>
                          ))
                        ) : row.isActive ? (
                          <><Sk w="3/4" /><Sk w="1/2" /></>
                        ) : row.isPending ? (
                          <Sk dim />
                        ) : null}
                      </td>

                      {/* Indicators */}
                      <td className={cn(tdBase)}>
                        {row.indicatorTexts.length > 0 ? (
                          <>
                            {row.hasQualityWarning && (
                              <span
                                className="inline-flex items-center gap-0.5 text-[8px] text-amber-600 bg-amber-50 border border-amber-200 rounded px-1 py-0.5 mb-1"
                                title="品質分數未達標，建議人工確認"
                              >
                                ! 待確認
                              </span>
                            )}
                            {row.indicatorTexts.map((text, pi) => (
                              <div key={pi} className="mb-1 leading-relaxed">
                                <span className="font-mono text-[8px] text-gray-400 mr-1">
                                  P{row.taskCode.slice(1)}.{pi + 1}
                                </span>
                                {text}
                              </div>
                            ))}
                          </>
                        ) : row.isActive ? (
                          <><Sk /><Sk w="3/4" /><Sk w="2/3" /></>
                        ) : row.isPending ? (
                          <><Sk dim /><Sk w="2/3" dim /></>
                        ) : null}
                      </td>

                      {/* Level */}
                      <td className={cn(tdBase, "text-center font-semibold")}>
                        {row.isDone || row.isActive ? row.level : <span className="text-gray-300">—</span>}
                      </td>

                      {/* Knowledge */}
                      <td className={cn(tdBase)}>
                        {row.knowledge.length > 0 ? (
                          row.knowledge.map((k, ki) => (
                            <div key={ki} className="mb-0.5">
                              <span className="font-mono text-[8px] text-gray-400 mr-1">
                                K{String(ri * 2 + ki + 1).padStart(2, "0")}
                              </span>
                              {k}
                            </div>
                          ))
                        ) : row.isDone ? (
                          <><Sk w="3/4" /><Sk w="1/2" /></>
                        ) : row.isActive ? (
                          <><Sk /><Sk w="2/3" /></>
                        ) : row.isPending ? (
                          <><Sk dim /><Sk w="1/2" dim /></>
                        ) : null}
                      </td>

                      {/* Skills */}
                      <td className={cn(tdBase)}>
                        {row.skills.length > 0 ? (
                          row.skills.map((s, si) => (
                            <div key={si} className="mb-0.5">
                              <span className="font-mono text-[8px] text-gray-400 mr-1">
                                S{String(ri * 2 + si + 1).padStart(2, "0")}
                              </span>
                              {s}
                            </div>
                          ))
                        ) : row.isDone ? (
                          <><Sk w="3/4" /><Sk w="1/2" /></>
                        ) : row.isActive ? (
                          <><Sk /><Sk w="2/3" /></>
                        ) : row.isPending ? (
                          <><Sk dim /><Sk w="1/2" dim /></>
                        ) : null}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>

          {/* Attitudes table */}
          <table className="w-full border-collapse mt-3 text-[10px]">
            <thead>
              <tr>
                <th className={cn(thBase, "w-16 text-left")}>職能內涵</th>
                <th className={cn(thBase, "text-left")}>(A=attitude 態度)</th>
              </tr>
            </thead>
            <tbody>
              {attitudes.length > 0 ? (
                attitudes.map((a, i) => (
                  <tr key={i}>
                    <td className={cn(tdBase, "font-mono text-[9px] text-blue-600 dark:text-blue-400 whitespace-nowrap")}>
                      A{String(i + 1).padStart(2, "0")}
                    </td>
                    <td className={cn(tdBase)}>{a.content}</td>
                  </tr>
                ))
              ) : (
                [1, 2, 3].map((i) => (
                  <tr key={i}>
                    <td className={cn(tdBase, "font-mono text-[9px] text-gray-300")}>A0{i}</td>
                    <td className={cn(tdBase)}><Sk w="2/3" dim /></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          <p className="text-center text-[9px] text-gray-400 mt-4 pb-16">草稿版本・訪談中即時更新</p>
        </div>
      </div>
    </div>
  );
}
