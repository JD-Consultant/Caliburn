"use client";

// 職類建議卡(0031 A 案):顧問提議的職類以卡片進對話流——預勾+每列白話理由,
// 新手「點一下確認顧問剛說的話」即可;不彈窗。三出口(Claude AskUserQuestion 風格):
// 確認=寫參考集合(人選原則不變,useSetOccupations 同 picker 一條路)/
// 其他=回到聊天(聚焦輸入框)/ ✕=收合+occupation_dismissed 記帳(顧問下回合換話術)。
import { useState } from "react";
import { useSetOccupations } from "@/hooks/useDocument";
import { postReviewEvents } from "@/lib/api";
import type { OccPrecheckItem } from "@/types";
import { Button } from "@/components/ui/button";
import { Loader2, X } from "lucide-react";

export function OccupationSuggestCard({ profileId, items, onDone, onOther, onError }: {
  profileId: string;
  items: OccPrecheckItem[];
  onDone: () => void;                 // 確認成功 / ✕ 之後收卡
  onOther: () => void;                // 「其他」→ 聚焦輸入框繼續聊
  onError: (msg: string) => void;
}) {
  const [picked, setPicked] = useState<string[]>(items.map((i) => i.code)); // 預勾全部
  const setOcc = useSetOccupations(profileId);

  const toggle = (code: string) =>
    setPicked((p) => (p.includes(code) ? p.filter((c) => c !== code) : [...p, code]));

  const dismiss = () => {
    // 無聲記帳(失敗不擋 UI;§6.3 同款)——顧問下回合會收到「他關掉了」換話術
    postReviewEvents(profileId, [
      { doc_path: "reference:occupations", decision: "occupation_dismissed" },
    ]).catch(() => {});
    onDone();
  };

  return (
    <div className="rounded-md border border-sky-200 bg-sky-50/50 p-3 text-sm dark:border-sky-900 dark:bg-sky-950/30">
      <div className="mb-2 flex items-start justify-between gap-2">
        <p className="font-medium">顧問建議的職能基準參考</p>
        <button type="button" aria-label="先不選" onClick={dismiss}
                className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="mb-2 space-y-1.5">
        {items.map((it) => (
          <label key={it.code} className="flex cursor-pointer items-start gap-2">
            <input type="checkbox" className="mt-0.5" checked={picked.includes(it.code)}
                   onChange={() => toggle(it.code)} />
            <span>
              {it.name}
              <span className="ml-1 font-mono text-xs text-muted-foreground">{it.code}</span>
              <span className="block text-xs text-muted-foreground">{it.reason}</span>
            </span>
          </label>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Button size="sm" disabled={picked.length === 0 || setOcc.isPending}
                onClick={() => setOcc.mutate(picked, {
                  onSuccess: onDone,
                  onError: (e: unknown) =>
                    onError(e instanceof Error ? e.message : "加入參考失敗"),
                })}>
          {setOcc.isPending && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}
          加入參考({picked.length})
        </Button>
        <Button size="sm" variant="ghost" onClick={onOther}>
          都不像?用說的告訴我
        </Button>
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground">
        之後隨時可在〔選參考〕增減;選了我才拿得到官方任務清單當底稿。
      </p>
    </div>
  );
}
