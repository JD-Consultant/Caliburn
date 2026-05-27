"use client";

import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { Stage, ReadinessDetail } from "@/types";

const STAGES: { key: Stage; label: string }[] = [
  { key: "icap_ref", label: "iCAP 比對" },
  { key: "interview", label: "基本訪談" },
  { key: "task_extraction", label: "任務確認" },
  { key: "responsibility_grouping", label: "主要職責" },
  { key: "star", label: "STAR 深訪" },
  { key: "five_w2h", label: "5W2H 補充" },
  { key: "indicator", label: "行為指標" },
  { key: "ksa", label: "K/S/A 整理" },
  { key: "preview", label: "完成預覽" },
];

const STAGE_INDEX: Record<string, number> = Object.fromEntries(
  STAGES.map((s, i) => [s.key, i])
);

interface Props {
  stage: Stage;
  readiness?: ReadinessDetail;
}

export function ProgressTracker({ stage, readiness }: Props) {
  const current = STAGE_INDEX[stage] ?? 0;
  const showReadiness = stage === "interview" && readiness && readiness.score > 0;

  return (
    <div className="px-4 py-3">
      {/* Stage pills */}
      <div className="flex items-center gap-1 overflow-x-auto">
        {STAGES.map((s, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <div key={s.key} className="flex items-center gap-1 shrink-0">
              <div
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors",
                  done && "bg-emerald-100 text-emerald-700",
                  active && "bg-blue-600 text-white shadow-sm",
                  !done && !active && "bg-muted text-muted-foreground"
                )}
              >
                {done && <span>✓</span>}
                {s.label}
              </div>
              {i < STAGES.length - 1 && (
                <div className={cn("w-4 h-px", i < current ? "bg-emerald-300" : "bg-border")} />
              )}
            </div>
          );
        })}
      </div>

      {/* Readiness meter — only during interview stage */}
      {showReadiness && (
        <div className="mt-2.5 pt-2.5 border-t border-dashed">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-xs text-muted-foreground shrink-0">訪談完整度</span>
            <Progress value={Math.round(readiness.score * 100)} className="h-1.5 flex-1" />
            <span className="text-xs font-medium text-blue-600 shrink-0 w-8 text-right">
              {Math.round(readiness.score * 100)}%
            </span>
          </div>
          {readiness.missing_signals.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {readiness.missing_signals.map((s) => (
                <Badge
                  key={s.key}
                  variant="outline"
                  className="text-[10px] px-1.5 py-0 h-4 text-orange-500 border-orange-200"
                >
                  待補：{s.label.split("（")[0]}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
