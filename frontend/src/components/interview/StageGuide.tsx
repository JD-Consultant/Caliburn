"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ReadinessDetail, Stage, Task } from "@/types";
import type { ElementType } from "react";
import {
  CheckCircle2,
  ClipboardCheck,
  FileText,
  ListChecks,
  MessageSquareText,
  SearchCheck,
  Sparkles,
} from "lucide-react";

interface Props {
  stage: Stage;
  currentTask?: Task;
  currentTaskIndex: number;
  taskCount: number;
  missingFields?: string[];
  readiness?: ReadinessDetail;
  streaming?: boolean;
}

const FIELD_LABEL: Record<string, string> = {
  situation: "工作情境",
  purpose: "目的",
  collaborators: "協作者",
  stakeholders: "利害關係人",
  tools: "工具",
  workflow_steps: "工作步驟",
  outputs: "產出",
  quality_standards: "品質標準",
  time_standards: "時效標準",
};

const STAGE_LABEL: Record<Stage, string> = {
  basic_info: "建立脈絡",
  icap_ref: "iCAP 比對",
  interview: "基本訪談",
  task_extraction: "任務確認",
  responsibility_grouping: "主要職責",
  star: "真實案例",
  five_w2h: "工作細節",
  indicator: "行為指標",
  ksa: "K/S/A 整理",
  preview: "文件完成",
};

const STAGE_ICON: Record<Stage, ElementType> = {
  basic_info: SearchCheck,
  icap_ref: SearchCheck,
  interview: MessageSquareText,
  task_extraction: ListChecks,
  responsibility_grouping: ListChecks,
  star: ClipboardCheck,
  five_w2h: ClipboardCheck,
  indicator: Sparkles,
  ksa: Sparkles,
  preview: FileText,
};

export function StageGuide({
  stage,
  currentTask,
  currentTaskIndex,
  taskCount,
  missingFields = [],
  readiness,
  streaming,
}: Props) {
  const Icon = STAGE_ICON[stage];
  const taskPosition =
    currentTask && taskCount > 0 ? `${Math.min(currentTaskIndex + 1, taskCount)} / ${taskCount}` : null;
  const guide = buildGuide(stage, currentTask, missingFields, readiness, streaming);

  return (
    <div className="mb-3 rounded-lg border bg-background px-3 py-2.5 text-sm shadow-sm">
      <div className="flex items-start gap-2.5">
        <div
          className={cn(
            "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md",
            streaming ? "bg-blue-50 text-blue-600" : "bg-muted text-muted-foreground"
          )}
        >
          <Icon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-medium">{guide.title}</span>
            <Badge variant="outline" className="h-5 px-1.5 text-[10px]">
              {STAGE_LABEL[stage]}
            </Badge>
            {taskPosition && (
              <Badge variant="secondary" className="h-5 px-1.5 text-[10px]">
                任務 {taskPosition}
              </Badge>
            )}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{guide.action}</p>
          {guide.next && (
            <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <CheckCircle2 className="size-3 text-emerald-600" />
              <span>{guide.next}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function buildGuide(
  stage: Stage,
  currentTask?: Task,
  missingFields: string[] = [],
  readiness?: ReadinessDetail,
  streaming?: boolean,
) {
  const taskName = currentTask?.task_name;
  const missingText = missingFields.map((field) => FIELD_LABEL[field] ?? field).join("、");

  if (streaming) {
    return {
      title: "AI 正在處理你的回覆",
      action: "先不用輸入，等這一輪回覆完成後再補充或確認。",
      next: "完成後會更新目前階段與右側預覽",
    };
  }

  switch (stage) {
    case "basic_info":
    case "icap_ref":
      return {
        title: "先建立職務脈絡",
        action: "系統會先比對相近的 iCAP 職能基準，接著開始訪談。",
        next: "下一步會進入基本訪談",
      };
    case "interview": {
      const pct = readiness ? Math.round(readiness.score * 100) : 0;
      return {
        title: "描述你的日常工作",
        action: readiness
          ? `目前資訊完整度約 ${pct}%。請補充主要任務、產出、工具、協作對象或品質標準。`
          : "請用自己的話描述日常工作、常見任務、產出、使用工具與協作對象。",
        next: "資訊足夠後會整理任務清單給你確認",
      };
    }
    case "task_extraction":
      return {
        title: "檢查 AI 整理的任務清單",
        action: "請確認任務是否正確；如果有遺漏、命名不準或分類錯誤，直接在下方補充。",
        next: "確認後會整理主要職責分組",
      };
    case "responsibility_grouping":
      return {
        title: "檢查主要職責分組",
        action: "請確認主要職責名稱與任務歸屬是否合理；如果要合併、拆分或移動任務，直接在下方說明。",
        next: "確認後會逐一進入深度訪談",
      };
    case "star":
      return {
        title: taskName ? `分享「${taskName}」的真實案例` : "分享一個真實案例",
        action: "請描述一次具體工作情境：當時發生什麼、你的目標、你怎麼做、最後結果如何。",
        next: "案例完整後會補齊工作細節",
      };
    case "five_w2h":
      return {
        title: taskName ? `補齊「${taskName}」的工作細節` : "補齊工作細節",
        action: missingText
          ? `這一步主要需要補充：${missingText}。`
          : "請補充這項任務的目的、協作對象、工具、步驟、產出與品質/時效標準。",
        next: "資料足夠後會產生行為指標",
      };
    case "indicator":
      return {
        title: "產生行為指標",
        action: "AI 正在把任務資料轉成可觀察、可評估的行為指標。",
        next: "完成後會進入下一個任務或整理 K/S/A",
      };
    case "ksa":
      return {
        title: "整理知識、技能與態度",
        action: "AI 正在根據訪談內容與 iCAP 參考整理 K/S/A。",
        next: "完成後可以預覽職務文件",
      };
    case "preview":
      return {
        title: "職務文件已完成",
        action: "你可以查看報告、匯出文件，或在定版前檢查待確認內容。",
        next: "定版後會保存目前版本",
      };
  }
}
