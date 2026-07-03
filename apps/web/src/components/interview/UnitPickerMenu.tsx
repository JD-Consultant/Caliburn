"use client";

// 「選職責 ▾」工具列下拉（P3 UI 修訂：表格中心）：職責大池全列（序號＋引用行）。
// 勾＝空職責立即入表格（任務再從職責列「選任務 ▾」挑）；再點取消＝移除空職責；
// 含任務的鎖定（表格刪）。「自動勾選」＝補上主基準（順序1）來源的職責。
// commit-per-click，走 autosave（單一寫入路徑）。
import { useState } from "react";
import { Check, ChevronDown, ListChecks } from "lucide-react";
import type { KnowledgePack, OcsDocument } from "@/types";
import { addFromPool, deleteUnit } from "@/lib/ocsDoc";
import { unitRows, type UnitRowVM } from "@/lib/pack";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SourceLine } from "./fields/SourceLine";

export function UnitPickerMenu({ document: doc, pack, disabled, onChange }: {
  document: OcsDocument | undefined;
  pack?: KnowledgePack;
  disabled?: boolean;
  onChange: (d: OcsDocument) => void;
}) {
  const [open, setOpen] = useState(false);
  const rows = pack ? unitRows(pack) : [];
  const primary = pack?.occupation_details[0]?.ocs_code ?? "";
  const units = doc?.ocs_content?.ocu_units ?? [];
  const idxOf = (name: string) => units.findIndex((u) => u.ocu_name === name);

  const toggle = (row: UnitRowVM) => {
    if (!doc) return;
    const idx = idxOf(row.name);
    if (idx < 0) {
      onChange(addFromPool(doc, [{ unit: { name: row.name, srcs: row.srcs }, tasks: [] }]));
      return;
    }
    if ((units[idx].tasks?.length ?? 0) > 0) return; // 含任務鎖定（表格刪）
    onChange(deleteUnit(doc, idx));
  };

  // 自動勾選：補上主基準來源、還不在文件的職責（空職責，任務另挑）。
  const applyDefaults = () => {
    if (!doc || !primary) return;
    const picks = rows
      .filter((r) => r.srcs.some((s) => s.ocs_code === primary) && idxOf(r.name) < 0)
      .map((r) => ({ unit: { name: r.name, srcs: r.srcs }, tasks: [] }));
    if (picks.length) onChange(addFromPool(doc, picks));
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button size="sm" variant="outline" className="gap-1" disabled={disabled}>
          <ListChecks className="h-4 w-4" />
          選職責
          <ChevronDown className="h-3.5 w-3.5 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80" align="end">
        <div className="mb-1 flex items-center justify-between gap-2 px-1">
          <span className="text-xs text-muted-foreground">勾選入表格；任務從職責列挑</span>
          <button type="button" className="shrink-0 text-xs text-muted-foreground hover:text-foreground"
            title="補上主基準（順序1）來源的職責" onClick={applyDefaults}>
            自動勾選
          </button>
        </div>
        <Command>
          <CommandList>
            <CommandEmpty>沒有候選職責。請先〔選職類〕。</CommandEmpty>
            <CommandGroup>
              {rows.map((r, i) => {
                const idx = idxOf(r.name);
                const inDoc = idx >= 0;
                const locked = inDoc && (units[idx].tasks?.length ?? 0) > 0;
                return (
                  <CommandItem key={r.name} value={`${i} ${r.name}`} onSelect={() => toggle(r)}
                    className={"items-start " + (locked ? "opacity-60" : "")}>
                    <Check className={"mt-0.5 h-3.5 w-3.5 " + (inDoc ? "opacity-100" : "opacity-0")} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1">
                        <span className="font-mono text-xs text-muted-foreground">{i + 1}.</span>
                        <span className="flex-1">{r.name}</span>
                        {locked ? <Badge variant="secondary" className="text-[10px]" title="含任務，請在表格刪除">含任務</Badge> : null}
                      </div>
                      <SourceLine srcs={r.srcs} />
                    </div>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
