"use client";

// D27 官方職能基準「表頭」版型（5 欄對齊官方表格，可編輯/可自訂）。
// 代碼↔名稱綁定（選官方基準下拉）；所屬類別三類各列為 名稱|代碼（可手打自訂、加列刪列），
// 並提供「選官方▾」下拉把官方 {code,name} 綁定帶入；工作描述/級別預填可改+帶官方。
import { useRef, useState } from "react";
import { Check, ChevronDown, Plus, X } from "lucide-react";
import type { CodeName, OcsDocument, OptionItem } from "@/types";
import { useKnowledge } from "@/hooks/useKnowledge";
import { codedPoolOptions, primaryBasisOptions, primaryDefaults, type BasisOption } from "@/lib/pack";
import {
  clearPrimaryBasis,
  deleteCategory,
  setCategory,
  setOcsLevel,
  setPrimaryBasis,
  setProfileField,
  upsertCategory,
  type CatKind,
} from "@/lib/ocsDoc";
import { FieldText } from "./fields/FieldText";
import { OfficialMenu } from "./fields/OfficialMenu";
import { SourceLine } from "./fields/SourceLine";
import { Modal } from "./OccupationPicker";
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
const newId = () => (globalThis.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}`);

// 每類別的「選 ▾」下拉（官方候選勾選/取消）＋ 右側「+」直接加一列空白自訂。
// 自動勾選=主基準來源(spec 2026-07-04 §4):首開且該類空→自動套;選單頂列鈕可重套。
function CategoryPicker({ options, existing, onToggle, onAddBlank, onAutoApply }: {
  options: OptionItem[];
  existing: { code: string; name: string }[];
  onToggle: (o: OptionItem) => void;
  onAddBlank: () => void;
  onAutoApply?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const autoApplied = useRef(false);
  const has = (o: OptionItem) => existing.some((e) => ekey(e) === ekey(o));
  const handleOpen = (o: boolean) => {
    setOpen(o);
    if (o && !autoApplied.current) {
      autoApplied.current = true;
      if (existing.length === 0) onAutoApply?.(); // 首開且空才套
    }
  };
  return (
    <div className="flex items-center gap-0.5">
      <Popover open={open} onOpenChange={handleOpen}>
        <PopoverTrigger asChild>
          <button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground" title="選官方">
            <ChevronDown className="h-3.5 w-3.5" />
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-72">
          {onAutoApply ? (
            <div className="mb-1 flex items-center justify-end px-1">
              <button type="button" className="shrink-0 text-xs text-muted-foreground hover:text-foreground"
                title="補上主基準來源的官方項" onClick={onAutoApply}>
                自動勾選
              </button>
            </div>
          ) : null}
          <Command>
            <CommandList>
              <CommandEmpty>無候選</CommandEmpty>
              <CommandGroup>
                {options.map((o) => (
                  <CommandItem key={ekey(o)} value={`${o.code} ${o.name}`} onSelect={() => onToggle(o)} className="items-start">
                    <Check className={"mt-0.5 h-3.5 w-3.5 " + (has(o) ? "opacity-100" : "opacity-0")} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1">
                        {o.code ? <span className="font-mono text-xs text-muted-foreground">{o.code}</span> : null}
                        <span className="flex-1">{o.name}</span>
                      </div>
                      <SourceLine srcs={o.srcs} />
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      <button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground" title="加自訂（空白列）" onClick={onAddBlank}>
        <Plus className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

// 職能基準（文件身分）獨立選單窗（ADR 0029）：從**已選參考**單選一個當文件主基準
// （控制單選、不可自訂）；再點同項＝整組清空。樣式同〔選職責〕窗（序號＋來源行）。
function PrimaryBasisMenu({ options, selected, onPick }: {
  options: BasisOption[];
  selected: string;
  onPick: (code: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground"
              title="選職能基準（從已選參考單選）" onClick={() => setOpen(true)}>
        <ChevronDown className="h-3.5 w-3.5" />
      </button>
      {open ? (
        <Modal title="選職能基準（文件身分）" onClose={() => setOpen(false)}>
          <p className="mb-2 px-1 text-xs text-muted-foreground">從已選參考單選為文件主基準；再點同項＝清空。</p>
          <div className="rounded-lg border">
            <Command className="bg-transparent">
              <CommandList className="max-h-96">
                <CommandEmpty>沒有參考。請先〔選職能基準參考〕。</CommandEmpty>
                <CommandGroup>
                  {options.map((o, i) => (
                    <CommandItem key={o.ocs_code} value={`${i} ${o.ocs_code} ${o.occupation_name}`}
                      onSelect={() => { onPick(o.ocs_code); setOpen(false); }} className="items-start">
                      <Check className={"mt-0.5 h-3.5 w-3.5 " + (o.ocs_code === selected ? "opacity-100" : "opacity-0")} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1">
                          <span className="font-mono text-xs text-muted-foreground">{i + 1}.</span>
                          <span className="flex-1">{o.occupation_name || o.ocs_code}</span>
                        </div>
                        <SourceLine srcs={[{ ocs_code: o.ocs_code, occupation_name: o.occupation_name, code: "" }]} />
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </div>
        </Modal>
      ) : null}
    </>
  );
}

// 來源標記（只標非官方）：官方→不標（乾淨像官方表）；custom→「自訂」。
function Marker({ status }: { status: "official" | "custom" }) {
  if (status === "official") return null;
  return (
    <span className="shrink-0 rounded bg-amber-100 px-1 py-0.5 text-[10px] text-amber-700" title="自訂項目">自訂</span>
  );
}

export function DocHeader({ document: doc, profileId, onChange }: {
  document: OcsDocument;
  profileId: string;
  onChange: (d: OcsDocument) => void;
}) {
  const p = doc.ocs_profile;
  // 知識包（ADR 0021）：主基準選項＝occupation_details、三類選單＝coded 池（顯真實分類碼）。
  const { data: pack } = useKnowledge(profileId, !!p.ocs_code);
  const opts = pack ? primaryBasisOptions(pack) : [];
  const isOfficialBasis = !!p.ocs_code && opts.some((o) => o.ocs_code === p.ocs_code);
  const catOptions = (kind: CatKind): OptionItem[] => (pack ? codedPoolOptions(pack.pools[kind]) : []);
  const catStatus = (e: { _src?: "official" | "custom" }): "official" | "custom" =>
    e._src === "custom" ? "custom" : e._src === "official" ? "official" : "custom";

  // 主基準(表頭層)自動勾選規則(spec 2026-07-04 §4):主基準空白/自訂 → 不套。
  const levelAuto = useRef(false);
  const primaryBasis = () => (isOfficialBasis ? opts.find((o) => o.ocs_code === p.ocs_code) : undefined);
  const levelSrcOf = (b: BasisOption) => ({
    ocs_code: b.ocs_code, occupation_name: b.occupation_name, code: "", level: b.ocs_level as number });
  const applyCatDefaults = (kind: CatKind) => {
    if (!isOfficialBasis) return;
    const existing = p.category?.[kind] ?? [];
    const picks = primaryDefaults(catOptions(kind), p.ocs_code)
      .filter((o) => !existing.some((e) => ekey(e) === ekey(o)))
      .map((o) => ({ code: o.code, name: o.name, _id: newId(), _src: "official" as const,
                     _ref: o.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: o.code } }));
    if (picks.length) onChange(setCategory(doc, kind, [...existing, ...picks]));
  };

  // 下拉勾選：官方項已在→取消（移除），不在→加入（綁定 name+code + 來源 meta）。
  const toggleOfficial = (kind: CatKind, o: OptionItem) => {
    const existing = p.category?.[kind] ?? [];
    if (existing.some((e) => ekey(e) === ekey(o)))
      onChange(setCategory(doc, kind, existing.filter((e) => ekey(e) !== ekey(o))));
    else {
      const ref = o.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: o.code };
      onChange(setCategory(doc, kind, [...existing, { code: o.code, name: o.name, _id: newId(), _src: "official", _ref: ref }]));
    }
  };
  // 右側「+」：直接加一列空白自訂（名稱/代碼就地編輯）。
  const addBlankCategory = (kind: CatKind) => {
    const existing = p.category?.[kind] ?? [];
    onChange(setCategory(doc, kind, [...existing, { code: "", name: "", _id: newId(), _src: "custom" }]));
  };

  // 攤平成多列：每類至少一列（空則一列可填的虛擬列）；子類別/代碼標籤只在該類第一列 rowSpan。
  const catRows = KINDS.flatMap((k) => {
    const entries = p.category?.[k.key] ?? [];
    const rows = entries.length ? entries : [{ name: "", code: "" }];
    return rows.map((e, i) => ({
      ...k, idx: i, name: e.name, code: e.code, src: (e as CodeName)._src,
      real: i < entries.length, firstOfKind: i === 0, kindCount: rows.length,
    }));
  });

  return (
    <table className="w-full table-fixed border-collapse overflow-hidden rounded-lg border text-sm">
      <colgroup>
        <col className="w-24" /><col className="w-28" /><col /><col className="w-24" /><col className="w-32" />
      </colgroup>
      <tbody>
        {/* 職能基準代碼：▾ 在標籤旁，選官方基準 → code+名稱綁定一起帶；值顯示於格 */}
        <tr>
          <th className={TH} colSpan={2}>
            <div className="flex items-center justify-between gap-1">
              <span>職能基準代碼</span>
              <PrimaryBasisMenu
                options={opts}
                selected={p.ocs_code}
                onPick={(code) => {
                  if (code === p.ocs_code) { onChange(clearPrimaryBasis(doc)); return; } // 再點=整組清空(spec §9 決策 4)
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

        {/* 職能基準名稱（職類/職業）：一律唯讀顯示——名稱綁定於單選的職能基準，不可自由填 */}
        <tr>
          <th className={TH} rowSpan={2}>
            職能基準名稱
            <div className="text-xs font-normal text-muted-foreground">（隨基準帶入）</div>
          </th>
          <th className={TH}>職類</th>
          <td className={TD} colSpan={3}>
            <span className="block px-1.5 py-1">{p.ocs_name?.job_category_name || "—"}</span>
          </td>
        </tr>
        <tr>
          <th className={TH}>職業</th>
          <td className={TD} colSpan={3}>
            <span className="block px-1.5 py-1">{p.ocs_name?.occupation_name || "—"}</span>
          </td>
        </tr>

        {/* 所屬類別（職類別/職業別/行業別）：名稱|代碼 可手打自訂、加列刪列 + 選官方▾ */}
        {catRows.map((r, gi) => (
          <tr key={`${r.key}-${r.idx}`}>
            {gi === 0 ? <th className={TH} rowSpan={catRows.length}>所屬類別</th> : null}
            {r.firstOfKind ? (
              <th className={TH} rowSpan={r.kindCount}>
                <div className="flex items-center gap-1">
                  <span>{r.label}</span>
                  <CategoryPicker
                    options={catOptions(r.key)}
                    existing={p.category?.[r.key] ?? []}
                    onToggle={(o) => toggleOfficial(r.key, o)}
                    onAddBlank={() => addBlankCategory(r.key)}
                    onAutoApply={isOfficialBasis ? () => applyCatDefaults(r.key) : undefined}
                  />
                </div>
              </th>
            ) : null}
            <td className={TD}>
              <div className="flex items-center gap-1.5">
                <div className="min-w-0 flex-1">
                  {r.real && r.src === "official" ? (
                    <span className="block px-1.5 py-1">{r.name}</span>
                  ) : (
                    <FieldText value={r.name} placeholder="名稱（可自訂）"
                      onCommit={(v) => onChange(upsertCategory(doc, r.key, r.idx, "name", v))} />
                  )}
                </div>
                {r.real ? <Marker status={catStatus({ _src: r.src })} /> : null}
              </div>
            </td>
            {r.firstOfKind ? <th className={TH} rowSpan={r.kindCount}>{r.codeLabel}</th> : null}
            <td className={TD}>
              <div className="flex items-center gap-1">
                <div className="flex-1">
                  {r.real && r.src === "official" ? (
                    <span className="block px-1.5 py-1 font-mono">{r.code}</span>
                  ) : (
                    <FieldText value={r.code} placeholder="代碼"
                      onCommit={(v) => onChange(upsertCategory(doc, r.key, r.idx, "code", v))} />
                  )}
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
                options={[1, 2, 3, 4, 5, 6].map((n) => ({
                  value: String(n), label: `級別 ${n}`,
                  srcs: opts.filter((o) => o.ocs_level === n).map((o) => ({ ocs_code: o.ocs_code, occupation_name: o.occupation_name, code: "" })),
                }))}
                selected={p.ocs_level != null ? String(p.ocs_level) : ""}
                onAutoApply={(() => { const b = primaryBasis(); return b?.ocs_level != null
                  ? () => onChange(setOcsLevel(doc, String(b.ocs_level), levelSrcOf(b))) : undefined; })()}
                onOpenChange={(o) => { if (o && !levelAuto.current) { levelAuto.current = true;
                  const b = primaryBasis(); // 首開且空→帶主基準級別(spec §4)
                  if (p.ocs_level == null && b?.ocs_level != null)
                    onChange(setOcsLevel(doc, String(b.ocs_level), levelSrcOf(b))); } }}
                onPick={(v) => { const b = primaryBasis(); // 值==官方值即官方(spec §9 決策 6)
                  const official = b?.ocs_level != null && Number(v) === b.ocs_level;
                  onChange(setOcsLevel(doc, v, official ? levelSrcOf(b!) : undefined)); }}
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
