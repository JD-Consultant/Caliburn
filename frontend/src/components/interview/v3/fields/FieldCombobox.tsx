"use client";
import { useState } from "react";
import { Check, ChevronsUpDown, ChevronDown, Plus, X } from "lucide-react";
import type { OptionItem } from "@/types";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { FieldText } from "./FieldText";

type Item = { code: string; name: string };
const keyOf = (i: { code: string; name: string }) => i.code || "name:" + i.name;

export function FieldCombobox({
  label, value, options, allowCustom = false, onCommit, pillSources = false,
  layout = "pills", title, customMode = "search", footerWithCode = true, autoCode, editMultiline = false,
}: {
  label: string;
  value: Item[];
  options: OptionItem[];
  allowCustom?: boolean;
  onCommit: (next: Item[]) => void;
  pillSources?: boolean;
  layout?: "pills" | "list";
  // 有 title → 標題列（標題 + ▾ 在右）+ 清單在下（同所屬類別/基準級別）。
  title?: string;
  // search：搜尋框 + 輸入即新增；footer：無搜尋 + 底部「＋ 加自訂」（同所屬類別）。
  customMode?: "search" | "footer";
  footerWithCode?: boolean;
  // 設了前綴（如 "A"）→ 自訂只填名稱、代碼自動遞增（A01、A02…）。
  autoCode?: string;
  // list 模式名稱欄是否多行（長文字如補充說明）。
  editMultiline?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState(false);
  const [cCode, setCCode] = useState("");
  const [cName, setCName] = useState("");
  const sel = new Set(value.map(keyOf));
  const sourcesOf = (k: string) => options.find((o) => keyOf(o) === k)?.sources ?? [];

  const toggle = (opt: { code: string; name: string }) => {
    const k = keyOf(opt);
    if (sel.has(k)) onCommit(value.filter((v) => keyOf(v) !== k));
    else onCommit([...value, { code: opt.code, name: opt.name }]);
  };
  const remove = (k: string) => onCommit(value.filter((v) => keyOf(v) !== k));
  const addCustomFromQuery = () => {
    const n = query.trim();
    if (!n || value.some((v) => v.name === n)) { setQuery(""); return; }
    onCommit([...value, { code: "", name: n }]);
    setQuery("");
  };
  const nextCode = (prefix: string) => {
    const esc = prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(`^${esc}(\\d+)$`);
    let max = 0;
    for (const c of [...value, ...options]) {
      const m = re.exec(c.code || "");
      if (m) max = Math.max(max, parseInt(m[1], 10));
    }
    // 純字母前綴（A/K/S）補零到 2 位（A01）；含數字/點的任務範圍前綴（O1.1.）不補零（O1.1.1）。
    const pad = /^[A-Za-z]+$/.test(prefix) ? 2 : 0;
    return `${prefix}${String(max + 1).padStart(pad, "0")}`;
  };
  const confirmFooterAdd = () => {
    const n = cName.trim();
    if (!n) return;
    const code = autoCode ? nextCode(autoCode) : footerWithCode ? cCode.trim() : "";
    onCommit([...value, { code, name: n }]);
    setCCode(""); setCName(""); setAdding(false);
  };
  const selectAllOfficial = () => {
    const next = [...value];
    for (const o of options) if (!next.some((v) => keyOf(v) === keyOf(o))) next.push({ code: o.code, name: o.name });
    onCommit(next);
  };

  const toggleList = (
    <CommandGroup>
      {options.map((o) => {
        const k = keyOf(o);
        return (
          <CommandItem key={k} value={`${o.code} ${o.name}`} onSelect={() => toggle(o)}>
            <Check className={"h-3.5 w-3.5 " + (sel.has(k) ? "opacity-100" : "opacity-0")} />
            {o.code ? <span className="font-mono text-xs text-muted-foreground">{o.code}</span> : null}
            <span className="flex-1">{o.name}</span>
            {value.some((e) => e.code && e.code === o.code && e.name !== o.name) ? (
              <span className="ml-1 shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-700">已改</span>
            ) : null}
            {pillSources && (o.sources?.length ?? 0) > 1 ? <span className="text-[10px] text-sky-700">共 {o.sources!.length}</span> : null}
          </CommandItem>
        );
      })}
    </CommandGroup>
  );

  const menu = customMode === "footer" ? (
    <>
      <Command>
        <CommandList>
          <CommandEmpty>無候選</CommandEmpty>
          {toggleList}
        </CommandList>
      </Command>
      <div className="border-t p-1.5">
        {adding ? (
          <div className="flex items-center gap-1">
            {footerWithCode && !autoCode ? (
              <input autoFocus className="w-16 rounded border px-1.5 py-1 text-xs" placeholder="代碼" value={cCode} onChange={(e) => setCCode(e.target.value)} />
            ) : null}
            <input autoFocus={!(footerWithCode && !autoCode)} className="min-w-0 flex-1 rounded border px-1.5 py-1 text-xs" placeholder="名稱" value={cName}
              onChange={(e) => setCName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); confirmFooterAdd(); } else if (e.key === "Escape") setAdding(false); }} />
            <button type="button" className="shrink-0 rounded border px-2 py-1 text-xs hover:bg-accent" onClick={confirmFooterAdd}>加</button>
          </div>
        ) : (
          <button type="button" className="flex w-full items-center justify-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-accent" onClick={() => setAdding(true)}>
            <Plus className="h-3.5 w-3.5" /> 加自訂
          </button>
        )}
      </div>
    </>
  ) : (
    <Command>
      <CommandInput placeholder={allowCustom ? "搜尋或輸入自訂…" : "搜尋官方候選…"} value={query} onValueChange={setQuery} />
      <CommandList>
        <CommandEmpty>
          {allowCustom && query.trim() ? (
            <button type="button" className="inline-flex items-center gap-1 text-xs text-sky-700 hover:underline" onClick={addCustomFromQuery}>
              <Plus className="h-3 w-3" /> 新增「{query.trim()}」
            </button>
          ) : "無候選"}
        </CommandEmpty>
        {toggleList}
      </CommandList>
    </Command>
  );

  const statusOf = (item: Item): "official" | "edited" | "custom" => {
    if (options.some((o) => o.code === item.code && o.name === item.name)) return "official";
    if (item.code && options.some((o) => o.code === item.code)) return "edited";
    return "custom";
  };
  const officialNameOf = (code: string) => options.find((o) => o.code === code)?.name ?? "";

  const selectedView = layout === "list" ? (
    <div className="space-y-1">
      {value.map((v, idx) => {
        const status = statusOf(v);
        return (
          <div key={`${keyOf(v)}-${idx}`} className="flex items-start gap-2">
            {v.code ? <span className="mt-2 shrink-0 font-mono text-xs text-muted-foreground">{v.code}</span> : null}
            <div className="min-w-0 flex-1">
              <FieldText value={v.name} multiline={editMultiline}
                onCommit={(name) => onCommit(value.map((x, i) => (i === idx ? { ...x, name } : x)))} />
            </div>
            {status === "edited" ? (
              <span className="mt-2 shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-700" title={`已改（官方原為：${officialNameOf(v.code)}）`}>已改</span>
            ) : status === "custom" ? (
              <span className="mt-2 shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-700" title="自訂項目">自訂</span>
            ) : null}
            <button type="button" className="mt-2 shrink-0 text-muted-foreground hover:text-destructive" onClick={() => onCommit(value.filter((_, i) => i !== idx))}><X className="h-3.5 w-3.5" /></button>
          </div>
        );
      })}
    </div>
  ) : (
    <div className="flex flex-wrap gap-1">
      {value.map((v) => {
        const k = keyOf(v);
        const n = pillSources ? sourcesOf(k).length : 0;
        return (
          <span key={k} className="inline-flex items-center gap-1 rounded-full border bg-muted/50 px-2 py-0.5 text-xs">
            {v.code ? <span className="font-mono text-muted-foreground">{v.code}</span> : null}
            <span>{v.name}</span>
            {n > 1 ? <span className="rounded bg-sky-100 px-1 text-[10px] text-sky-700" title={"來自：" + sourcesOf(k).join("、")}>共 {n}</span> : null}
            <button type="button" className="text-muted-foreground hover:text-destructive" onClick={() => remove(k)}><X className="h-3 w-3" /></button>
          </span>
        );
      })}
    </div>
  );

  const onMenuOpenChange = (o: boolean) => { setOpen(o); if (!o) setAdding(false); };

  // 標題模式：標題 + ▾ + 帶官方 在右，清單在下（同所屬類別/基準級別）。
  if (title !== undefined) {
    return (
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium">{title}</span>
          <div className="flex items-center gap-1.5">
            <Popover open={open} onOpenChange={onMenuOpenChange}>
              <PopoverTrigger asChild>
                <button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground" title="選/加">
                  <ChevronDown className="h-4 w-4" />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-72">{menu}</PopoverContent>
            </Popover>
            <button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={selectAllOfficial}>帶官方</button>
          </div>
        </div>
        {selectedView}
      </div>
    );
  }

  // 預設模式：清單/pills 在上，觸發鈕在下。
  return (
    <div className="space-y-1.5">
      {selectedView}
      <div className="flex items-center gap-1.5">
        <Popover open={open} onOpenChange={onMenuOpenChange}>
          <PopoverTrigger asChild>
            <Button type="button" variant="outline" size="sm" className="justify-between gap-1 text-xs">
              {label} <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-72">{menu}</PopoverContent>
        </Popover>
        <Button type="button" variant="ghost" size="sm" className="text-xs text-muted-foreground" onClick={selectAllOfficial}>帶官方</Button>
      </div>
    </div>
  );
}
