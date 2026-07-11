"use client";
import { useMemo, useState } from "react";
import { ChevronDown, Plus, X } from "lucide-react";
import type { NoteItem, OcsDocument, OptionItem } from "@/types";
import { useKnowledge } from "@/hooks/useKnowledge";
import { noteRowsFromStrings, valuePoolOptions } from "@/lib/pack";
import { setNoteItems, type NoteField } from "@/lib/ocsDoc";
import { FieldText } from "./fields/FieldText";
import { SourceLine } from "./fields/SourceLine";
import { Modal } from "./OccupationPicker";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";

const newId = () => (globalThis.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}`);

// 素材庫窗(ADR 0029):列官方素材,點一列＝插入到文件(**無勾選狀態**、可重複插入);
// 純工具、無首開自動、無 footer 自訂。加自訂列走右側「＋」。
function MaterialMenu({ title, options, onInsert }: {
  title: string; options: OptionItem[]; onInsert: (o: OptionItem) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground" title="從素材庫插入" onClick={() => setOpen(true)}>
        <ChevronDown className="h-4 w-4" />
      </button>
      {open ? (
        <Modal title={title} onClose={() => setOpen(false)}>
          <p className="mb-2 px-1 text-xs text-muted-foreground">點一列＝插入到下方(可重複、插入後可再改字)。</p>
          <div className="rounded-lg border">
            <Command className="bg-transparent">
              <CommandInput placeholder="搜尋素材…" />
              <CommandList className="max-h-96">
                <CommandEmpty>無素材。請先〔選職能基準參考〕。</CommandEmpty>
                <CommandGroup>
                  {options.map((o, i) => (
                    <CommandItem key={i} value={`${i} ${o.name}`} onSelect={() => onInsert(o)} className="items-start">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1">
                          <span className="font-mono text-xs text-muted-foreground">{i + 1}.</span>
                          <span className="flex-1">{o.name}</span>
                        </div>
                        <SourceLine srcs={o.srcs} />
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

// NOTE 兩欄=實體列(spec §3):影子列 notes._<field> 為真相({code,text,_id,_src,_ref})。
// 素材庫窗點即插入;表格列就地自由編輯(改字保留來源=不斷根、刪列、加列)。
function NoteMaterialField({ doc, profileId, field, title, onChange }: {
  doc: OcsDocument; profileId: string; field: NoteField; title: string; onChange: (d: OcsDocument) => void;
}) {
  const { data: pack } = useKnowledge(profileId, !!doc.ocs_profile.ocs_code);
  const options = pack ? valuePoolOptions(pack.pools[field]) : [];
  // 影子列=真相;舊 draft(只有 string[])→ 文字對池重建(顯示用,下次 commit 隨 PATCH 落庫)。
  const rows = useMemo<NoteItem[]>(() => {
    const shadow = doc.notes?.[`_${field}`];
    if (shadow) return shadow;
    const texts = doc.notes?.[field] ?? [];
    return pack ? noteRowsFromStrings(texts, pack.pools[field])
                : texts.map((t, i) => ({ code: `n${i + 1}`, text: t }));
  }, [doc.notes, field, pack]);
  const commit = (next: NoteItem[]) => onChange(setNoteItems(doc, field, next));
  const insert = (o: OptionItem) => commit([...rows, { code: "", text: o.name, _id: newId(), _src: "official",
    _ref: o.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: o.code } }]);
  const addBlank = () => commit([...rows, { code: "", text: "", _id: newId(), _src: "custom" }]);
  // 改字不斷根(全局不變量):保留 _ref/身分,只換文字。
  const editText = (idx: number, text: string) => commit(rows.map((r, i) => (i === idx ? { ...r, text } : r)));
  const removeAt = (idx: number) => commit(rows.filter((_, i) => i !== idx));

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{title}</span>
        <div className="flex items-center gap-1.5">
          <MaterialMenu title={`素材庫：${title}`} options={options} onInsert={insert} />
          <button type="button" className="inline-flex items-center text-muted-foreground hover:text-foreground" title="加一列（自訂）" onClick={addBlank}>
            <Plus className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="space-y-1">
        {rows.map((r, idx) => (
          <div key={r._id ?? `${r.code}-${idx}`} className="flex items-start gap-2">
            {r.code ? <span className="mt-2 shrink-0 font-mono text-xs text-muted-foreground">{r.code}</span> : null}
            <div className="min-w-0 flex-1">
              <FieldText value={r.text} multiline placeholder="（就地編輯）" onCommit={(v) => editText(idx, v)} />
            </div>
            <button type="button" className="mt-2 shrink-0 text-muted-foreground hover:text-destructive" title="刪除此列" onClick={() => removeAt(idx)}>
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DocNotes({ document: doc, profileId, onChange }: {
  document: OcsDocument; profileId: string; onChange: (d: OcsDocument) => void;
}) {
  return (
    <div className="space-y-4 rounded-lg border bg-background p-4">
      <p className="text-sm font-semibold">說明與補充事項</p>
      <NoteMaterialField doc={doc} profileId={profileId} field="prerequisites" title="建議擔任此職類／職業之學歷／經歷／或能力條件" onChange={onChange} />
      <NoteMaterialField doc={doc} profileId={profileId} field="supplements" title="其他補充說明" onChange={onChange} />
    </div>
  );
}
