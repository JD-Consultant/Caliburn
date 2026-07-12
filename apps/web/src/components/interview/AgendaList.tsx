"use client";

// 議程三態清單(T9;ADR 0030 §6.5 設計④):資料源=GET interview 的 agenda
// (ledger 推導,update_plan 樣式);開場審一次議程,之後不逐題徵求同意。
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { AGENDA_GLYPH, agendaCounts, type AgendaItem } from "@/lib/interviewUi";

const STATE_CLASS: Record<AgendaItem["state"], string> = {
  completed: "text-muted-foreground line-through decoration-muted-foreground/50",
  in_progress: "font-medium text-foreground",
  pending: "text-muted-foreground",
  boundary: "text-muted-foreground/60 line-through",
};

const GLYPH_CLASS: Record<AgendaItem["state"], string> = {
  completed: "text-emerald-600",
  in_progress: "text-sky-600",
  pending: "text-muted-foreground/60",
  boundary: "text-muted-foreground/60",
};

export function AgendaList({ items }: { items: AgendaItem[] }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;
  const { done, total } = agendaCounts(items);
  return (
    <div className="border-b">
      <button
        type="button"
        className="flex w-full items-center gap-1.5 px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted/50"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        訪談議程 {done}/{total}
      </button>
      {open ? (
        <ul className="space-y-0.5 px-3 pb-2 text-xs">
          {items.map((it) => (
            <li key={it.key} className="flex items-start gap-1.5">
              <span className={"w-3 shrink-0 " + GLYPH_CLASS[it.state]}>{AGENDA_GLYPH[it.state]}</span>
              <span className={STATE_CLASS[it.state]}>
                {it.label}
                {it.state === "boundary" ? "(不談)" : null}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
