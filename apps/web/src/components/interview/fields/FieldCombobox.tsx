"use client";
import { useState, type ReactNode } from "react";
import { Check, ChevronsUpDown, ChevronDown, Pencil, Plus, X } from "lucide-react";
import type { OptionItem, SourceRef } from "@/types";
import { docItemForOption, itemMatchesOption, optionInDoc, originalNameNote, renamedRefItem } from "@/lib/pack";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { FieldText } from "./FieldText";
import { SourceLine } from "./SourceLine";

type Item = { code: string; name: string; _id?: string; _src?: "official" | "custom"; _ref?: SourceRef };
const keyOf = (i: { code: string; name: string }) => i.code || "name:" + i.name;
const newId = () => (globalThis.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}`);

// 參考選單(ADR 0029):多選、列內改名(僅已勾列、改字不斷根=保留 _ref)、改名後顯原名副行;
// 無自訂 footer(自訂回表格加列走「＋」)、無首開自動寫;窗頂搜尋框;批次帶入鈕＝「選同X」。
export function FieldCombobox({
  label = "選/加", value, options, onCommit, pillSources = false,
  layout = "pills", title, autoCode, editMultiline = false,
  defaults, autoApplyLabel = "選同職能基準", gridLayout = false, badge,
}: {
  label?: string;
  value: Item[];
  options: OptionItem[];
  onCommit: (next: Item[]) => void;
  pillSources?: boolean;
  layout?: "pills" | "list";
  // 有 title → 標題列（標題 + ▾ + 「+」加自訂 在右）+ 清單在下。
  title?: string;
  // 設了前綴（如 "A"）→ 加的空白列暫定碼 A01…；OPKS 由 setter 依位置重編。
  autoCode?: string;
  // list 模式名稱欄是否多行（長文字如補充說明）。
  editMultiline?: boolean;
  // 「選同X」批次帶入的目標集（該實體自己的官方配套）；空 → 批次鈕停用（未選/無來源）。
  defaults?: OptionItem[];
  // 批次帶入鈕文案（選同工作任務／選同職能基準…；ADR 0029 取代舊「自動勾選」）。
  autoApplyLabel?: string;
  // OPLKS 版式(spec §7):左欄=標籤+▾、右欄=內容全列+格底＋自訂(需 title)。
  gridLayout?: boolean;
  // 標籤旁徽章(如 D7 AI 待審標記;最小適配)。
  badge?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null);
  // 相似比對群(ADR 0022):展開狀態(key = 代表列 keyOf)。分群是 render-only 顯示變換。
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggleExpand = (k: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k); else next.add(k);
      return next;
    });
  const sourcesOf = (k: string) => options.find((o) => keyOf(o) === k)?.sources ?? [];

  // 勾＝加入本值(帶來源身分);取消勾＝**按身分**移除(不看 _src,改過名仍能取消)。
  const toggle = (opt: OptionItem) => {
    if (value.some((v) => itemMatchesOption(v, opt))) {
      onCommit(value.filter((v) => !itemMatchesOption(v, opt)));
      return;
    }
    const ref: SourceRef = opt.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: opt.code };
    onCommit([...value, { code: opt.code, name: opt.name, _id: newId(), _src: "official", _ref: ref }]);
  };
  const remove = (k: string) => onCommit(value.filter((v) => keyOf(v) !== k));
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
  // 改文件那筆的名字（改字不斷根：保留 _ref/身分；勾選不掉、可顯原名副行）。
  const renameItem = (item: Item, name: string) =>
    onCommit(value.map((v) => (v === item ? renamedRefItem(v, name) : v)));
  // 「選同X」批次帶入：套 defaults 中還不在文件的（身分已在→跳過）。
  const applyDefaults = () => {
    const next = [...value];
    for (const o of defaults ?? []) {
      if (next.some((v) => itemMatchesOption(v, o))) continue;
      const ref: SourceRef = o.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: o.code };
      next.push({ code: o.code, name: o.name, _id: newId(), _src: "official", _ref: ref });
    }
    onCommit(next);
  };

  const renameRow = (o: OptionItem, mine: Item, i: number) => (
    <div key={keyOf(o)} className="flex items-start gap-2 px-2 py-1.5">
      <Check className="mt-0.5 h-3.5 w-3.5 opacity-100" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1">
          <span className="font-mono text-xs text-muted-foreground">{o.code || `${i + 1}.`}</span>
          <div className="min-w-0 flex-1">
            <FieldText value={mine.name} autoFocus multiline={editMultiline}
              onCommit={(name) => { renameItem(mine, name); setRenaming(null); }} />
          </div>
        </div>
        {mine.name !== o.name ? <div className="mt-0.5 text-[10px] text-muted-foreground">原名:{o.name}</div> : null}
        <SourceLine srcs={o.srcs} />
      </div>
    </div>
  );

  const optionRow = (o: OptionItem, i: number) => {
    const k = keyOf(o);
    const mine = docItemForOption(value, o);
    if (mine && renaming === k) return renameRow(o, mine, i);
    const groupChecked = optionInDoc(value, o);
    const orig = originalNameNote(value, o);
    const shown = mine && mine.name !== o.name ? mine.name : o.name;
    return (
      <div key={k}>
        <CommandItem value={`${o.code} ${o.name}`} onSelect={() => toggle(o)} className="group items-start">
          <Check className={"mt-0.5 h-3.5 w-3.5 " + (groupChecked ? "opacity-100" : "opacity-0")} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1">
              {/* W1：系統碼不上選單——無碼（池選項）顯序號；類別選單有真實分類碼照顯 */}
              <span className="font-mono text-xs text-muted-foreground">{o.code || `${i + 1}.`}</span>
              <span className="flex-1">{shown}</span>
              {mine ? (
                // 列內改名（僅已勾列）：hover 才浮現鉛筆；改的就是文件那筆。
                <button type="button" title="改名（保留來源）"
                  className="shrink-0 text-muted-foreground opacity-0 hover:text-foreground group-hover:opacity-100"
                  onClick={(e) => { e.stopPropagation(); setRenaming(k); }}>
                  <Pencil className="h-3 w-3" />
                </button>
              ) : null}
              {(o.variants?.length ?? 0) > 0 ? (
                <button type="button"
                  className="shrink-0 rounded bg-sky-100 px-1 text-[10px] text-sky-700 hover:bg-sky-200"
                  title="相似版本(不同基準的近似措辭),展開可改選"
                  onClick={(e) => { e.stopPropagation(); toggleExpand(k); }}>
                  {(o.variants!.length + 1)} 個版本 {expanded.has(k) ? "▴" : "▾"}
                </button>
              ) : null}
            </div>
            {orig ? <div className="mt-0.5 text-[10px] text-muted-foreground">原名:{orig}</div> : null}
            <SourceLine srcs={o.srcs} />
          </div>
        </CommandItem>
        {expanded.has(k)
          ? (o.variants ?? []).map((v) => (
              <CommandItem key={keyOf(v) + "-variant"} value={`${v.code} ${v.name}`}
                onSelect={() => toggle(v)} className="items-start pl-8">
                <Check className={"mt-0.5 h-3.5 w-3.5 " + (optionInDoc(value, v) ? "opacity-100" : "opacity-0")} />
                <div className="min-w-0 flex-1">
                  <span>{v.name}</span>
                  <SourceLine srcs={v.srcs} />
                </div>
              </CommandItem>
            ))
          : null}
      </div>
    );
  };

  const menuHeader = (
    <div className="mb-1 flex items-center justify-end px-1">
      <button type="button" disabled={(defaults ?? []).length === 0}
        className="shrink-0 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40"
        title="補上官方配套（還沒在文件的）" onClick={applyDefaults}>
        {autoApplyLabel}
      </button>
    </div>
  );

  // 窗頂搜尋框（全列照舊，打字只過濾；ADR 0029）。
  const menu = (
    <Command>
      <CommandInput placeholder="搜尋候選…" />
      <CommandList>
        <CommandEmpty>無候選</CommandEmpty>
        <CommandGroup>{options.map((o, i) => optionRow(o, i))}</CommandGroup>
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
                onCommit={(name) => onCommit(value.map((x, i) => (i === idx ? renamedRefItem(x, name) : x)))} />
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

  const onMenuOpenChange = (o: boolean) => { setOpen(o); if (!o) setRenaming(null); };

  const menuTrigger = (
    <Popover open={open} onOpenChange={onMenuOpenChange}>
      <PopoverTrigger asChild>
        <button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground" title="選/加">
          <ChevronDown className="h-4 w-4" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-72">{menuHeader}{menu}</PopoverContent>
    </Popover>
  );

  // OPLKS 版式(spec §7):左欄=標籤+▾、右欄=內容全列+格底＋自訂。逐層縮排、hover 才見工具。
  if (title !== undefined && gridLayout) {
    return (
      <div className="flex items-start gap-3">
        <div className="flex w-40 shrink-0 items-center gap-1 pt-1">
          <span className="text-sm font-medium">{title}</span>
          {badge}
          {menuTrigger}
        </div>
        <div className="min-w-0 flex-1">
          {selectedView}
          <button type="button" className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground opacity-60 hover:text-foreground hover:opacity-100" onClick={addBlank}>
            <Plus className="h-3 w-3" /> 加自訂
          </button>
        </div>
      </div>
    );
  }

  // 標題模式：標題 + ▾ + 帶官方 在右，清單在下（同所屬類別/基準級別）。
  if (title !== undefined) {
    return (
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium">{title}{badge}</span>
          <div className="flex items-center gap-1.5">
            {menuTrigger}
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
