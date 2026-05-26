"use client";

import { cn } from "@/lib/utils";
import type { AiMessageKind, InterviewMessage } from "@/types";

interface Props {
  message: InterviewMessage;
  streaming?: boolean;
}

export function ChatBubble({ message, streaming }: Props) {
  const isAi = message.role === "ai";
  const kind = message.extra_data?.kind;
  const label = kind ? KIND_LABEL[kind] : null;

  return (
    <div className={cn("flex gap-3 px-4 py-2", isAi ? "justify-start" : "justify-end")}>
      {isAi && (
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs shrink-0 mt-0.5">
          AI
        </div>
      )}
      <div
        className={cn(
          "max-w-[75%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap leading-relaxed",
          isAi
            ? cn("bg-muted text-foreground rounded-tl-sm", KIND_STYLE[kind ?? "question"])
            : "bg-blue-600 text-white rounded-tr-sm"
        )}
      >
        {isAi && label && (
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide opacity-70">
            {label}
          </div>
        )}
        {message.content}
        {streaming && (
          <span className="inline-block w-1.5 h-4 bg-current ml-0.5 animate-pulse align-middle" />
        )}
      </div>
    </div>
  );
}

const KIND_LABEL: Record<AiMessageKind, string> = {
  summary: "整理結果",
  question: "下一個問題",
  status: "處理狀態",
  error: "錯誤",
};

const KIND_STYLE: Record<AiMessageKind, string> = {
  summary: "border border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/20 dark:text-emerald-50",
  question: "bg-muted text-foreground",
  status: "border border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-50",
  error: "border border-destructive/30 bg-destructive/10 text-destructive",
};
