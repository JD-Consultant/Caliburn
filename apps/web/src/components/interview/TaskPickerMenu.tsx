"use client";

// 每職責列的「選任務 ▾」（P3 UI 修訂：遞迴選單落在表格上）：任務大池全列
// （不過濾不分組；序號＋引用行），自己的預勾、其餘可勾＝借用（`_ref` 照記）；
// 已在他職責 →「已加入」disabled。空職責首次開 → 自動帶入該職責官方任務
// （預勾統一規則：初次/按「自動勾選」時套用）。勾＝加入本職責；取消勾選＝
// 移除該任務（四格/級別/筆記皆空才可，有內容鎖定 → 表格刪）。
import { useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import type { KnowledgePack, OcsDocument } from "@/types";
import { addTasksToUnit, deleteTask, taskHasContent, type PoolPick } from "@/lib/ocsDoc";
import { taskRows, unitRows, type TaskRowVM } from "@/lib/pack";
import { taskUrns } from "@/lib/urn";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandItem, CommandList } from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";
import { SourceLine } from "./fields/SourceLine";

export function TaskPickerMenu({ document: doc, pack, unitIdx, onChange }: {
  document: OcsDocument;
  pack?: KnowledgePack;
  unitIdx: number;
  onChange: (d: OcsDocument) => void;
}) {
  const [open, setOpen] = useState(false);
  const applied = useRef(false); // 首開自動帶官方任務，一次為限（之後以使用者動過的為準）
  const rows = pack ? taskRows(pack) : [];
  const unit = doc.ocs_content?.ocu_units?.[unitIdx];
  // 本職責的官方任務集:以 unit._refs 的 (ocs_code, ocu_code) 對回 units 池列(身分對位,
  // spec 2026-07-04 §6;改過名的職責 _refs 已清 → 無 own=全借用,行為由身分導出)。
  const unitPairs = new Set((unit?._refs ?? [])
    .filter((r) => r.ocu_code)
    .map((r) => `${r.ocs_code}__${r.ocu_code}`));
  const ownKeys = pack && unit && unitPairs.size
    ? unitRows(pack)
        .filter((u) => u.srcs.some((s) => s.ocu_code && unitPairs.has(`${s.ocs_code}__${s.ocu_code}`)))
        .flatMap((u) => u.ownTaskKeys)
    : [];
  const unitOcc = unit?._refs?.[0]?.ocs_code || unit?.source?.ocs_code || "";

  // 文件內任務的 URN → 位置對照（判斷勾選狀態/已加入/可否移除）。
  const urnLoc = new Map<string, { u: number; t: number; filled: boolean }>();
  (doc.ocs_content?.ocu_units ?? []).forEach((uu, ui) => {
    (uu.tasks ?? []).forEach((tt, ti) => {
      for (const urn of taskUrns(tt)) urnLoc.set(urn, { u: ui, t: ti, filled: taskHasContent(tt) });
    });
  });
  const locOf = (row: TaskRowVM) => {
    for (const urn of row.urns) {
      const l = urnLoc.get(urn);
      if (l) return l;
    }
    return null;
  };

  // provenance 優先取「與本職責同職業」的來源（合併列雙來源時對到自己這邊）。
  const pickOf = (row: TaskRowVM): PoolPick["tasks"][number] => {
    const pref = row.srcs.find((s) => s.ocs_code === unitOcc) ?? row.srcs[0];
    return {
      name: row.name,
      srcs: row.srcs,
      provenance: { ocs_code: pref?.ocs_code ?? "", task_code: pref?.task_code ?? "" },
    };
  };

  const toggle = (row: TaskRowVM) => {
    const loc = locOf(row);
    if (!loc) {
      onChange(addTasksToUnit(doc, unitIdx, [pickOf(row)]));
      return;
    }
    if (loc.u !== unitIdx || loc.filled) return; // 他職責/有內容 → 鎖定
    onChange(deleteTask(doc, loc.u, loc.t));
  };

  // 自動勾選：補上本職責官方任務中還不在文件的（借用列不動）。
  const applyDefaults = () => {
    const picks = rows.filter((r) => ownKeys.includes(r.name) && !locOf(r)).map(pickOf);
    if (picks.length) onChange(addTasksToUnit(doc, unitIdx, picks));
  };

  const onOpenChange = (o: boolean) => {
    setOpen(o);
    if (o && !applied.current) {
      applied.current = true;
      if ((unit?.tasks?.length ?? 0) === 0) applyDefaults(); // 空職責首開＝套官方配套
    }
  };

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md border border-dashed px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          選任務
          <ChevronDown className="h-3.5 w-3.5 opacity-50" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-96" align="start">
        <div className="mb-1 flex items-center justify-between gap-2 px-1">
          <span className="text-xs text-muted-foreground">全部任務可選；他職責的＝借用</span>
          <button type="button" className="shrink-0 text-xs text-muted-foreground hover:text-foreground"
            title="補上本職責的官方任務" onClick={applyDefaults}>
            自動勾選
          </button>
        </div>
        <Command>
          <CommandList>
            <CommandEmpty>沒有候選任務。請先〔選職類〕。</CommandEmpty>
            <CommandGroup>
              {rows.map((r, i) => {
                const loc = locOf(r);
                const here = loc?.u === unitIdx;
                const elsewhere = !!loc && !here;
                const locked = elsewhere || (here && loc.filled);
                const isOwn = ownKeys.includes(r.name);
                return (
                  <CommandItem key={r.name} value={`${i} ${r.name}`} onSelect={() => toggle(r)}
                    className={"items-start " + (locked ? "opacity-60" : "")}>
                    <Check className={"mt-0.5 h-3.5 w-3.5 " + (loc ? "opacity-100" : "opacity-0")} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-xs text-muted-foreground">{i + 1}.</span>
                        <span className="flex-1">{r.name}</span>
                        {isOwn ? null : <Badge variant="outline" className="text-[10px]">借用</Badge>}
                        {elsewhere ? <span className="text-[10px] text-muted-foreground">已加入</span> : null}
                        {here && loc.filled ? <Badge variant="secondary" className="text-[10px]" title="已填內容，請在表格刪除">已填</Badge> : null}
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
