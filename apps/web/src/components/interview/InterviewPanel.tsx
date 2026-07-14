"use client";

// 訪談面板(T9 改造;ADR 0030 §6.5/§6.6):對話(打字機動畫)+議程三態+進度+
// 「正在整理…」狀態指示。AI 寫入的審閱=表格內 `_pending` ✓/✗(T8)——
// 側欄只保留待審計數鈕(點擊捲動到表格工具列);SuggestionReview 掛點已拆(T12 刪檔)。
// 逐字稿以 server 為真相(useInterview view;每回合後 invalidate 重抓)。
import { useEffect, useRef, useState } from "react";
import { Loader2, MessageCircle, Send } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { AgendaList } from "@/components/interview/AgendaList";
import { OccupationSuggestCard } from "@/components/interview/OccupationSuggestCard";
import {
  useFinishInterview, useInterview, useInterviewTurn, useStartInterview,
} from "@/hooks/useInterview";
import {
  chipOptions, docHasTasks, hasMaterial, isIntakeInvite, occSuggestions,
  typewriterDone, typewriterSlice,
} from "@/lib/interviewUi";
import { postReviewEvents } from "@/lib/api";
import { listPending } from "@/lib/ocsDoc";
import type {
  ChoiceWidget, InterviewProgress, OccPrecheckItem, OcsDocument, OpenPickerWidget,
} from "@/types";

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

// 打字機泡泡(§6.6 呈現節奏):前端逐字顯示已回全文(體感字元級 streaming,
// 零後端改動;真 SSE 記縫)。點擊即全顯。
function TypewriterBubble({ text }: { text: string }) {
  const [tick, setTick] = useState(0);
  const done = typewriterDone(text, tick);
  useEffect(() => {
    if (done) return;
    const id = setInterval(() => setTick((t) => t + 1), 30);
    return () => clearInterval(id);
  }, [done]);
  return (
    <div
      className="mr-6 cursor-pointer whitespace-pre-line rounded-md bg-muted/40 p-2"
      title={done ? undefined : "點擊顯示全文"}
      onClick={() => setTick(Math.ceil(text.length))}
    >
      {typewriterSlice(text, tick)}
      {!done ? <span className="animate-pulse">▍</span> : null}
    </div>
  );
}

// intake 邀請卡(0032):開盤的手永遠是人——兩出口:開任務盤(頁面開全域盤)/
// 用聊的就好(task_board_dismissed 無聲記帳 → 顧問下回合改口頭盤點,不再邀請)。
function IntakeInviteCard({ onOpen, onDecline }: {
  onOpen: () => void; onDecline: () => void;
}) {
  return (
    <div className="rounded-md border border-sky-200 bg-sky-50/50 p-3 text-sm dark:border-sky-900 dark:bg-sky-950/30">
      <p className="mb-2">
        想快一點的話,可以先打開任務盤,勾一下你大概有做哪些(約 2 分鐘)——
        我再逐條跟你聊細節;想直接用聊的也行。
      </p>
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={onOpen}>開任務盤(約 2 分鐘)</Button>
        <Button size="sm" variant="ghost" onClick={onDecline}>用聊的就好</Button>
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground">
        之後隨時可從上方工具列「選工作任務」自己開。
      </p>
    </div>
  );
}

// 封閉題卡(AskUserQuestion 樣式):單選 chips+推薦標記+永遠附「其他(自由輸入)」;
function ChoiceCard({ widget, onSubmit, busy }: {
  widget: ChoiceWidget; onSubmit: (text: string) => void; busy: boolean;
}) {
  const [other, setOther] = useState("");
  const chips = chipOptions(widget.options, widget.recommended);
  return (
    <div className="rounded-md border bg-muted/40 p-3 text-sm">
      <p className="mb-2">{widget.question}</p>
      <div className="flex flex-wrap gap-2">
        {chips.map((c) => (
          <Badge
            key={c.label}
            variant="outline"
            className={"cursor-pointer select-none hover:bg-muted "
              + (busy ? "pointer-events-none opacity-50" : "")}
            onClick={() => onSubmit(c.label)}
          >
            {c.label}
            {c.recommended ? (
              <span className="ml-1 rounded bg-emerald-100 px-1 text-[9px] text-emerald-700">推薦</span>
            ) : null}
          </Badge>
        ))}
      </div>
      <form
        className="mt-2 flex gap-2"
        onSubmit={(e) => { e.preventDefault(); if (other.trim()) onSubmit(other.trim()); }}
      >
        <input
          className="flex-1 rounded-md border bg-background px-2 py-1 text-xs"
          placeholder="其他(自由輸入)…"
          value={other}
          onChange={(e) => setOther(e.target.value)}
          disabled={busy}
        />
        <Button type="submit" size="sm" variant="outline" disabled={busy || !other.trim()}>
          送出
        </Button>
      </form>
    </div>
  );
}

export function InterviewPanel({
  profileId, doc, onWidget, referenceEmpty, onOpenReference, onOpenTaskBoard,
}: {
  profileId: string;
  doc?: OcsDocument;                          // 待審計數(文件內 _pending)資料源
  onWidget?: (w: OpenPickerWidget) => void;   // 0028:引擎 widget 指令 → 頁面開對應 picker
  referenceEmpty?: boolean;                   // 0031:參考集合空 → 顯示常駐〔待選〕chip
  onOpenReference?: () => void;               // chip 重入口 → 頁面開〔選參考〕modal
  onOpenTaskBoard?: () => void;               // 0032 intake 卡「開任務盤」→ 頁面開全域盤
}) {
  const view = useInterview(profileId);
  const start = useStartInterview(profileId);
  const turn = useInterviewTurn(profileId);
  const finish = useFinishInterview(profileId);
  const [input, setInput] = useState("");
  const [lastSent, setLastSent] = useState("");
  const [finishDismissed, setFinishDismissed] = useState(false);
  // 0031 A 案:職類建議卡進對話流(不彈窗);0032:intake 邀請卡同款(AI 不彈盤)
  const [occCard, setOccCard] = useState<OccPrecheckItem[] | null>(null);
  const [intakeCard, setIntakeCard] = useState(false);
  const [cardError, setCardError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  // 打字機只給「送出後新到的」顧問回合(基準線在 send 事件設定);
  // 歷史逐字稿與重載直接全顯,不重播動畫。
  const [animateAfter, setAnimateAfter] = useState<number | null>(null);

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
    setLastSent(t);
    setAnimateAfter(turns.length > 0 ? turns[turns.length - 1].seq : 0);
    // 0028 D1(§16.18):open_picker 指令=**事件**,在 mutation onSuccess 派發一次。
    // 0031:occupation 有建議 → 職類卡;0032:task_board_intake → 邀請卡(不彈盤);
    // 其餘照舊 onWidget(頁面開 picker)。
    turn.mutate(t, {
      onSuccess: (res) => {
        const w = res.widget;
        if (!w || w.kind !== "open_picker") return;
        const sugg = occSuggestions(w);
        if (sugg.length > 0) setOccCard(sugg);
        else if (isIntakeInvite(w)) setIntakeCard(true);
        else onWidget?.(w);
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

  // T8/T9:待審=文件內 _pending;計數鈕捲動定位到表格工具列(建議層已拆)。
  const pendingCount = doc ? listPending(doc).length : 0;

  return (
    <div className="flex h-full flex-col">
      <ProgressHeader progress={progress} />
      {/* 0031 常駐 chip:參考集合空=結構化鏈路還沒起跑;關卡片後這裡是唯一重入口 */}
      {referenceEmpty && !occCard ? (
        <button
          type="button"
          onClick={() => onOpenReference?.()}
          className="flex items-center gap-1.5 border-b bg-amber-50/60 px-3 py-1.5 text-left text-xs text-amber-800 hover:bg-amber-100/60 dark:bg-amber-950/30 dark:text-amber-200"
        >
          📌 待選:職能基準參考——選了才有官方任務清單當底稿〔開啟〕
        </button>
      ) : null}
      <AgendaList items={view.data?.agenda ?? []} />
      <div className="flex-1 space-y-3 overflow-y-auto p-3 text-sm">
        {turns.length === 0 && start.data && (
          <p className="rounded-md bg-muted/40 p-2 whitespace-pre-line">{start.data.greeting}</p>
        )}
        {turns.map((t) =>
          t.role === "employee" ? (
            <div key={t.seq} className="ml-6 rounded-md bg-primary/10 p-2">{t.text}</div>
          ) : t.seq > (animateAfter ?? Number.POSITIVE_INFINITY) ? (
            <TypewriterBubble key={t.seq} text={t.text} />
          ) : (
            <div key={t.seq} className="mr-6 whitespace-pre-line rounded-md bg-muted/40 p-2">
              {t.text}
            </div>
          ),
        )}
        {busy && (
          <div className="mr-6 space-y-1 p-2 text-muted-foreground">
            <div className="flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> 顧問思考中…
            </div>
            {hasMaterial(lastSent) ? (
              <div className="pl-5 text-xs">正在整理你剛說的內容…</div>
            ) : null}
          </div>
        )}
        {widget && widget.kind !== "open_picker" && !busy && (
          <ChoiceCard widget={widget} onSubmit={send} busy={busy} />
        )}
        {/* 0031 職類建議卡:確認=寫參考集合/其他=回聊天/✕=收合+dismissed 記帳 */}
        {occCard && !busy ? (
          <OccupationSuggestCard
            profileId={profileId}
            items={occCard}
            onDone={() => { setOccCard(null); setCardError(null); }}
            onOther={() => { setOccCard(null); inputRef.current?.focus(); }}
            onError={setCardError}
          />
        ) : null}
        {cardError ? <p className="text-xs text-destructive">{cardError}</p> : null}
        {/* 0032 intake 邀請卡:文件一有任務即自癒不再渲染(docHasTasks 雙保險) */}
        {intakeCard && !docHasTasks(doc) && !busy ? (
          <IntakeInviteCard
            onOpen={() => { setIntakeCard(false); onOpenTaskBoard?.(); }}
            onDecline={() => {
              // 無聲記帳(失敗不擋 UI;§6.3 同款)——顧問下回合知情改口頭盤點
              postReviewEvents(profileId, [
                { doc_path: "board:tasks", decision: "task_board_dismissed" },
              ]).catch(() => {});
              setIntakeCard(false);
            }}
          />
        ) : null}
        {/* T10 收尾三訊號 → 建議收尾(不強制;coverage 全綠/疲勞/輪數預算任一)
            +0032 T5e 補漏 offer:尾聲開盤掃官方清單(盤=人開,checklist 補回憶缺口) */}
        {turn.data?.suggest_finish && !finish.data && !busy ? (
          <div className="rounded-md border border-emerald-200 bg-emerald-50/50 p-3 text-sm">
            <p className="mb-2 text-emerald-800">差不多了——要不要進入收尾對帳?我會把這場記到的內容唸一遍給你核對。</p>
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" onClick={() => finish.mutate()} disabled={finish.isPending}>
                {finish.isPending && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}
                進入收尾對帳
              </Button>
              <Button size="sm" variant="outline" onClick={() => onOpenTaskBoard?.()}>
                先開盤掃一遍補漏
              </Button>
            </div>
          </div>
        ) : null}
        {/* 收尾卡(§6.5 設計③):結構化總結回讀,指著表格對帳;可補充/更正(回 run_turn) */}
        {finish.data?.summary && !finishDismissed ? (
          <div className="rounded-md border bg-muted/40 p-3 text-sm">
            <p className="mb-1 font-medium">收尾對帳——這場我記下了:</p>
            <ul className="mb-2 list-disc space-y-0.5 pl-5 text-xs">
              {finish.data.summary.lines.map((ln, i) => <li key={i}>{ln}</li>)}
              {finish.data.summary.lines.length === 0 ? <li>(本場無新增紀錄)</li> : null}
            </ul>
            <p className="mb-2 text-xs text-muted-foreground">
              其中 {finish.data.summary.pending_count} 筆綠字未審——到表格逐筆 ✓/✗,或用上方「接受全部」。
              有要補充或更正的,直接打在下面輸入框。
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant="outline" onClick={() => setFinishDismissed(true)}>
                完成
              </Button>
              {/* 0032 T5e:補漏掃描——盤當 checklist,補訪談的回憶缺口(人拉取) */}
              <Button size="sm" variant="ghost" onClick={() => onOpenTaskBoard?.()}>
                開盤掃一遍,看有沒有漏的
              </Button>
            </div>
          </div>
        ) : null}
        {turn.isError && (
          <p className="text-xs text-destructive">這回合出了點問題,再送一次即可。</p>
        )}
        <div ref={bottomRef} />
      </div>
      {/* 待審計數(決策在表格內 ✓✗;此鈕只做捲動定位到工具列) */}
      {pendingCount > 0 ? (
        <div className="border-t">
          <button
            type="button"
            onClick={() => window.document.getElementById("ai-pending-bar")
              ?.scrollIntoView({ behavior: "smooth", block: "center" })}
            className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-muted/50"
          >
            <Badge variant="secondary">{pendingCount}</Badge>
            筆 AI 待審(綠字)——點我到表格逐筆 ✓/✗
          </button>
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
            ref={inputRef}
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
