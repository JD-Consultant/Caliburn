"use client";

// D27「說明與補充事項」可編輯區塊：學經歷/能力建議(prerequisites) + 其他補充
// 說明(supplements)，皆為字串清單，可新增/改/刪。變更經 onChange→PATCH。
import { addNote, deleteNote, updateNote, type NoteField } from "@/lib/ocsDoc";
import type { OcsDocument } from "@/types";
import { Plus, Trash2 } from "lucide-react";

function NoteList({
  doc,
  onChange,
  field,
  title,
}: {
  doc: OcsDocument;
  onChange: (d: OcsDocument) => void;
  field: NoteField;
  title: string;
}) {
  const rows = doc.notes?.[field] ?? [];
  return (
    <div>
      <p className="mb-1.5 text-sm font-medium">{title}</p>
      <div className="space-y-1.5">
        {rows.map((r, i) => (
          <div key={`${i}-${r}`} className="flex items-center gap-1.5">
            <span className="text-muted-foreground">•</span>
            <input
              defaultValue={r}
              placeholder="輸入一條…"
              onBlur={(e) => {
                if (e.target.value !== r) onChange(updateNote(doc, field, i, e.target.value));
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") e.currentTarget.blur();
              }}
              className="w-full rounded-md border px-2.5 py-1.5 text-sm"
            />
            <button type="button" className="shrink-0 p-1.5 text-muted-foreground hover:text-destructive" onClick={() => onChange(deleteNote(doc, field, i))}>
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        <button type="button" className="inline-flex items-center gap-1 rounded-md border border-dashed px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground" onClick={() => onChange(addNote(doc, field))}>
          <Plus className="h-3.5 w-3.5" />
          新增一條
        </button>
      </div>
    </div>
  );
}

export function DocNotes({
  document: doc,
  onChange,
}: {
  document: OcsDocument;
  onChange: (d: OcsDocument) => void;
}) {
  return (
    <div className="space-y-4 rounded-lg border bg-background p-4">
      <p className="text-sm font-semibold">說明與補充事項</p>
      <NoteList doc={doc} onChange={onChange} field="prerequisites" title="建議擔任此職類／職業之學歷／經歷／或能力條件" />
      <NoteList doc={doc} onChange={onChange} field="supplements" title="其他補充說明" />
    </div>
  );
}
