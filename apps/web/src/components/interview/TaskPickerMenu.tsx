"use client";

// 每職責列的「選任務」按鈕 → **獨立選單窗**(Modal;原下拉 Popover 太擠——任務大池
// 全列+來源行,東西太多):任務大池全列(不過濾不分組;✓+序號+引用行),自己的預勾、
// 其餘可勾＝借用(`_ref` 照記);已在他職責 →「已加入」disabled。空職責首次開 →
// 自動帶入該職責官方任務(預勾統一規則:初次/按「自動勾選」時套用)。勾＝加入本職責;
// 取消勾選＝移除該任務(四格/級別/筆記皆空才可,有內容鎖定 → 表格刪)。
// commit-per-click;與選職類/選職責/AI 任務盤同 Modal 家族。
import { useState } from "react";
import { Check, Pencil } from "lucide-react";
import type { KnowledgePack, OcsDocument } from "@/types";
import { addTasksToUnit, deleteTask, renameTask, taskHasContent, type PoolPick } from "@/lib/ocsDoc";
import { taskRowsWithSimilar, unitRows, type TaskRowVM } from "@/lib/pack";
import { taskUrns } from "@/lib/urn";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";
import { Modal } from "./OccupationPicker";
import { FieldText } from "./fields/FieldText";
import { SourceLine } from "./fields/SourceLine";

export function TaskPickerMenu({ document: doc, pack, unitIdx, onChange }: {
  document: OcsDocument;
  pack?: KnowledgePack;
  unitIdx: number;
  onChange: (d: OcsDocument) => void;
}) {
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null);
  const rows = pack ? taskRowsWithSimilar(pack) : []; // 灰區相似對掛 similarTo(純顯示,ADR 0022)
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

  // 選同主要職責：補上本職責官方任務中還不在文件的（借用列不動）。ADR 0029 不再首開自動觸發。
  const applyDefaults = () => {
    const picks = rows.filter((r) => ownKeys.includes(r.name) && !locOf(r)).map(pickOf);
    if (picks.length) onChange(addTasksToUnit(doc, unitIdx, picks));
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 rounded-md border border-dashed px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        選任務
      </button>
      {open ? (
        <Modal title={`選任務——${unit?.ocu_name || "職責"}`} onClose={() => { setOpen(false); setRenaming(null); }}>
          <div className="mb-2 flex items-center justify-between gap-2 px-1">
            <span className="text-xs text-muted-foreground">全部任務可選；他職責的＝借用</span>
            <button type="button" className="shrink-0 text-xs text-muted-foreground hover:text-foreground"
              title="補上本職責的官方任務" onClick={applyDefaults}>
              選同主要職責
            </button>
          </div>
          <div className="rounded-lg border">
            <Command className="bg-transparent">
              <CommandInput placeholder="搜尋任務…" />
              <CommandList className="max-h-96">
                <CommandEmpty>沒有候選任務。請先〔選職類〕。</CommandEmpty>
                <CommandGroup>
                  {rows.map((r, i) => {
                    const loc = locOf(r);
                    const here = loc?.u === unitIdx;
                    const elsewhere = !!loc && !here;
                    const locked = elsewhere || (here && loc.filled);
                    const isOwn = ownKeys.includes(r.name);
                    const curName = here ? (doc.ocs_content.ocu_units[loc!.u].tasks[loc!.t].task_codes?.[0]?.name ?? r.name) : r.name;
                    const renamed = here && curName !== r.name;
                    if (here && renaming === r.name) {
                      return (
                        <div key={r.name} className="flex items-start gap-2 px-2 py-1.5">
                          <Check className="mt-0.5 h-3.5 w-3.5 opacity-100" />
                          <div className="min-w-0 flex-1">
                            <FieldText value={curName} autoFocus
                              onCommit={(v) => { onChange(renameTask(doc, loc!.u, loc!.t, v)); setRenaming(null); }} />
                            {renamed ? <div className="mt-0.5 text-[10px] text-muted-foreground">原名:{r.name}</div> : null}
                            <SourceLine srcs={r.srcs} />
                          </div>
                        </div>
                      );
                    }
                    return (
                      <CommandItem key={r.name} value={`${i} ${r.name}`} onSelect={() => toggle(r)}
                        className={"group items-start " + (locked ? "opacity-60" : "")}>
                        <Check className={"mt-0.5 h-3.5 w-3.5 " + (loc ? "opacity-100" : "opacity-0")} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-xs text-muted-foreground">{i + 1}.</span>
                            <span className="flex-1">{renamed ? curName : r.name}</span>
                            {here ? (
                              <button type="button" title="改名（保留來源）"
                                className="shrink-0 text-muted-foreground opacity-0 hover:text-foreground group-hover:opacity-100"
                                onClick={(e) => { e.stopPropagation(); setRenaming(r.name); }}>
                                <Pencil className="h-3 w-3" />
                              </button>
                            ) : null}
                            {isOwn ? null : <Badge variant="outline" className="text-[10px]">借用</Badge>}
                            {elsewhere ? <span className="text-[10px] text-muted-foreground">已加入</span> : null}
                            {here && loc.filled ? <Badge variant="secondary" className="text-[10px]" title="已填內容，請在表格刪除">已填</Badge> : null}
                            {r.similarTo ? (
                              // 相似徽章(ADR 0022):灰區對純顯示——不自動勾、不合併、不擋;
                              // 點開並排全文由人判斷是否同一件事。
                              <Popover>
                                <PopoverTrigger asChild>
                                  <button type="button"
                                    className="shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-700 hover:bg-amber-200"
                                    onClick={(e) => e.stopPropagation()}>
                                    ⚠ 與 {r.similarTo.length} 項相似
                                  </button>
                                </PopoverTrigger>
                                <PopoverContent className="w-80 text-xs" onClick={(e) => e.stopPropagation()}>
                                  <p className="mb-1 font-medium">相似任務(請確認是否為同一件事):</p>
                                  <p className="rounded bg-muted/50 p-1">{r.name}</p>
                                  {r.similarTo.map((s) => (
                                    <p key={s.name} className="mt-1 rounded border p-1">
                                      {s.name}
                                      <span className="ml-1 text-muted-foreground">{Math.round(s.score * 100)}%</span>
                                    </p>
                                  ))}
                                </PopoverContent>
                              </Popover>
                            ) : null}
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
