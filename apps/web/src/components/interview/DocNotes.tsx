"use client";
import type { OcsDocument } from "@/types";
import { useKnowledge } from "@/hooks/useKnowledge";
import { valuePoolOptions } from "@/lib/pack";
import { setNoteItems, type NoteField } from "@/lib/ocsDoc";
import { FieldCombobox } from "./fields/FieldCombobox";

// NOTE 候選＝知識包 prerequisites/supplements 池（key=text，序號顯示+引用行；ADR 0021）。
// 勾選互動改素材庫模式（點一下即加純文字）屬 Plan UX（spec §1.2/A3），此處只換資料源。
function NoteCombo({ doc, profileId, field, title, onChange }: {
  doc: OcsDocument; profileId: string; field: NoteField; title: string; onChange: (d: OcsDocument) => void;
}) {
  const { data: pack } = useKnowledge(profileId, !!doc.ocs_profile.ocs_code);
  const options = pack ? valuePoolOptions(pack.pools[field]) : [];
  const value = (doc.notes?.[field] ?? []).map((t) => ({ code: "", name: t }));
  return (
    <div>
      <FieldCombobox label="選/輸入" title={title} layout="list" customMode="footer" editMultiline
        value={value} options={options}
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
