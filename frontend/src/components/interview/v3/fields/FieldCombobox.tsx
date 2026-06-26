"use client";
import { useState } from "react";
import { Check, ChevronsUpDown, Plus, X } from "lucide-react";
import type { OptionItem } from "@/types";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";

type Item = { code: string; name: string };
const keyOf = (i: { code: string; name: string }) => i.code || "name:" + i.name;

export function FieldCombobox({
  label, value, options, allowCustom = false, onCommit, pillSources = false,
}: {
  label: string;
  value: Item[];
  options: OptionItem[];
  allowCustom?: boolean;
  onCommit: (next: Item[]) => void;
  pillSources?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const sel = new Set(value.map(keyOf));
  const sourcesOf = (k: string) => options.find((o) => keyOf(o) === k)?.sources ?? [];

  const toggle = (opt: { code: string; name: string }) => {
    const k = keyOf(opt);
    if (sel.has(k)) onCommit(value.filter((v) => keyOf(v) !== k));
    else onCommit([...value, { code: opt.code, name: opt.name }]);
  };
  const remove = (k: string) => onCommit(value.filter((v) => keyOf(v) !== k));
  const addCustom = () => {
    const n = query.trim();
    if (!n || value.some((v) => v.name === n)) { setQuery(""); return; }
    onCommit([...value, { code: "", name: n }]);
    setQuery("");
  };
  const selectAllOfficial = () => {
    const next = [...value];
    for (const o of options) if (!next.some((v) => keyOf(v) === keyOf(o))) next.push({ code: o.code, name: o.name });
    onCommit(next);
  };

  return (
    <div className="space-y-1.5">
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
      <div className="flex items-center gap-1.5">
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button type="button" variant="outline" size="sm" className="justify-between gap-1 text-xs">
              {label} <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-72">
            <Command>
              <CommandInput placeholder={allowCustom ? "搜尋或輸入自訂…" : "搜尋官方候選…"} value={query} onValueChange={setQuery} />
              <CommandList>
                <CommandEmpty>
                  {allowCustom && query.trim() ? (
                    <button type="button" className="inline-flex items-center gap-1 text-xs text-sky-700 hover:underline" onClick={addCustom}>
                      <Plus className="h-3 w-3" /> 新增「{query.trim()}」
                    </button>
                  ) : "無候選"}
                </CommandEmpty>
                <CommandGroup>
                  {options.map((o) => {
                    const k = keyOf(o);
                    return (
                      <CommandItem key={k} value={`${o.code} ${o.name}`} onSelect={() => toggle(o)}>
                        <Check className={"h-3.5 w-3.5 " + (sel.has(k) ? "opacity-100" : "opacity-0")} />
                        {o.code ? <span className="font-mono text-xs text-muted-foreground">{o.code}</span> : null}
                        <span className="flex-1">{o.name}</span>
                        {pillSources && (o.sources?.length ?? 0) > 1 ? <span className="text-[10px] text-sky-700">共 {o.sources!.length}</span> : null}
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
        <Button type="button" variant="ghost" size="sm" className="text-xs text-muted-foreground" onClick={selectAllOfficial}>帶官方</Button>
      </div>
    </div>
  );
}
