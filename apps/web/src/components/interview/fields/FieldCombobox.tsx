"use client";
import { useRef, useState } from "react";
import { Check, ChevronsUpDown, ChevronDown, Plus, X } from "lucide-react";
import type { OptionItem, SourceRef } from "@/types";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { FieldText } from "./FieldText";
import { SourceLine } from "./SourceLine";

type Item = { code: string; name: string; _id?: string; _src?: "official" | "custom"; _ref?: SourceRef };
const keyOf = (i: { code: string; name: string }) => i.code || "name:" + i.name;
const newId = () => (globalThis.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}`);

export function FieldCombobox({
  label, value, options, allowCustom = false, onCommit, pillSources = false,
  layout = "pills", title, customMode = "search", autoCode, editMultiline = false,
  defaults, autoApplyOnFirstOpen = false,
}: {
  label: string;
  value: Item[];
  options: OptionItem[];
  allowCustom?: boolean;
  onCommit: (next: Item[]) => void;
  pillSources?: boolean;
  layout?: "pills" | "list";
  // 有 title → 標題列（標題 + ▾ + 「+」加自訂 在右）+ 清單在下。
  title?: string;
  // search：搜尋框 + 輸入即新增；footer：無搜尋（自訂用右側「+」直接加空白列）。
  customMode?: "search" | "footer";
  // 設了前綴（如 "A"）→ 加的空白列暫定碼 A01…；OPKS 由 setter 依位置重編。
  autoCode?: string;
  // list 模式名稱欄是否多行（長文字如補充說明）。
  editMultiline?: boolean;
  // 「自動勾選」的目標集（該實體自己的官方配套）；未給 = 全部 options。
  defaults?: OptionItem[];
  // 首次打開選單且欄位為空 → 自動套 defaults（spec 2026-07-04 §4；之後以使用者為準）。
  autoApplyOnFirstOpen?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const sourcesOf = (k: string) => options.find((o) => keyOf(o) === k)?.sources ?? [];

  // 勾選判定(DDD 實體 vs 值物件)：選項帶來源身分（srcs 任一 {ocs_code, code} 命中 _ref）
  // → 官方同物（池的合併列 srcs 多筆、own-first 重排後 srcs[0] 未必是 _ref 那筆，必須掃全部）；
  // 無 code 來源(值物件，如說明事項)→ 比 name。改過內容的項目 _src 變 custom → 自動視為未勾選。
  const officialMatch = (v: Item, o: OptionItem) => {
    const coded = (o.srcs ?? []).filter((s) => s.code);
    if (coded.length > 0 || o.code) {
      if (v._ref && coded.some((s) => s.code === v._ref!.code && s.ocs_code === v._ref!.ocs_code)) return true;
      if (!coded.length && o.code) return v._ref?.code === o.code; // 無 srcs 的舊路徑（自訂候選）
      return false;
    }
    return v.name === o.name;
  };
  const isOfficialSelected = (o: OptionItem) =>
    value.some((v) => v._src === "official" && officialMatch(v, o));

  const toggle = (opt: OptionItem) => {
    if (isOfficialSelected(opt)) {
      onCommit(value.filter((v) => !(v._src === "official" && officialMatch(v, opt))));
      return;
    }
    const ref: SourceRef = opt.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: opt.code };
    onCommit([...value, { code: opt.code, name: opt.name, _id: newId(), _src: "official", _ref: ref }]);
  };
  const remove = (k: string) => onCommit(value.filter((v) => keyOf(v) !== k));
  const addCustomFromQuery = () => {
    const n = query.trim();
    if (!n || value.some((v) => v.name === n)) { setQuery(""); return; }
    onCommit([...value, { code: "", name: n, _id: newId(), _src: "custom" }]);
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
  // 「+」直接加一列空白自訂（就地編輯）。OPKS/態度由 setter 依位置重編碼，故給暫定碼即可。
  const addBlank = () => onCommit([...value, { code: autoCode ? nextCode(autoCode) : "", name: "", _id: newId(), _src: "custom" }]);
  // 自動勾選：套用 defaults（該實體自己的官方配套）；未給 defaults = 全部 options（舊「帶官方」行為）。
  const applyDefaults = () => {
    const next = [...value];
    for (const o of defaults ?? options) {
      if (next.some((v) => v._src === "official" && officialMatch(v, o))) continue; // 已選官方→跳過
      const ref: SourceRef = o.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: o.code };
      next.push({ code: o.code, name: o.name, _id: newId(), _src: "official", _ref: ref });
    }
    onCommit(next);
  };

  const toggleList = (
    <CommandGroup>
      {options.map((o, i) => {
        const k = keyOf(o);
        return (
          <CommandItem key={k} value={`${o.code} ${o.name}`} onSelect={() => toggle(o)} className="items-start">
            <Check className={"mt-0.5 h-3.5 w-3.5 " + (isOfficialSelected(o) ? "opacity-100" : "opacity-0")} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1">
                {/* W1：系統碼不上選單——無碼（池選項）顯序號；類別選單有真實分類碼照顯 */}
                <span className="font-mono text-xs text-muted-foreground">{o.code || `${i + 1}.`}</span>
                <span className="flex-1">{o.name}</span>
              </div>
              <SourceLine srcs={o.srcs} />
            </div>
          </CommandItem>
        );
      })}
    </CommandGroup>
  );

  // 選單頂列的「自動勾選」鈕(spec 2026-07-04 §4:鈕一律在選單內,外部按鈕列不再放)。
  const menuHeader = (
    <div className="mb-1 flex items-center justify-end px-1">
      <button type="button" className="shrink-0 text-xs text-muted-foreground hover:text-foreground"
        title="套用官方預設(勾上還沒選的)" onClick={applyDefaults}>
        自動勾選
      </button>
    </div>
  );

  const menu = customMode === "footer" ? (
    <Command>
      <CommandList>
        <CommandEmpty>無候選</CommandEmpty>
        {toggleList}
      </CommandList>
    </Command>
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

  const statusOf = (item: Item): "official" | "custom" =>
    item._src === "custom" ? "custom" : item._src === "official" ? "official" : "custom";

  const selectedView = layout === "list" ? (
    <div className="space-y-1">
      {value.map((v, idx) => {
        const status = statusOf(v);
        return (
          <div key={v._id ?? `${keyOf(v)}-${idx}`} className="flex items-start gap-2">
            {v.code ? <span className="mt-2 shrink-0 font-mono text-xs text-muted-foreground">{v.code}</span> : null}
            <div className="min-w-0 flex-1">
              <FieldText value={v.name} multiline={editMultiline}
                onCommit={(name) => onCommit(value.map((x, i) => (i === idx ? { ...x, name, _src: "custom" as const, _ref: undefined } : x)))} />
            </div>
            {status === "custom" ? (
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

  const autoApplied = useRef(false);
  const onMenuOpenChange = (o: boolean) => {
    setOpen(o);
    if (o && autoApplyOnFirstOpen && !autoApplied.current) {
      autoApplied.current = true;
      if (value.length === 0 && (defaults ?? []).length > 0) applyDefaults(); // 首開且空才套(spec §4)
    }
  };

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
              <PopoverContent className="w-72">{menuHeader}{menu}</PopoverContent>
            </Popover>
            <button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground" title="加自訂（空白列）" onClick={addBlank}>
              <Plus className="h-4 w-4" />
            </button>
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
          <PopoverContent className="w-72">{menuHeader}{menu}</PopoverContent>
        </Popover>
        <Button type="button" variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground" title="加自訂（空白列）" onClick={addBlank}>
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
