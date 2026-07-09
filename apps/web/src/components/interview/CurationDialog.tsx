"use client";

// 任務裁剪確認(0028 D1/D4/D5;T7):訪談引擎 widget 指令 → AI 依你的話**預勾**官方任務,
// 人確認才落文件(高風險=選單阻斷)。同 UI 家族:Modal(與 OccupationPicker 共用)+
// SourceLine 溯源;每列附**引文理由**(反盲簽:看得到「你說的那句」才勾)。
// 寫入走既有 addFromPool→persist(單一寫入路徑);要「討論」直接在對話裡跟顧問說。
import { useMemo, useState } from "react";
import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buildCurationRows, picksFromRows } from "@/lib/curation";
import { addFromPool } from "@/lib/ocsDoc";
import type { KnowledgePack, OcsDocument, PickerPrecheckItem } from "@/types";
import { Modal } from "./OccupationPicker";
import { SourceLine } from "./fields/SourceLine";

export function CurationDialog({ items, document: doc, pack, onApply, onClose }: {
  items: PickerPrecheckItem[];
  document: OcsDocument;
  pack?: KnowledgePack;
  onApply: (next: OcsDocument) => void;   // = 頁面 persist(autosave PATCH)
  onClose: () => void;
}) {
  const rows = useMemo(() => buildCurationRows(items, pack), [items, pack]);
  const [unchecked, setUnchecked] = useState<Set<string>>(new Set());
  const toggle = (key: string) =>
    setUnchecked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  const selected = rows.filter((r) => r.found && !unchecked.has(r.key));

  const apply = () => {
    if (!pack || selected.length === 0) return;
    onApply(addFromPool(doc, picksFromRows(selected, pack)));
    onClose();
  };

  return (
    <Modal title="AI 依你說的預勾了官方任務" onClose={onClose}>
      <p className="mb-2 text-xs text-muted-foreground">
        AI 可能看錯——掃一眼再套用;不對的取消勾選,或直接在對話裡跟顧問說。
      </p>
      <div className="max-h-80 space-y-1 overflow-y-auto rounded-lg border p-2">
        {rows.map((r) => {
          const on = r.found && !unchecked.has(r.key);
          return (
            <label key={r.key}
              className={"flex cursor-pointer items-start gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted/50 "
                + (r.found ? "" : "opacity-60")}>
              <input type="checkbox" className="mt-1" checked={on}
                     disabled={!r.found} onChange={() => toggle(r.key)} />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5">
                  <span className="flex-1">{r.name}</span>
                  {r.unit ? <Badge variant="outline" className="text-[10px]">{r.unit}</Badge> : null}
                  {!r.found ? (
                    <Badge variant="secondary" className="text-[10px]" title="知識包載入中或來源缺失">
                      來源未對位
                    </Badge>
                  ) : null}
                </span>
                {/* 引文理由(D4 反盲簽):AI 是憑這句預勾的 */}
                <span className="block truncate text-xs text-muted-foreground">
                  你說:「{r.quote}」
                </span>
                <SourceLine srcs={r.srcs} />
              </span>
              {on ? <Check className="mt-1 h-3.5 w-3.5 text-muted-foreground" /> : null}
            </label>
          );
        })}
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>之後再說</Button>
        <Button onClick={apply} disabled={!pack || selected.length === 0}>
          帶入 {selected.length} 項任務
        </Button>
      </div>
    </Modal>
  );
}
