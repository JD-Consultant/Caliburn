"use client";
import type { OcsDocument } from "@/types";
import { useHeaderMeta } from "@/hooks/useDocument";
import { noteOptions } from "@/lib/headerMeta";
import { setNotes, type NoteField } from "@/lib/ocsDoc";
import { FieldCombobox } from "./fields/FieldCombobox";

function NoteCombo({ doc, profileId, field, title, onChange }: {
  doc: OcsDocument; profileId: string; field: NoteField; title: string; onChange: (d: OcsDocument) => void;
}) {
  const { data: meta } = useHeaderMeta(profileId, !!doc.ocs_profile.ocs_code);
  const options = (meta ? noteOptions(meta, field) : []).map((t) => ({ code: "", name: t }));
  const value = (doc.notes?.[field] ?? []).map((t) => ({ code: "", name: t }));
  return (
    <div>
      <FieldCombobox label="選/輸入" title={title} layout="list" customMode="footer" footerWithCode={false} editMultiline
        value={value} options={options}
        onCommit={(items) => onChange(setNotes(doc, field, items.map((i) => i.name).filter(Boolean)))} />
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
