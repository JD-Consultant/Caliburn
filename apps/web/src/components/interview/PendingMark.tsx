"use client";

// 追蹤修訂標記 UI(ADR 0030 §6.6):新增/修改=綠字+淡綠底、刪除=紅字刪除線
// (沿 track-changes 慣例不發明新語彙);hover 浮 ✓/✗/?;「?」開出處卡=
// 官方來源行+訪談原話「第 N 輪:『…』」(HAX G11)。條目級粒度,筆級淡入。
// 決策本身無聲(§6.3):✓/✗ 只改文件+記帳,不觸發 AI 回應。
import type { PendingMark as Mark } from "@caliburn/ocs-contract";
import { Check, HelpCircle, X } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export type ReviewDecision = "accepted" | "rejected";

// 文字樣式:add/mod=綠;del=紅刪除線。搭配容器 "group/pending" 讓 ✓✗? hover 浮現。
export function pendingTextClass(op: Mark["op"]): string {
  return op === "del"
    ? "text-red-600 line-through decoration-red-400"
    : "rounded bg-emerald-50 px-0.5 text-emerald-700";
}

export function SourceCard({ mark }: { mark: Mark }) {
  const src = mark.src ?? undefined;
  return (
    <div className="space-y-1 text-xs">
      <div className="font-medium">AI 寫入出處</div>
      {src?.ref_urn ? (
        <div className="text-muted-foreground">官方來源:{src.ref_urn}</div>
      ) : null}
      {src?.quote ? (
        <div>第 {src.quote.turn_id} 輪:「{src.quote.text}」</div>
      ) : null}
      {!src?.ref_urn && !src?.quote ? (
        <div className="text-muted-foreground">(無出處資訊)</div>
      ) : null}
      {mark.op === "mod" && mark.prev != null ? (
        <div className="text-muted-foreground">原值:{String(mark.prev)}</div>
      ) : null}
    </div>
  );
}

export function PendingActions({
  mark,
  onDecide,
}: {
  mark: Mark;
  onDecide: (d: ReviewDecision) => void;
}) {
  return (
    <span className="inline-flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover/pending:opacity-100">
      <button
        type="button"
        title="接受(✓)"
        className="rounded p-0.5 text-emerald-600 hover:bg-emerald-100"
        onClick={(e) => { e.stopPropagation(); onDecide("accepted"); }}
      >
        <Check className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        title="拒絕(✗)"
        className="rounded p-0.5 text-red-500 hover:bg-red-100"
        onClick={(e) => { e.stopPropagation(); onDecide("rejected"); }}
      >
        <X className="h-3.5 w-3.5" />
      </button>
      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            title="出處(?)"
            className="rounded p-0.5 text-muted-foreground hover:bg-muted"
            onClick={(e) => e.stopPropagation()}
          >
            <HelpCircle className="h-3.5 w-3.5" />
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-72" onClick={(e) => e.stopPropagation()}>
          <SourceCard mark={mark} />
        </PopoverContent>
      </Popover>
    </span>
  );
}

// mod 的舊值小字副行(樣式同 0029 原名副行)。
export function PrevLine({ mark }: { mark: Mark }) {
  if (mark.op !== "mod" || mark.prev == null) return null;
  return <div className="text-[10px] text-muted-foreground no-underline">原:{String(mark.prev)}</div>;
}
