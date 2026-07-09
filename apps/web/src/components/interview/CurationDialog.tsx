"use client";

// AI 任務盤確認(0028 D1/D4/D5;D8 一窗兩步;D9 資料源收斂):**盤=編輯器知識包全量**
// (與 UnitPicker/TaskPickerMenu 同宇宙、同身分機制),**AI 只疊 precheck+引文**。
// 步1 勾職責(全部官方職責照列;有 AI 預勾任務的預勾)→ 步2 該職責全部官方任務
// (AI 預勾=勾+引文;已在文件=鎖「已加入/已填」;其餘未勾可勾)。職責是閘門:
// 未選職責的預勾任務不套用。**列=編輯器選單同款**(Command 列:✓+序號+SourceLine,
// 同 Unit/TaskPickerMenu 形式)。寫入走既有 addFromPool→persist(單一寫入路徑);
// 要「討論」直接在對話裡跟顧問說。
import { useMemo, useState } from "react";
import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Command, CommandGroup, CommandItem, CommandList } from "@/components/ui/command";
import { buildBoard, picksFromBoard, type BoardTaskRow } from "@/lib/curation";
import { addFromPool } from "@/lib/ocsDoc";
import type { KnowledgePack, OcsDocument, PickerPrecheckItem } from "@/types";
import { Modal } from "./OccupationPicker";
import { SourceLine } from "./fields/SourceLine";

export function CurationDialog({ precheck, document: doc, pack, onApply, onClose }: {
  precheck: PickerPrecheckItem[];         // AI 疊加層(D9);清單本身來自 pack
  document: OcsDocument;
  pack?: KnowledgePack;
  onApply: (next: OcsDocument) => void;   // = 頁面 persist(autosave PATCH)
  onClose: () => void;
}) {
  const board = useMemo(() => buildBoard(precheck, pack, doc), [precheck, pack, doc]);

  const [step, setStep] = useState<1 | 2>(1);
  // 勾選=衍生狀態:預設 + 使用者覆寫表(不用 effect 同步;新 payload 由頁面 key 重掛)
  const [dutyOverrides, setDutyOverrides] = useState<Map<string, boolean>>(new Map());
  const dutyOn = (d: (typeof board.duties)[number]) =>
    dutyOverrides.get(d.unit) ?? d.defaultOn;
  const toggleDuty = (unit: string, current: boolean) =>
    setDutyOverrides((prev) => new Map(prev).set(unit, !current));
  const pickedDuties = board.duties.filter(dutyOn);

  const [overrides, setOverrides] = useState<Map<string, boolean>>(new Map());
  const isOn = (r: BoardTaskRow) =>
    r.already ? true : (overrides.get(r.name) ?? r.prechecked);
  const toggle = (name: string, current: boolean) =>
    setOverrides((prev) => new Map(prev).set(name, !current));
  const pickedUnits = new Set(pickedDuties.map((d) => d.unit));
  const selected = board.tasks.filter(
    (r) => pickedUnits.has(r.unit) && !r.already && isOn(r));

  const apply = () => {
    if (!pack || selected.length === 0) return;
    onApply(addFromPool(doc, picksFromBoard(selected, board)));
    onClose();
  };

  // pack 載入中(剛選完職類 invalidate+prefetch 進行中)→ 載入態,資料到了自動浮現
  if (board.duties.length === 0) {
    return (
      <Modal title="帶入官方任務" onClose={onClose}>
        <p className="py-6 text-center text-sm text-muted-foreground">
          {pack ? "沒有候選職責。請先〔選職類〕。" : "官方任務清單載入中…"}
        </p>
      </Modal>
    );
  }

  const taskItem = (r: BoardTaskRow, i: number) => {
    const on = isOn(r);
    return (
      <CommandItem key={r.name} value={`${r.unit} ${i} ${r.name}`}
        onSelect={() => { if (!r.already) toggle(r.name, on); }}
        className={"items-start " + (r.already ? "opacity-60" : "")}>
        <Check className={"mt-0.5 h-3.5 w-3.5 " + (on ? "opacity-100" : "opacity-0")} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-xs text-muted-foreground">{i + 1}.</span>
            <span className="flex-1">{r.name}</span>
            {r.already ? (
              <Badge variant="secondary" className="text-[10px]"
                     title={r.filled ? "已在文件且已填內容" : "此官方任務已在文件,不可重複帶入"}>
                {r.filled ? "已填" : "已加入"}
              </Badge>
            ) : null}
          </div>
          {/* 引文理由(D4 反盲簽):AI 是憑這句預勾的;無引文不顯示 */}
          {r.quote ? (
            <span className="block truncate text-xs text-muted-foreground">
              你說:「{r.quote}」
            </span>
          ) : null}
          <SourceLine srcs={r.srcs} />
        </div>
      </CommandItem>
    );
  };

  if (step === 1) {
    return (
      <Modal title="帶入官方任務 1/2:先勾職責" onClose={onClose}>
        <p className="mb-2 text-xs text-muted-foreground">
          先勾這份工作<strong>有的職責</strong>(AI 依你說的預勾了部分),下一步再挑各職責底下的任務。
        </p>
        <div className="rounded-lg border">
          <Command className="bg-transparent">
            <CommandList className="max-h-80">
              <CommandGroup>
                {board.duties.map((d, i) => {
                  const on = dutyOn(d);
                  return (
                    <CommandItem key={d.unit} value={`${i} ${d.unit}`}
                      onSelect={() => toggleDuty(d.unit, on)} className="items-start">
                      <Check className={"mt-0.5 h-3.5 w-3.5 " + (on ? "opacity-100" : "opacity-0")} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-xs text-muted-foreground">{i + 1}.</span>
                          <span className="flex-1">{d.unit}</span>
                          <Badge variant="outline" className="text-[10px]">{d.total} 項任務</Badge>
                          {d.prechecked > 0 ? (
                            <Badge variant="secondary" className="text-[10px]">AI 預勾 {d.prechecked}</Badge>
                          ) : null}
                          {d.inDoc ? (
                            <Badge variant="secondary" className="text-[10px]"
                                   title="此職責已在文件;可再進去補任務">已加入</Badge>
                          ) : null}
                        </div>
                        <SourceLine srcs={d.srcs} />
                      </div>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
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
      <div className="rounded-lg border">
        <Command className="bg-transparent">
          <CommandList className="max-h-80">
            {pickedDuties.map((d) => (
              <CommandGroup key={d.unit}>
                <p className="px-2 py-1 text-xs font-medium text-muted-foreground">{d.unit}</p>
                {board.tasks.filter((r) => r.unit === d.unit).map(taskItem)}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
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
