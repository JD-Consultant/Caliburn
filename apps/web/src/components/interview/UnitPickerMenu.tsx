"use client";

// 「選職責」工具列按鈕 → **獨立選單窗**(Modal):職責大池全列(✓+序號+名稱+來源行)。
// 勾＝空職責立即入表格(任務再從職責列「選任務」挑);再點取消＝移除空職責;含任務鎖定(表格刪)。
// 身分對位靠 _refs(改名不斷根後名可異,勾選仍在);列內改名(僅已勾)＋原名副行;窗頂搜尋。
// 「選同職能基準」＝補上主基準來源的職責。commit-per-click,走 autosave(單一寫入路徑)。
import { useState } from "react";
import { Check, ListChecks, Pencil } from "lucide-react";
import type { KnowledgePack, OcsDocument } from "@/types";
import { addFromPool, deleteUnit, renameUnit } from "@/lib/ocsDoc";
import { isOfficialBasis, unitRows, type UnitRowVM } from "@/lib/pack";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "./OccupationPicker";
import { FieldText } from "./fields/FieldText";
import { SourceLine } from "./fields/SourceLine";

// 池列 ↔ 文件職責身分對位:靠 (ocs_code, ocu_code) 對(_refs),名字不參與(改名不斷根)。
const rowPairs = (r: UnitRowVM) => r.srcs.filter((s) => s.ocu_code).map((s) => `${s.ocs_code}__${s.ocu_code}`);

export function UnitPickerMenu({ document: doc, pack, disabled, onChange }: {
  document: OcsDocument | undefined;
  pack?: KnowledgePack;
  disabled?: boolean;
  onChange: (d: OcsDocument) => void;
}) {
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null);
  const rows = pack ? unitRows(pack) : [];
  // ADR 0029:主基準＝**文件表頭所選**;未選或非官方 → 「選同職能基準」批次鈕停用。
  const primary = doc?.ocs_profile?.ocs_code ?? "";
  const canApplyDefaults = !!pack && isOfficialBasis(pack, primary);
  const units = doc?.ocs_content?.ocu_units ?? [];
  // 身分對位:_refs 的 (ocs_code, ocu_code) 命中池列;無 _refs 才退回比名(舊/手建)。
  const idxOf = (row: UnitRowVM) => {
    const pairs = rowPairs(row);
    return units.findIndex((u) => {
      const up = (u._refs ?? []).filter((r) => r.ocu_code).map((r) => `${r.ocs_code}__${r.ocu_code}`);
      return up.length ? up.some((p) => pairs.includes(p)) : u.ocu_name === row.name;
    });
  };

  const toggle = (row: UnitRowVM) => {
    if (!doc) return;
    const idx = idxOf(row);
    if (idx < 0) {
      onChange(addFromPool(doc, [{ unit: { name: row.name, srcs: row.srcs }, tasks: [] }]));
      return;
    }
    if ((units[idx].tasks?.length ?? 0) > 0) return; // 含任務鎖定（表格刪）
    onChange(deleteUnit(doc, idx));
  };

  // 選同職能基準：補上主基準來源、還不在文件的職責（空職責，任務另挑）。
  const applyDefaults = () => {
    if (!doc || !primary) return;
    const picks = rows
      .filter((r) => r.srcs.some((s) => s.ocs_code === primary) && idxOf(r) < 0)
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
        <Modal title="選職責" onClose={() => { setOpen(false); setRenaming(null); }}>
          <div className="mb-2 flex items-center justify-between gap-2 px-1">
            <span className="text-xs text-muted-foreground">勾選入表格；任務從職責列挑</span>
            <button type="button" disabled={!canApplyDefaults}
              className="shrink-0 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40"
              title="補上主基準來源的職責" onClick={applyDefaults}>
              選同職能基準
            </button>
          </div>
          <div className="rounded-lg border">
            <Command className="bg-transparent">
              <CommandInput placeholder="搜尋職責…" />
              <CommandList className="max-h-96">
                <CommandEmpty>沒有候選職責。請先〔選職能基準參考〕。</CommandEmpty>
                <CommandGroup>
                  {rows.map((r, i) => {
                    const idx = idxOf(r);
                    const inDoc = idx >= 0;
                    const unit = inDoc ? units[idx] : undefined;
                    const locked = inDoc && (units[idx].tasks?.length ?? 0) > 0;
                    const renamed = !!unit && unit.ocu_name !== r.name;
                    if (inDoc && renaming === r.name) {
                      return (
                        <div key={r.name} className="flex items-start gap-2 px-2 py-1.5">
                          <Check className="mt-0.5 h-3.5 w-3.5 opacity-100" />
                          <div className="min-w-0 flex-1">
                            <FieldText value={unit!.ocu_name ?? ""} autoFocus
                              onCommit={(v) => { onChange(renameUnit(doc!, idx, v)); setRenaming(null); }} />
                            {renamed ? <div className="mt-0.5 text-[10px] text-muted-foreground">原名:{r.name}</div> : null}
                            <SourceLine srcs={r.srcs} />
                          </div>
                        </div>
                      );
                    }
                    return (
                      <CommandItem key={r.name} value={`${i} ${r.name}`} onSelect={() => toggle(r)}
                        className={"group items-start " + (locked ? "opacity-60" : "")}>
                        <Check className={"mt-0.5 h-3.5 w-3.5 " + (inDoc ? "opacity-100" : "opacity-0")} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1">
                            <span className="font-mono text-xs text-muted-foreground">{i + 1}.</span>
                            <span className="flex-1">{renamed ? unit!.ocu_name : r.name}</span>
                            {inDoc ? (
                              <button type="button" title="改名（保留來源）"
                                className="shrink-0 text-muted-foreground opacity-0 hover:text-foreground group-hover:opacity-100"
                                onClick={(e) => { e.stopPropagation(); setRenaming(r.name); }}>
                                <Pencil className="h-3 w-3" />
                              </button>
                            ) : null}
                            {locked ? <Badge variant="secondary" className="text-[10px]" title="含任務，請在表格刪除">含任務</Badge> : null}
                          </div>
                          {renamed ? <div className="mt-0.5 text-[10px] text-muted-foreground">原名:{r.name}</div> : null}
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
