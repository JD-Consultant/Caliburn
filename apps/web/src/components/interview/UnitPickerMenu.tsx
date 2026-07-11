"use client";

// 「選職責」工具列按鈕 → **獨立選單窗**(Modal;原下拉 Popover 太擠——職責多+每列
// 來源行,東西太多):職責大池全列(✓+序號+引用行,Command 選單列)。
// 勾＝空職責立即入表格(任務再從職責列「選任務」挑);再點取消＝移除空職責;
// 含任務的鎖定(表格刪)。「自動勾選」＝補上主基準(順序1)來源的職責。
// commit-per-click,走 autosave(單一寫入路徑)。與選職類/AI 任務盤同 Modal 家族。
import { useState } from "react";
import { Check, ListChecks } from "lucide-react";
import type { KnowledgePack, OcsDocument } from "@/types";
import { addFromPool, deleteUnit } from "@/lib/ocsDoc";
import { isOfficialBasis, unitRows, type UnitRowVM } from "@/lib/pack";
import { Command, CommandEmpty, CommandGroup, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "./OccupationPicker";
import { SourceLine } from "./fields/SourceLine";

export function UnitPickerMenu({ document: doc, pack, disabled, onChange }: {
  document: OcsDocument | undefined;
  pack?: KnowledgePack;
  disabled?: boolean;
  onChange: (d: OcsDocument) => void;
}) {
  const [open, setOpen] = useState(false);
  const rows = pack ? unitRows(pack) : [];
  // ADR 0029:主基準＝**文件表頭所選**(職類視窗單選帶入),不再取 pack 第一順位。
  // 未選或非官方身分 → 「選同職能基準」批次鈕停用(比照 isOfficialBasis)。
  const primary = doc?.ocs_profile?.ocs_code ?? "";
  const canApplyDefaults = !!pack && isOfficialBasis(pack, primary);
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
    <>
      <Button size="sm" variant="outline" className="gap-1" disabled={disabled}
              onClick={() => setOpen(true)}>
        <ListChecks className="h-4 w-4" />
        選職責
      </Button>
      {open ? (
        <Modal title="選職責" onClose={() => setOpen(false)}>
          <div className="mb-2 flex items-center justify-between gap-2 px-1">
            <span className="text-xs text-muted-foreground">勾選入表格；任務從職責列挑</span>
            <button type="button" disabled={!canApplyDefaults}
              className="shrink-0 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40"
              title="補上主基準來源的職責" onClick={applyDefaults}>
              自動勾選
            </button>
          </div>
          <div className="rounded-lg border">
            <Command className="bg-transparent">
              <CommandList className="max-h-96">
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
          </div>
        </Modal>
      ) : null}
    </>
  );
}
