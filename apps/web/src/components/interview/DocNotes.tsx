"use client";
import { useMemo } from "react";
import type { NoteItem, OcsDocument } from "@/types";
import { useKnowledge } from "@/hooks/useKnowledge";
import { isOfficialBasis, noteRowsFromStrings, primaryDefaults, valuePoolOptions } from "@/lib/pack";
import { setNoteItems, type NoteField } from "@/lib/ocsDoc";
import { FieldCombobox } from "./fields/FieldCombobox";

// NOTE 兩欄=實體列(spec 2026-07-04 §3):影子列 notes._<field> 為真相({code,text,_id,_src,_ref}),
// 官方判定走 _ref 有碼比對(來源 n 碼,api build_pack 蓋);候選=知識包池、defaults=主基準來源。
function NoteCombo({ doc, profileId, field, title, onChange }: {
  doc: OcsDocument; profileId: string; field: NoteField; title: string; onChange: (d: OcsDocument) => void;
}) {
  const { data: pack } = useKnowledge(profileId, !!doc.ocs_profile.ocs_code);
  const options = pack ? valuePoolOptions(pack.pools[field]) : [];
  const primary = doc.ocs_profile.ocs_code;
  const defaults = pack && isOfficialBasis(pack, primary) ? primaryDefaults(options, primary) : [];
  // 影子列=真相;舊 draft(只有 string[])→ 文字對池重建(顯示用,下次 commit 隨 PATCH 落庫)。
  const rows = useMemo<NoteItem[]>(() => {
    const shadow = doc.notes?.[`_${field}`];
    if (shadow) return shadow;
    const texts = doc.notes?.[field] ?? [];
    return pack ? noteRowsFromStrings(texts, pack.pools[field])
                : texts.map((t, i) => ({ code: `n${i + 1}`, text: t }));
  }, [doc.notes, field, pack]);
  const value = rows.map((r) => ({ code: r.code, name: r.text, _id: r._id, _src: r._src, _ref: r._ref }));
  return (
    <div>
      <FieldCombobox label="選/輸入" title={title} layout="list" customMode="footer" editMultiline
        autoCode="n" autoApplyOnFirstOpen
        value={value} options={options} defaults={defaults}
        onCommit={(items) => onChange(setNoteItems(doc, field,
          items.map((i) => ({ code: i.code, text: i.name, _id: i._id, _src: i._src, _ref: i._ref }))))} />
    </div>
  );
}

export function DocNotes({ document: doc, profileId, onChange }: {
  document: OcsDocument; profileId: string; onChange: (d: OcsDocument) => void;
}) {
  return (
    <div className="space-y-4 rounded-lg border bg-background p-4">
      <p className="text-sm font-semibold">說明與補充事項</p>
      <NoteCombo doc={doc} profileId={profileId} field="prerequisites" title="建議擔任此職類／職業之學歷／經歷／或能力條件" onChange={onChange} />
      <NoteCombo doc={doc} profileId={profileId} field="supplements" title="其他補充說明" onChange={onChange} />
    </div>
  );
}
