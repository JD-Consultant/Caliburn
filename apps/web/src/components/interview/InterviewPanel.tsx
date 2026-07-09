"use client";

// 訪談面板(T11;ADR 0020 混合載體:文件常駐、面板在側;ADR 0023 回合制)。
// 逐字稿以 server 為真相(useInterview view;每回合後 invalidate 重抓)——
// 面板不自設對話 state,對齊 cache-as-state 心法。結構化決策(ask_choice)用
// 卡片勾選,開放敘事用自由輸入(上游研究 §8:decision=widget、narrative=對話)。
import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Loader2, MessageCircle, Send } from "lucide-react";

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
import type { ChoiceWidget, InterviewProgress, OcsDocument, OpenPickerWidget } from "@/types";

const PHASE_LABEL: Record<string, string> = {
  survey: "盤點", deep: "深掘", review: "總審",
  // 0028 D2 議程推導 phase(derive_phase)
  onboarding_occupation: "選職類", task_curation: "任務盤點",
  opks_deep: "深掘", attitudes_wrapup: "態度收尾",
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
  widget: ChoiceWidget; onSubmit: (text: string) => void; busy: boolean;
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

export function InterviewPanel({ profileId, doc, onApplyDoc, onWidget }: {
  profileId: string;
  doc?: OcsDocument;                     // 套用建議用(頁面的即時文件)
  onApplyDoc?: (next: OcsDocument) => void;   // = 頁面 persist(走 autosave PATCH)
  onWidget?: (w: OpenPickerWidget) => void;   // 0028:引擎 widget 指令 → 頁面開對應 picker
}) {
  const view = useInterview(profileId);
  const start = useStartInterview(profileId);
  const turn = useInterviewTurn(profileId);
  const review = useReviewInterview(profileId);
  const [input, setInput] = useState("");
  const [showReview, setShowReview] = useState(false);
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
    // 0028 D1(§16.18):open_picker 指令=**事件**,在 mutation onSuccess 派發一次。
    // 反例=存進 state 用 effect 派發:turn.data 回合後常駐+onWidget 每 render 新身分
    // → 頁面任何重渲染都重派發 → 關不掉的重彈迴圈(真人實測抓到)。
    turn.mutate(t, {
      onSuccess: (res) => {
        const w = res.widget;
        if (w && w.kind === "open_picker") onWidget?.(w);
      },
    });
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

  const pendingCount =
    view.data?.suggestions?.filter((s) => s.status === "pending").length ?? 0;

  return (
    <div className="flex h-full flex-col">
      <ProgressHeader progress={progress} />
      <div className="flex-1 space-y-3 overflow-y-auto p-3 text-sm">
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
        {widget && widget.kind !== "open_picker" && !busy && (
          <ChoiceCard widget={widget} onSubmit={send} busy={busy} />
        )}
        {turn.isError && (
          <p className="text-xs text-destructive">這回合出了點問題,再送一次即可。</p>
        )}
        <div ref={bottomRef} />
      </div>
      {/* 0028 D5/D7 載體修正:待審清單原在滾動串**頂端**、對話自動捲到底 → 清單一長
          就被推出視線(真人實測「要拉到最上面才看得到」)。改**底部常駐計數鈕**
          (輸入框上、決策當下視線內),點開才展開。 */}
      {pendingCount > 0 ? (
        <div className="border-t">
          <button
            type="button"
            onClick={() => setShowReview((v) => !v)}
            className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-muted/50"
          >
            <span className="flex items-center gap-2">
              <Badge variant="secondary">{pendingCount}</Badge>
              項 AI 建議待審
            </span>
            {showReview ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </button>
          {showReview ? (
            <div className="max-h-64 overflow-y-auto border-t p-3">
              <SuggestionReview
                suggestions={view.data?.suggestions ?? []}
                busy={review.isPending}
                onDecide={decide}
              />
            </div>
          ) : null}
        </div>
      ) : null}
      <div className="border-t">
        {/* D8 P4:meta 快速回覆——**僅流程動作**(跳過/沒有/下一題),不做內容答案 chips
            (BEI 開放故事是深度來源,內容用說的;後端 skips 語彙認得「跳過」) */}
        {turns.length > 0 ? (
          <div className="flex flex-wrap gap-1.5 px-3 pt-2">
            {["跳過這題", "沒有/不適用", "先記到這,下一題"].map((c) => (
              <Badge
                key={c}
                variant="outline"
                className={"cursor-pointer select-none "
                  + (busy ? "pointer-events-none opacity-50" : "hover:bg-muted")}
                onClick={() => send(c)}
              >
                {c}
              </Badge>
            ))}
          </div>
        ) : null}
        <form
          className="flex gap-2 p-3"
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
    </div>
  );
}
