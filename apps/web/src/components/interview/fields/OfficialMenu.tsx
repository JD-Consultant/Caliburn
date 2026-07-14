"use client";
import { useState, type ReactNode } from "react";
import { Check } from "lucide-react";
import type { SourceRef } from "@/types";
import { Command, CommandEmpty, CommandGroup, CommandItem, CommandList } from "@/components/ui/command";
import { Modal } from "../OccupationPicker";
import { SourceLine } from "./SourceLine";

export type OfficialMenuOption = { value: string; label: string; hint?: string; srcs?: SourceRef[] };

// 單值「選官方」**獨立選單窗**(ADR 0029:Modal 家族,不再是 Popover)：列官方候選 + 來源行；
// selected 時打勾。基準級別/任務級別/工作描述共用。批次帶入鈕文案由 autoApplyLabel 指定(選同X)。
export function OfficialMenu({ trigger, title = "選官方", options, onPick, selected, onOpenChange, onAutoApply, autoApplyLabel = "選同官方" }: {
  trigger: ReactNode;
  title?: string;        // 獨立窗標題
  options: OfficialMenuOption[];
  onPick: (value: string) => void;
  selected?: string; // 目前選中值（單選時打勾）；不傳＝不顯示勾（如 append 用途）
  onOpenChange?: (open: boolean) => void; // 開關通知（讓父層在開啟時才 lazy 取資料）
  onAutoApply?: () => void; // 給了→窗頂顯批次帶入鈕（選同X;ADR 0029）
  autoApplyLabel?: string;  // 批次帶入鈕文案(如「選同職能基準」)
}) {
  const [open, setOpen] = useState(false);
  const setOpenAnd = (o: boolean) => { setOpen(o); onOpenChange?.(o); };
  return (
    <>
      <span className="inline-flex" onClick={() => setOpenAnd(true)}>{trigger}</span>
      {open ? (
        <Modal title={title} onClose={() => setOpenAnd(false)}>
          {onAutoApply ? (
            <div className="mb-2 flex items-center justify-end px-1">
              <button type="button" className="shrink-0 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => { onAutoApply(); setOpenAnd(false); }}>
                {autoApplyLabel}
              </button>
            </div>
          ) : null}
          <div className="rounded-lg border">
            <Command className="bg-transparent">
              <CommandList className="max-h-96">
                <CommandEmpty>無官方候選</CommandEmpty>
                <CommandGroup>
                  {options.map((o, i) => (
                    <CommandItem key={i} value={`${o.label}-${i}`} onSelect={() => { onPick(o.value); setOpenAnd(false); }} className="items-start">
                      {selected !== undefined ? (
                        <Check className={"mt-0.5 h-3.5 w-3.5 " + (o.value === selected ? "opacity-100" : "opacity-0")} />
                      ) : null}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1">
                          <span className="flex-1 truncate">{o.label}</span>
                          {o.hint ? <span className={"ml-1 shrink-0 rounded px-1 text-[10px] " + (o.hint === "已改" ? "bg-amber-100 text-amber-700" : "text-sky-700")}>{o.hint}</span> : null}
                        </div>
                        <SourceLine srcs={o.srcs} />
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </div>
        </Modal>
      ) : null}
    </>
  );
}
