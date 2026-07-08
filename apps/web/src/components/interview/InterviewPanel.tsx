"use client";

// 訪談面板(T11;ADR 0020 混合載體:文件常駐、面板在側;ADR 0023 回合制)。
// 逐字稿以 server 為真相(useInterview view;每回合後 invalidate 重抓)——
// 面板不自設對話 state,對齊 cache-as-state 心法。結構化決策(ask_choice)用
// 卡片勾選,開放敘事用自由輸入(上游研究 §8:decision=widget、narrative=對話)。
import { useEffect, useRef, useState } from "react";
import { Loader2, MessageCircle, Send } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { SuggestionReview } from "@/components/interview/SuggestionReview";
import {
  useInterview,
  useInterviewTurn,
  useReviewInterview,
  useStartInterview,
} from "@/hooks/useInterview";
import { applyAccepted } from "@/lib/interviewDoc";
import type { InterviewProgress, InterviewWidget, OcsDocument } from "@/types";

const PHASE_LABEL: Record<string, string> = {
  survey: "盤點", deep: "深掘", review: "總審",
};

function ProgressHeader({ progress }: { progress: InterviewProgress | null }) {
  if (!progress) return null;
  // v2:進度=覆蓋率(帳本 filled/required),取代 v1 task_index/total
  const { filled = 0, required = 0 } = progress.coverage ?? {};
  const pct = required ? Math.round((filled / required) * 100) : 0;
  return (
    <div className="space-y-1 border-b p-3">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {PHASE_LABEL[progress.phase] ?? progress.phase}
          {progress.phase !== "review" && required > 0 && ` · 已補 ${filled}/${required}`}
        </span>
      </div>
      <Progress value={progress.phase === "review" ? 100 : pct} className="h-1.5" />
    </div>
  );
}

function ChoiceCard({ widget, onSubmit, busy }: {
  widget: InterviewWidget; onSubmit: (text: string) => void; busy: boolean;
}) {
  const [picked, setPicked] = useState<string[]>([]);
  return (
    <div className="rounded-md border bg-muted/40 p-3 text-sm">
      <p className="mb-2">{widget.question}</p>
      <div className="flex flex-wrap gap-2">
        {widget.options.map((o) => (
          <Badge
            key={o}
            variant={picked.includes(o) ? "default" : "outline"}
            className="cursor-pointer select-none"
            onClick={() =>
              setPicked((p) => (p.includes(o) ? p.filter((x) => x !== o) : [...p, o]))}
          >
            {o}
          </Badge>
        ))}
      </div>
      <Button
        size="sm" className="mt-2" disabled={busy || picked.length === 0}
        onClick={() => onSubmit(`我選:${picked.join("、")}`)}
      >
        送出選擇
      </Button>
    </div>
  );
}

export function InterviewPanel({ profileId, doc, onApplyDoc }: {
  profileId: string;
  doc?: OcsDocument;                     // 套用建議用(頁面的即時文件)
  onApplyDoc?: (next: OcsDocument) => void;   // = 頁面 persist(走 autosave PATCH)
}) {
  const view = useInterview(profileId);
  const start = useStartInterview(profileId);
  const turn = useInterviewTurn(profileId);
  const review = useReviewInterview(profileId);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const turns = view.data?.turns ?? [];
  const progress: InterviewProgress | null =
    turn.data?.progress ?? (start.data ? start.data.progress : null)
    ?? (view.data ? { phase: view.data.phase, coverage: { filled: 0, required: 0 } } : null);
  const widget = turn.data?.widget ?? null;
  const busy = turn.isPending || start.isPending;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length, busy]);

  const send = (text: string) => {
    const t = text.trim();
    if (!t || busy) return;
    setInput("");
    turn.mutate(t);
  };

  // 尚無 session(GET 404)→ 開始畫面
  const notStarted = view.isError || (!view.data && !view.isLoading);
  if (notStarted && !start.data) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <MessageCircle className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          讓 AI 顧問陪你把每個任務的細節問出來——文件會邊談邊長。
        </p>
        <Button onClick={() => start.mutate()} disabled={start.isPending}>
          {start.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
          開始訪談
        </Button>
        {start.isError && (
          <p className="text-xs text-destructive">
            無法開始訪談,請稍後再試。
          </p>
        )}
      </div>
    );
  }

  // 批審(ADR 0025 節點批審):轉狀態 → 前端 applyAccepted(含 add_task/add_duty 落地)
  // → 頁面 persist(既有寫入路徑)。renumber 由 ocsDoc 處理(前端職權)。
  const decide = (accept: string[], reject: string[]) => {
    review.mutate({ accept, reject }, {
      onSuccess: (res) => {
        if (!doc || !onApplyDoc || res.accepted.length === 0) return;
        const out = applyAccepted(doc, res.accepted);
        if (out.applied.length > 0) onApplyDoc(out.doc);
      },
    });
  };

  return (
    <div className="flex h-full flex-col">
      <ProgressHeader progress={progress} />
      <div className="flex-1 space-y-3 overflow-y-auto p-3 text-sm">
        {(view.data?.suggestions?.some((s) => s.status === "pending") ?? false) && (
          <SuggestionReview
            suggestions={view.data!.suggestions}
            busy={review.isPending}
            onDecide={decide}
          />
        )}
        {turns.length === 0 && start.data && (
          <p className="rounded-md bg-muted/40 p-2">{start.data.greeting}</p>
        )}
        {turns.map((t) => (
          <div
            key={t.seq}
            className={t.role === "employee"
              ? "ml-6 rounded-md bg-primary/10 p-2"
              : "mr-6 rounded-md bg-muted/40 p-2 whitespace-pre-line"}
          >
            {t.text}
          </div>
        ))}
        {busy && (
          <div className="mr-6 flex items-center gap-2 p-2 text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> 顧問思考中…
          </div>
        )}
        {widget && !busy && (
          <ChoiceCard widget={widget} onSubmit={send} busy={busy} />
        )}
        {turn.isError && (
          <p className="text-xs text-destructive">這回合出了點問題,再送一次即可。</p>
        )}
        <div ref={bottomRef} />
      </div>
      <form
        className="flex gap-2 border-t p-3"
        onSubmit={(e) => { e.preventDefault(); send(input); }}
      >
        <input
          className="flex-1 rounded-md border bg-background px-3 py-2 text-sm"
          placeholder="想到什麼說什麼…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
        />
        <Button type="submit" size="icon" disabled={busy || !input.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}
