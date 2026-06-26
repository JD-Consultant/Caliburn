"use client";
import { useState, type ReactNode } from "react";
import { Check } from "lucide-react";
import type { SourceRef } from "@/types";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandItem, CommandList } from "@/components/ui/command";
import { SourceLine } from "./SourceLine";

export type OfficialMenuOption = { value: string; label: string; hint?: string; srcs?: SourceRef[] };

// 單值「選官方」選單：列官方候選 + 來源行；selected 時打勾。基準級別/職能基準代碼/任務級別共用。
export function OfficialMenu({ trigger, options, onPick, selected }: {
  trigger: ReactNode;
  options: OfficialMenuOption[];
  onPick: (value: string) => void;
  selected?: string; // 目前選中值（單選時打勾）；不傳＝不顯示勾（如 append 用途）
}) {
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent className="w-72">
        <Command>
          <CommandList>
            <CommandEmpty>無官方候選</CommandEmpty>
            <CommandGroup>
              {options.map((o, i) => (
                <CommandItem key={i} value={`${o.label}-${i}`} onSelect={() => { onPick(o.value); setOpen(false); }} className="items-start">
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
      </PopoverContent>
    </Popover>
  );
}
