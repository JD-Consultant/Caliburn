"use client";

// D27 官方職能基準「表頭」版型（5 欄對齊官方表格，可編輯/可自訂）。
// 代碼↔名稱綁定（選官方基準下拉）；所屬類別三類各列為 名稱|代碼（可手打自訂、加列刪列），
// 並提供「選官方▾」下拉把官方 {code,name} 綁定帶入；工作描述/級別預填可改+帶官方。
import { useState, type ReactNode } from "react";
import { Check, ChevronDown, Plus, X } from "lucide-react";
import type { OcsDocument, OptionItem } from "@/types";
import { useHeaderMeta } from "@/hooks/useDocument";
import { categoryOptions, primaryOptions } from "@/lib/headerMeta";
import {
  deleteCategory,
  setCategory,
  setOcsLevel,
  setOcsName,
  setPrimaryBasis,
  setProfileField,
  upsertCategory,
  type CatKind,
} from "@/lib/ocsDoc";
import { FieldText } from "./fields/FieldText";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandItem, CommandList } from "@/components/ui/command";

const TH = "border bg-muted/50 px-3 py-2 text-left align-middle font-medium whitespace-nowrap";
const TD = "border align-middle px-1";

const KINDS: { key: CatKind; label: string; codeLabel: string }[] = [
  { key: "job_categories", label: "職類別", codeLabel: "職類別代碼" },
  { key: "occupations", label: "職業別", codeLabel: "職業別代碼" },
  { key: "industries", label: "行業別", codeLabel: "行業別代碼" },
];

const ekey = (i: { code: string; name: string }) => i.code || "name:" + i.name;

// 每類別的「選/加 ▾」下拉：官方候選可勾選/取消勾選（toggle）；
// 底部「＋」展開一列 代碼／名稱／[加] 加自訂。
function CategoryPicker({ options, existing, onToggle, onAddCustom }: {
  options: OptionItem[];
  existing: { code: string; name: string }[];
  onToggle: (o: OptionItem) => void;
  onAddCustom: (code: string, name: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const has = (o: OptionItem) => existing.some((e) => ekey(e) === ekey(o));
  const confirmAdd = () => {
    const n = name.trim();
    if (!n) return;
    onAddCustom(code.trim(), n);
    setCode(""); setName(""); setAdding(false);
  };
  return (
    <Popover open={open} onOpenChange={(o) => { setOpen(o); if (!o) setAdding(false); }}>
      <PopoverTrigger asChild>
        <button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground" title="選/加">
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-72">
        <Command>
          <CommandList>
            <CommandEmpty>無候選</CommandEmpty>
            <CommandGroup>
              {options.map((o) => (
                <CommandItem key={ekey(o)} value={`${o.code} ${o.name}`} onSelect={() => onToggle(o)}>
                  <Check className={"h-3.5 w-3.5 " + (has(o) ? "opacity-100" : "opacity-0")} />
                  {o.code ? <span className="font-mono text-xs text-muted-foreground">{o.code}</span> : null}
                  <span className="flex-1">{o.name}</span>
                  {existing.some((e) => e.code && e.code === o.code && e.name !== o.name) ? (
                    <span className="ml-1 shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-700">已改</span>
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
        <div className="border-t p-1.5">
          {adding ? (
            <div className="flex items-center gap-1">
              <input autoFocus className="w-16 rounded border px-1.5 py-1 text-xs" placeholder="代碼" value={code} onChange={(e) => setCode(e.target.value)} />
              <input className="min-w-0 flex-1 rounded border px-1.5 py-1 text-xs" placeholder="名稱" value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); confirmAdd(); } else if (e.key === "Escape") setAdding(false); }} />
              <button type="button" className="shrink-0 rounded border px-2 py-1 text-xs hover:bg-accent" onClick={confirmAdd}>加</button>
            </div>
          ) : (
            <button type="button" className="flex w-full items-center justify-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-accent" onClick={() => setAdding(true)}>
              <Plus className="h-3.5 w-3.5" /> 加自訂
            </button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

// 來源標記（只標非官方）：官方原樣→不標（乾淨像官方表）；edited→「已改」；custom→「自訂」。
function Marker({ status, official }: {
  status: "official" | "edited" | "custom";
  official?: string;
}) {
  if (status === "official") return null;
  return (
    <span className="shrink-0 rounded bg-amber-100 px-1 py-0.5 text-[10px] text-amber-700"
      title={status === "edited" ? `已改（官方原為：${official ?? ""}）` : "自訂項目"}>
      {status === "edited" ? "已改" : "自訂"}
    </span>
  );
}

// 單值「選官方」選單：列官方候選，點一個即填入（值仍可在欄位編輯）。
function OfficialMenu({ trigger, options, onPick }: {
  trigger: ReactNode;
  options: { value: string; label: string; hint?: string }[];
  onPick: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent className="w-72">
        <Command>
          <CommandList>
            <CommandEmpty>無官方候選</CommandEmpty>
            <CommandGroup>
              {options.map((o, i) => (
                <CommandItem key={i} value={`${o.label}-${i}`} onSelect={() => { onPick(o.value); setOpen(false); }}>
                  <span className="flex-1 truncate">{o.label}</span>
                  {o.hint ? <span className={"ml-1 shrink-0 rounded px-1 text-[10px] " + (o.hint === "已改" ? "bg-amber-100 text-amber-700" : "text-sky-700")}>{o.hint}</span> : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export function DocHeader({ document: doc, profileId, onChange }: {
  document: OcsDocument;
  profileId: string;
  onChange: (d: OcsDocument) => void;
}) {
  const p = doc.ocs_profile;
  const { data: meta } = useHeaderMeta(profileId, !!p.ocs_code);
  const opts = meta ? primaryOptions(meta) : [];
  const catOptions = (kind: CatKind): OptionItem[] => (meta ? categoryOptions(meta, kind) : []);
  const catStatus = (kind: CatKind, e: { code: string; name: string }): "official" | "edited" | "custom" => {
    const options = catOptions(kind);
    if (!e.name && !e.code) return "custom";
    if (options.some((o) => o.code === e.code && o.name === e.name)) return "official";
    if (e.code && options.some((o) => o.code === e.code)) return "edited";
    return "custom";
  };

  // 下拉勾選：官方項已在→取消（移除），不在→加入（綁定 name+code）。
  const toggleOfficial = (kind: CatKind, o: OptionItem) => {
    const existing = p.category?.[kind] ?? [];
    if (existing.some((e) => ekey(e) === ekey(o)))
      onChange(setCategory(doc, kind, existing.filter((e) => ekey(e) !== ekey(o))));
    else
      onChange(setCategory(doc, kind, [...existing, { code: o.code, name: o.name }]));
  };
  // 下拉底部「加自訂」：加一列 {code,name}（代碼/名稱皆可填）。
  const addCustom = (kind: CatKind, code: string, name: string) => {
    const existing = p.category?.[kind] ?? [];
    if (existing.some((e) => e.name === name && e.code === code)) return;
    onChange(setCategory(doc, kind, [...existing, { code, name }]));
  };

  // 攤平成多列：每類至少一列（空則一列可填的虛擬列）；子類別/代碼標籤只在該類第一列 rowSpan。
  const catRows = KINDS.flatMap((k) => {
    const entries = p.category?.[k.key] ?? [];
    const rows = entries.length ? entries : [{ name: "", code: "" }];
    return rows.map((e, i) => ({
      ...k, idx: i, name: e.name, code: e.code,
      real: i < entries.length, firstOfKind: i === 0, kindCount: rows.length,
    }));
  });

  return (
    <table className="w-full table-fixed border-collapse overflow-hidden rounded-lg border text-sm">
      <colgroup>
        <col className="w-24" /><col className="w-20" /><col /><col className="w-24" /><col className="w-32" />
      </colgroup>
      <tbody>
        {/* 職能基準代碼：▾ 在標籤旁，選官方基準 → code+名稱綁定一起帶；值顯示於格 */}
        <tr>
          <th className={TH} colSpan={2}>
            <div className="flex items-center justify-between gap-1">
              <span>職能基準代碼</span>
              <OfficialMenu
                trigger={<button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground" title="選職能基準"><ChevronDown className="h-3.5 w-3.5" /></button>}
                options={opts.map((o) => ({ value: o.ocs_code, label: `${o.ocs_code}　${o.occupation_name}` }))}
                onPick={(code) => {
                  const o = opts.find((x) => x.ocs_code === code);
                  if (o) onChange(setPrimaryBasis(doc, { ocs_code: o.ocs_code, occupation_name: o.occupation_name, job_category_name: o.job_category_name || "" }));
                }}
              />
            </div>
          </th>
          <td className={TD} colSpan={3}>
            <span className="px-1.5 font-mono text-sm">{p.ocs_code || "—"}</span>
          </td>
        </tr>

        {/* 職能基準名稱（職類/職業，擇一填寫；可改） */}
        <tr>
          <th className={TH} rowSpan={2}>
            職能基準名稱
            <div className="text-xs font-normal text-muted-foreground">（擇一填寫）</div>
          </th>
          <th className={TH}>職類</th>
          <td className={TD} colSpan={3}>
            <FieldText value={p.ocs_name?.job_category_name ?? ""} placeholder="職類名稱"
              onCommit={(v) => onChange(setOcsName(doc, "job_category_name", v))} />
          </td>
        </tr>
        <tr>
          <th className={TH}>職業</th>
          <td className={TD} colSpan={3}>
            <FieldText value={p.ocs_name?.occupation_name ?? ""} placeholder="職業名稱"
              onCommit={(v) => onChange(setOcsName(doc, "occupation_name", v))} />
          </td>
        </tr>

        {/* 所屬類別（職類別/職業別/行業別）：名稱|代碼 可手打自訂、加列刪列 + 選官方▾ */}
        {catRows.map((r, gi) => (
          <tr key={`${r.key}-${r.idx}`}>
            {gi === 0 ? <th className={TH} rowSpan={catRows.length}>所屬類別</th> : null}
            {r.firstOfKind ? (
              <th className={TH} rowSpan={r.kindCount}>
                <div className="flex items-center justify-between gap-1">
                  <span>{r.label}</span>
                  <CategoryPicker
                    options={catOptions(r.key)}
                    existing={p.category?.[r.key] ?? []}
                    onToggle={(o) => toggleOfficial(r.key, o)}
                    onAddCustom={(code, name) => addCustom(r.key, code, name)}
                  />
                </div>
              </th>
            ) : null}
            <td className={TD}>
              <div className="flex items-center gap-1.5">
                <div className="min-w-0 flex-1">
                  <FieldText value={r.name} placeholder="名稱（可自訂）"
                    onCommit={(v) => onChange(upsertCategory(doc, r.key, r.idx, "name", v))} />
                </div>
                {r.real ? (
                  <Marker status={catStatus(r.key, { code: r.code, name: r.name })}
                    official={catOptions(r.key).find((o) => o.code === r.code)?.name} />
                ) : null}
              </div>
            </td>
            {r.firstOfKind ? <th className={TH} rowSpan={r.kindCount}>{r.codeLabel}</th> : null}
            <td className={TD}>
              <div className="flex items-center gap-1">
                <div className="flex-1">
                  <FieldText value={r.code} placeholder="代碼"
                    onCommit={(v) => onChange(upsertCategory(doc, r.key, r.idx, "code", v))} />
                </div>
                {r.real ? (
                  <button type="button" className="shrink-0 text-muted-foreground hover:text-destructive" title="刪除此列" onClick={() => onChange(deleteCategory(doc, r.key, r.idx))}>
                    <X className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </div>
            </td>
          </tr>
        ))}

        {/* 工作描述：▾ 在標籤旁（同所屬類別），textarea 自動長高/縮短 */}
        <tr>
          <th className={TH} colSpan={2}>
            <div className="flex items-center justify-between gap-1">
              <span>工作描述</span>
              <OfficialMenu
                trigger={<button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground" title="加入官方描述（加到下一行）"><ChevronDown className="h-3.5 w-3.5" /></button>}
                options={opts.filter((o) => o.job_description).map((o) => ({ value: o.job_description, label: `${o.ocs_code}　${o.occupation_name}` }))}
                onPick={(v) => { const curDesc = p.job_description ?? ""; onChange(setProfileField(doc, "job_description", curDesc.trim() ? `${curDesc}\n\n${v}` : v)); }}
              />
            </div>
          </th>
          <td className={TD} colSpan={3}>
            <FieldText multiline value={p.job_description ?? ""} placeholder="（本職務的工作描述）"
              onCommit={(v) => onChange(setProfileField(doc, "job_description", v))} />
          </td>
        </tr>

        {/* 基準級別：▾ 在標籤旁（同所屬類別），值顯示於格 */}
        <tr>
          <th className={TH} colSpan={2}>
            <div className="flex items-center justify-between gap-1">
              <span>基準級別</span>
              <OfficialMenu
                trigger={<button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground" title="選級別"><ChevronDown className="h-3.5 w-3.5" /></button>}
                options={[1, 2, 3, 4, 5, 6].map((n) => ({ value: String(n), label: `級別 ${n}`, hint: opts.some((o) => o.ocs_level === n) ? "官方" : undefined }))}
                onPick={(v) => onChange(setOcsLevel(doc, v))}
              />
            </div>
          </th>
          <td className={TD} colSpan={3}>
            <span className="px-1.5 text-sm">{p.ocs_level != null ? `級別 ${p.ocs_level}` : "—"}</span>
          </td>
        </tr>
      </tbody>
    </table>
  );
}
