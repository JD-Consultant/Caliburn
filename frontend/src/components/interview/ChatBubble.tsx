"use client";

import { cn } from "@/lib/utils";
import type { InterviewMessage } from "@/types";

interface Props {
  message: InterviewMessage;
  streaming?: boolean;
}

export function ChatBubble({ message, streaming }: Props) {
  const isAi = message.role === "ai";

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
            ? "bg-muted text-foreground rounded-tl-sm"
            : "bg-blue-600 text-white rounded-tr-sm"
        )}
      >
        {message.content}
        {streaming && (
          <span className="inline-block w-1.5 h-4 bg-current ml-0.5 animate-pulse align-middle" />
        )}
      </div>
    </div>
  );
}
