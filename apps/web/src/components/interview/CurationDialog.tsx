"use client";

// 任務裁剪確認(0028 D1/D4/D5;D8 P1b 一窗兩步):訪談引擎給**全檢查表**(precheck+others),
// 這裡照 DACUM duty→task 兩步走——步1 勾「職責」(有 AI 預勾任務的職責預勾)→
// 步2 只列所選職責的任務(AI 預勾=勾+引文;others=未勾可勾;已加入=鎖定)。
// 同 UI 家族:Modal(與 OccupationPicker 共用)+ SourceLine 溯源;每列附**引文理由**
// (反盲簽:看得到「你說的那句」才勾)。寫入走既有 addFromPool→persist(單一寫入路徑);
// 要「討論」直接在對話裡跟顧問說。職責是閘門:未選職責的 AI 預勾任務也不套用。
import { useMemo, useState } from "react";
import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  buildCurationRows, dutyRows, filterByDuties, markAlreadyInDoc, picksFromRows,
  type CurationRow,
} from "@/lib/curation";
import { addFromPool } from "@/lib/ocsDoc";
import type { CurationChecklist, KnowledgePack, OcsDocument } from "@/types";
import { Modal } from "./OccupationPicker";
import { SourceLine } from "./fields/SourceLine";

export function CurationDialog({ input, document: doc, pack, onApply, onClose }: {
  input: CurationChecklist;               // 全檢查表(D8):precheck=AI 預勾、others=照列未勾
  document: OcsDocument;
  pack?: KnowledgePack;
  onApply: (next: OcsDocument) => void;   // = 頁面 persist(autosave PATCH)
  onClose: () => void;
}) {
  // already=已在文件(provenance/名稱對位)→ 鎖定「已加入」不可再套(重複添加守衛;
  // 官方任務同編輯器 TaskPickerMenu 行為:重複要加隻能走自訂)
  const rows = useMemo(
    () => markAlreadyInDoc(buildCurationRows(input, pack), doc), [input, pack, doc]);
  const duties = useMemo(() => dutyRows(rows), [rows]);

  const [step, setStep] = useState<1 | 2>(1);
  // 勾選=衍生狀態:預設 + 使用者覆寫表(不用 effect 同步;新 payload 由頁面 key 重掛)
  const [dutyOverrides, setDutyOverrides] = useState<Map<string, boolean>>(new Map());
  const dutyOn = (d: (typeof duties)[number]) => dutyOverrides.get(d.unit) ?? d.defaultOn;
  const toggleDuty = (unit: string, current: boolean) =>
    setDutyOverrides((prev) => new Map(prev).set(unit, !current));
  const pickedDuties = duties.filter(dutyOn);

  const [overrides, setOverrides] = useState<Map<string, boolean>>(new Map());
  const isOn = (r: CurationRow) =>
    r.already ? true : (overrides.get(r.key) ?? (r.prechecked && r.found));
  const toggle = (key: string, current: boolean) =>
    setOverrides((prev) => new Map(prev).set(key, !current));
  const visible = filterByDuties(rows, new Set(pickedDuties.map((d) => d.unit)));
  const selected = visible.filter((r) => r.found && !r.already && isOn(r));

  const apply = () => {
    if (!pack || selected.length === 0) return;
    onApply(addFromPool(doc, picksFromRows(selected, pack)));
    onClose();
  };

  const taskRow = (r: CurationRow) => {
    const locked = !r.found || !!r.already;
    const on = isOn(r);
    return (
      <label key={r.key}
        className={"flex cursor-pointer items-start gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted/50 "
          + (locked ? "opacity-60" : "")}>
        <input type="checkbox" className="mt-1" checked={on}
               disabled={locked} onChange={() => toggle(r.key, on)} />
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5">
            <span className="flex-1">{r.name}</span>
            {r.already ? (
              <Badge variant="secondary" className="text-[10px]" title="此官方任務已在文件,不可重複帶入">
                已加入
              </Badge>
            ) : null}
            {!r.found ? (
              <Badge variant="secondary" className="text-[10px]" title="知識包載入中或來源缺失">
                來源未對位
              </Badge>
            ) : null}
          </span>
          {/* 引文理由(D4 反盲簽):AI 是憑這句預勾的;others 無引文不顯示 */}
          {r.quote ? (
            <span className="block truncate text-xs text-muted-foreground">
              你說:「{r.quote}」
            </span>
          ) : null}
          <SourceLine srcs={r.srcs} />
        </span>
        {on ? <Check className="mt-1 h-3.5 w-3.5 text-muted-foreground" /> : null}
      </label>
    );
  };

  if (step === 1) {
    return (
      <Modal title="帶入官方任務 1/2:先勾職責" onClose={onClose}>
        <p className="mb-2 text-xs text-muted-foreground">
          先勾這份工作<strong>有的職責</strong>(AI 依你說的預勾了部分),下一步再挑各職責底下的任務。
        </p>
        <div className="max-h-80 space-y-1 overflow-y-auto rounded-lg border p-2">
          {duties.map((d) => {
            const on = dutyOn(d);
            return (
              <label key={d.unit}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted/50">
                <input type="checkbox" checked={on}
                       onChange={() => toggleDuty(d.unit, on)} />
                <span className="flex-1">{d.unit || "未分組"}</span>
                <Badge variant="outline" className="text-[10px]">{d.total} 項任務</Badge>
                {d.prechecked > 0 ? (
                  <Badge variant="secondary" className="text-[10px]">AI 預勾 {d.prechecked}</Badge>
                ) : null}
              </label>
            );
          })}
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>之後再說</Button>
          <Button onClick={() => setStep(2)} disabled={pickedDuties.length === 0}>
            下一步({pickedDuties.length} 個職責)
          </Button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title="帶入官方任務 2/2:確認任務" onClose={onClose}>
      <p className="mb-2 text-xs text-muted-foreground">
        AI 可能看錯——掃一眼再套用;不對的取消勾選,或直接在對話裡跟顧問說。
      </p>
      <div className="max-h-80 space-y-2 overflow-y-auto rounded-lg border p-2">
        {pickedDuties.map((d) => (
          <div key={d.unit}>
            <p className="px-2 py-1 text-xs font-medium text-muted-foreground">{d.unit || "未分組"}</p>
            <div className="space-y-1">
              {rows.filter((r) => r.unit === d.unit).map(taskRow)}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={() => setStep(1)}>上一步</Button>
        <Button onClick={apply} disabled={!pack || selected.length === 0}>
          帶入 {selected.length} 項任務
        </Button>
      </div>
    </Modal>
  );
}
