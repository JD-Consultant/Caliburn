"use client";

// 總審清單(T12;ADR 0025 節點批審):pending 建議 → 新舊對照、預設全勾、
// Accept all / 逐條。**套用是呼叫端(頁面)的事**:onDecide 回 accept/reject id,
// 頁面用 applyAccepted + autosave commit 走既有寫入路徑。
import { useState } from "react";
import { Check, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { InterviewSuggestion } from "@/types";

function Val({ v }: { v: unknown }) {
  const s = v == null ? "(空)" : typeof v === "object" ? JSON.stringify(v) : String(v);
  return <span className="break-all">{s}</span>;
}

export function SuggestionReview({ suggestions, busy, onDecide }: {
  suggestions: InterviewSuggestion[];
  busy: boolean;
  onDecide: (accept: string[], reject: string[]) => void;
}) {
  const pending = suggestions.filter((s) => s.status === "pending");
  const [unchecked, setUnchecked] = useState<Set<string>>(new Set());
  if (pending.length === 0) return null;

  const toggle = (id: string) =>
    setUnchecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  const accept = pending.filter((s) => !unchecked.has(s.id)).map((s) => s.id);
  const reject = pending.filter((s) => unchecked.has(s.id)).map((s) => s.id);

  return (
    <div className="space-y-2 rounded-md border p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">
          AI 建議更新 <Badge variant="secondary">{pending.length}</Badge>
        </span>
        <Button size="sm" disabled={busy} onClick={() => onDecide(accept, reject)}>
          <Check className="mr-1 h-3.5 w-3.5" />
          套用勾選({accept.length})
        </Button>
      </div>
      <ul className="space-y-2 text-xs">
        {pending.map((s) => {
          const on = !unchecked.has(s.id);
          const isAdd = s.doc_path.startsWith("add_");
          return (
            <li key={s.id} className="rounded border p-2">
              <label className="flex cursor-pointer items-start gap-2">
                <input type="checkbox" checked={on} onChange={() => toggle(s.id)}
                       className="mt-0.5" />
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="text-muted-foreground">{s.reason}</div>
                  {isAdd ? (
                    <div>新增:<Val v={s.new_value} /></div>
                  ) : (
                    <div className="space-y-0.5">
                      <div className="text-muted-foreground line-through">
                        <Val v={s.old_value} />
                      </div>
                      <div><Val v={s.new_value} /></div>
                    </div>
                  )}
                </div>
                {!on && <X className="h-3.5 w-3.5 text-muted-foreground" />}
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
