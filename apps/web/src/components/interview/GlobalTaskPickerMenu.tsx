"use client";

// 全域〔選工作任務〕窗(ADR 0029;spec §6)——頂欄入口:任務大池全列,勾一筆即自動掛到
// 它的**來源職責**(在文件→掛入;不在→先自動加該職責再掛);每列副行預告「將掛入:○○職責」。
// 多來源任務取主基準優先(resolveHomeUnit)。「選同職能基準」＝主基準全部職責+官方任務整組帶入。
// 取消勾規則同職責內任務窗(空任務可移、有內容鎖定→表格刪)。與其他選單同 Modal 家族。
import { useState } from "react";
import { Check, ListChecks } from "lucide-react";
import type { KnowledgePack, OcsDocument } from "@/types";
import { addFromPool, addTasksToUnit, deleteTask, taskHasContent } from "@/lib/ocsDoc";
import {
  isOfficialBasis, primarySkeletonPicks, resolveHomeUnit, taskPickFromRow, taskRows, type TaskRowVM,
} from "@/lib/pack";
import { taskUrns } from "@/lib/urn";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "./OccupationPicker";
import { SourceLine } from "./fields/SourceLine";

export function GlobalTaskPickerMenu({
  document: doc, pack, disabled, onChange, open: openProp, onOpenChange,
}: {
  document: OcsDocument | undefined;
  pack?: KnowledgePack;
  disabled?: boolean;
  onChange: (d: OcsDocument) => void;
  open?: boolean;                       // 受控開窗(0032 intake 卡程式化開;省略=內部 state)
  onOpenChange?: (v: boolean) => void;
}) {
  const [openState, setOpenState] = useState(false);
  const open = openProp ?? openState;
  const setOpen = (v: boolean) => { setOpenState(v); onOpenChange?.(v); };
  const rows = pack ? taskRows(pack) : [];
  const primary = doc?.ocs_profile?.ocs_code ?? "";
  const canApplyDefaults = !!pack && isOfficialBasis(pack, primary);

  // 文件內任務 URN → 位置對照（勾選狀態/已填鎖定）。
  const urnLoc = new Map<string, { u: number; t: number; filled: boolean }>();
  (doc?.ocs_content?.ocu_units ?? []).forEach((uu, ui) => {
    (uu.tasks ?? []).forEach((tt, ti) => {
      for (const urn of taskUrns(tt)) urnLoc.set(urn, { u: ui, t: ti, filled: taskHasContent(tt) });
    });
  });
  const locOf = (row: TaskRowVM) => {
    for (const urn of row.urns) { const l = urnLoc.get(urn); if (l) return l; }
    return null;
  };

  const toggle = (row: TaskRowVM) => {
    if (!doc || !pack) return;
    const loc = locOf(row);
    if (loc) {
      if (loc.filled) return;            // 有內容鎖定（表格刪）
      onChange(deleteTask(doc, loc.u, loc.t));
      return;
    }
    const home = resolveHomeUnit(row, doc, pack, primary);
    const pick = taskPickFromRow(row, primary);
    if (home && home.existingIdx >= 0) {
      onChange(addTasksToUnit(doc, home.existingIdx, [pick]));   // 來源職責已在 → 掛入
    } else if (home) {
      onChange(addFromPool(doc, [{ unit: { name: home.ocuName, srcs: [home.unitSrc] }, tasks: [pick] }])); // 不在 → 先建職責再掛
    } else {
      onChange(addFromPool(doc, [{ unit: { name: "工作任務", srcs: [] }, tasks: [pick] }])); // 無來源職責(異常) → 落到通用職責
    }
  };

  // 選同職能基準：主基準全部職責 + 官方任務整組帶入（一鍵鋪官方骨架）。
  const applyDefaults = () => {
    if (!doc || !pack || !primary) return;
    const picks = primarySkeletonPicks(pack, primary);
    if (picks.length) onChange(addFromPool(doc, picks));
  };

  return (
    <>
      <Button size="sm" variant="outline" className="gap-1" disabled={disabled} onClick={() => setOpen(true)}>
        <ListChecks className="h-4 w-4" />
        選工作任務
      </Button>
      {open ? (
        <Modal title="選工作任務（全域）" onClose={() => setOpen(false)}>
          <div className="mb-2 flex items-center justify-between gap-2 px-1">
            <span className="text-xs text-muted-foreground">勾一筆＝自動掛到它的來源職責</span>
            <button type="button" disabled={!canApplyDefaults}
              className="shrink-0 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40"
              title="主基準全部職責+官方任務整組帶入" onClick={applyDefaults}>
              選同職能基準
            </button>
          </div>
          <div className="rounded-lg border">
            <Command className="bg-transparent">
              <CommandInput placeholder="搜尋任務…" />
              <CommandList className="max-h-96">
                <CommandEmpty>沒有候選任務。請先〔選職能基準參考〕。</CommandEmpty>
                <CommandGroup>
                  {rows.map((r, i) => {
                    const loc = locOf(r);
                    const locked = !!loc && loc.filled;
                    const home = doc && pack ? resolveHomeUnit(r, doc, pack, primary) : null;
                    return (
                      <CommandItem key={r.name} value={`${i} ${r.name}`} onSelect={() => toggle(r)}
                        className={"items-start " + (locked ? "opacity-60" : "")}>
                        <Check className={"mt-0.5 h-3.5 w-3.5 " + (loc ? "opacity-100" : "opacity-0")} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-xs text-muted-foreground">{i + 1}.</span>
                            <span className="flex-1">{r.name}</span>
                            {locked ? <Badge variant="secondary" className="text-[10px]" title="已填內容，請在表格刪除">已填</Badge> : null}
                          </div>
                          {!loc && home ? <div className="mt-0.5 text-[10px] text-sky-700">將掛入:{home.ocuName}職責</div> : null}
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
