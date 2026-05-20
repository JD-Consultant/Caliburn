"use client";

import { useState } from "react";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ChevronRight,
  ChevronDown,
  CheckCircle2,
  Circle,
  Loader2,
} from "lucide-react";
import type { Task, Stage, ReadinessDetail, BehaviorIndicator } from "@/types";
import { cn } from "@/lib/utils";

interface Props {
  tasks: Task[];
  stage?: Stage;
  readiness?: ReadinessDetail;
  currentTaskIndex?: number;
  behaviorIndicators?: BehaviorIndicator[];
}

const FIELD_LABEL: Record<string, string> = {
  situation: "情境",
  purpose: "目的",
  stakeholders: "相關人員",
  tools: "工具",
  outputs: "產出",
  quality_standards: "品質標準",
};

const SIGNAL_SHORT: Record<string, string> = {
  tasks: "工作任務",
  outputs: "工作產出",
  tools: "使用工具",
  stakeholders: "協作對象",
  quality: "品質標準",
  context: "工作頻率",
};

const PER_TASK_STAGES = new Set<Stage>(["star", "five_w2h", "indicator"]);

interface TaskStageStatus {
  isActive: boolean;
  isDone: boolean;
  isPending: boolean;
  starDone: boolean;
  fiveW2HDone: boolean;
  indicatorDone: boolean;
  indicatorScore?: number;
  starActive: boolean;
  fiveW2HActive: boolean;
  indicatorActive: boolean;
}

function getTaskStageStatus(
  task: Task,
  index: number,
  currentTaskIndex: number,
  stage: Stage,
  behaviorIndicators: BehaviorIndicator[],
): TaskStageStatus {
  const indicator = behaviorIndicators.find(
    (b) => b.task_name === task.task_name,
  );
  const hasIndicator = !!indicator;
  const hasStarCase = !!(task.star_case?.situation && task.star_case?.action);
  const isActive = index === currentTaskIndex;

  return {
    isActive,
    isDone: hasIndicator,
    isPending: index > currentTaskIndex && !hasIndicator,
    starDone: hasStarCase || hasIndicator,
    fiveW2HDone: hasIndicator,
    indicatorDone: hasIndicator,
    indicatorScore: indicator?.quality_score,
    starActive: isActive && stage === "star",
    fiveW2HActive: isActive && stage === "five_w2h",
    indicatorActive: isActive && stage === "indicator",
  };
}

function StagePill({
  label,
  done,
  active,
  score,
}: {
  label: string;
  done: boolean;
  active: boolean;
  score?: number;
}) {
  if (done) {
    return (
      <span className="inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 font-medium">
        <CheckCircle2 className="w-2.5 h-2.5" />
        {label}
        {score !== undefined && ` ${Math.round(score * 100)}%`}
      </span>
    );
  }
  if (active) {
    return (
      <span className="inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300 font-medium">
        <Loader2 className="w-2.5 h-2.5 animate-spin" />
        {label}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground font-medium">
      {label}
    </span>
  );
}

export function TaskPanel({
  tasks,
  stage,
  readiness,
  currentTaskIndex = 0,
  behaviorIndicators = [],
}: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const isPerTaskStage = stage !== undefined && PER_TASK_STAGES.has(stage);
  const doneCount = behaviorIndicators.length;

  // During interview stage with no tasks: show readiness breakdown panel
  if (!tasks.length) {
    if (stage !== "interview" || !readiness || readiness.score === 0)
      return null;

    return (
      <div className="w-72 border-l flex flex-col bg-background">
        <div className="px-4 py-3 border-b">
          <h3 className="text-sm font-semibold">訪談進度</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            AI 正在收集任務所需資訊
          </p>
        </div>
        <div className="p-4 space-y-4">
          {/* Score bar */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-muted-foreground">資訊完整度</span>
              <span className="text-xs font-semibold text-blue-600">
                {Math.round(readiness.score * 100)}%
              </span>
            </div>
            <Progress value={Math.round(readiness.score * 100)} className="h-2" />
            {readiness.ready ? (
              <p className="text-[11px] text-emerald-600 mt-1.5">
                資訊已足夠，即將整理任務清單
              </p>
            ) : (
              <p className="text-[11px] text-muted-foreground mt-1.5">
                達到 70% 後將自動整理任務
              </p>
            )}
          </div>

          {/* Signal checklist */}
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground mb-2">
              資訊收集狀況
            </p>
            {readiness.signals.map((s) => (
              <div key={s.key} className="flex items-start gap-2">
                {s.detected ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                ) : (
                  <Circle className="w-3.5 h-3.5 text-muted-foreground/40 shrink-0 mt-0.5" />
                )}
                <div className="flex-1 min-w-0">
                  <span
                    className={cn(
                      "text-xs",
                      s.detected ? "text-foreground" : "text-muted-foreground",
                    )}
                  >
                    {SIGNAL_SHORT[s.key] ?? s.label.split("（")[0]}
                  </span>
                  {s.detected && s.examples.length > 0 && (
                    <p className="text-[10px] text-muted-foreground truncate mt-0.5">
                      {s.examples.slice(0, 2).join("、")}
                    </p>
                  )}
                </div>
                {s.weight > 1 && (
                  <Badge
                    variant="outline"
                    className="text-[9px] px-1 py-0 h-3.5 shrink-0"
                  >
                    重要
                  </Badge>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-72 border-l flex flex-col bg-background">
      <div className="px-4 py-3 border-b">
        <h3 className="text-sm font-semibold">
          {isPerTaskStage ? "任務深度訪談" : "已萃取任務"}
        </h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          {isPerTaskStage
            ? `${doneCount} / ${tasks.length} 完成`
            : `${tasks.length} 個任務`}
        </p>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-3 space-y-2">
          {tasks.map((task, index) => {
            const stageStatus = isPerTaskStage
              ? getTaskStageStatus(
                  task,
                  index,
                  currentTaskIndex,
                  stage,
                  behaviorIndicators,
                )
              : null;
            const pct = task.completeness_pct ?? 0;
            const isOpen = expanded === task.task_name;

            return (
              <div
                key={task.task_name}
                className={cn(
                  "rounded-lg border bg-card overflow-hidden transition-colors",
                  stageStatus?.isActive &&
                    "border-blue-400 dark:border-blue-600 shadow-sm",
                  stageStatus?.isDone &&
                    "border-emerald-200 dark:border-emerald-800 bg-emerald-50/30 dark:bg-emerald-950/10",
                  stageStatus?.isPending && "opacity-50",
                )}
              >
                <button
                  className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-muted/50 transition-colors"
                  onClick={() =>
                    setExpanded(isOpen ? null : task.task_name)
                  }
                >
                  {/* Status icon */}
                  {stageStatus ? (
                    stageStatus.isDone ? (
                      <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-500" />
                    ) : stageStatus.isActive ? (
                      <div className="w-3.5 h-3.5 shrink-0 rounded-full border-2 border-blue-500 bg-blue-100 dark:bg-blue-950" />
                    ) : (
                      <Circle className="w-3.5 h-3.5 shrink-0 text-muted-foreground/30" />
                    )
                  ) : isOpen ? (
                    <ChevronDown className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
                  )}

                  <div className="flex-1 min-w-0">
                    <p
                      className={cn(
                        "text-xs font-medium truncate",
                        stageStatus?.isActive &&
                          "text-blue-700 dark:text-blue-300",
                        stageStatus?.isDone && "text-emerald-700 dark:text-emerald-300",
                      )}
                    >
                      {task.task_name}
                    </p>

                    {stageStatus ? (
                      <div className="flex items-center gap-1 mt-1">
                        <StagePill
                          label="STAR"
                          done={stageStatus.starDone}
                          active={stageStatus.starActive}
                        />
                        <StagePill
                          label="5W2H"
                          done={stageStatus.fiveW2HDone}
                          active={stageStatus.fiveW2HActive}
                        />
                        <StagePill
                          label="指標"
                          done={stageStatus.indicatorDone}
                          active={stageStatus.indicatorActive}
                          score={stageStatus.indicatorScore}
                        />
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 mt-1">
                        <Progress value={pct} className="h-1.5 flex-1" />
                        <span className="text-[10px] text-muted-foreground w-7 shrink-0">
                          {pct}%
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Collapse arrow for per-task stage cards */}
                  {stageStatus && (
                    <span className="shrink-0">
                      {isOpen ? (
                        <ChevronDown className="w-3 h-3 text-muted-foreground/50" />
                      ) : (
                        <ChevronRight className="w-3 h-3 text-muted-foreground/30" />
                      )}
                    </span>
                  )}
                </button>

                {/* Expanded content */}
                {isOpen && (
                  <div className="px-3 pb-3 space-y-2 border-t bg-muted/20">
                    {/* STAR case preview */}
                    {task.star_case?.situation && (
                      <div className="pt-2">
                        <p className="text-[10px] text-muted-foreground mb-0.5">
                          STAR 情境
                        </p>
                        <p className="text-[11px] line-clamp-2 text-foreground/80">
                          {task.star_case.situation}
                        </p>
                      </div>
                    )}

                    {/* Behavior indicator preview */}
                    {stageStatus?.indicatorDone &&
                      (() => {
                        const ind = behaviorIndicators.find(
                          (b) => b.task_name === task.task_name,
                        );
                        return ind?.indicator_5w2h ? (
                          <div className="pt-1">
                            <p className="text-[10px] text-muted-foreground mb-0.5">
                              行為指標
                            </p>
                            <p className="text-[11px] line-clamp-3 text-foreground/80">
                              {ind.indicator_5w2h}
                            </p>
                          </div>
                        ) : null;
                      })()}

                    {/* Missing fields (task_extraction / non-per-task stages) */}
                    {!stageStatus &&
                      task.missing_fields &&
                      task.missing_fields.length > 0 && (
                        <div className="pt-2">
                          <p className="text-[10px] text-muted-foreground mb-1">
                            待補欄位
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {task.missing_fields.map((f) => (
                              <Badge
                                key={f}
                                variant="outline"
                                className="text-[10px] px-1.5 py-0 h-4 text-orange-600 border-orange-200"
                              >
                                {FIELD_LABEL[f] ?? f}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                    {task.category && (
                      <p className="text-[11px] text-muted-foreground pt-1">
                        類別：{task.category}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
}
