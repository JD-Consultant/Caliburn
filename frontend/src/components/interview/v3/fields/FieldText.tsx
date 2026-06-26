"use client";
import { useEffect, useRef, useState } from "react";
import { Layers } from "lucide-react";

export function FieldText({
  value, placeholder, multiline = false, official, onCommit,
}: { value: string; placeholder?: string; multiline?: boolean; official?: string; onCommit: (v: string) => void }) {
  const [draft, setDraft] = useState(value);
  const focused = useRef(false);
  // value 變且未聚焦 → 同步（反映自動帶入/綁定/外部寫入）
  useEffect(() => { if (!focused.current) setDraft(value); }, [value]);
  const commit = () => { if (draft !== value) onCommit(draft); };
  const cls = "w-full rounded-md border px-2.5 py-1.5 text-sm focus:outline-none";
  return (
    <div className="space-y-1">
      {multiline ? (
        <textarea className={cls} rows={3} placeholder={placeholder} value={draft}
          onFocus={() => (focused.current = true)} onBlur={() => { focused.current = false; commit(); }}
          onChange={(e) => setDraft(e.target.value)} />
      ) : (
        <input className={cls} placeholder={placeholder} value={draft}
          onFocus={() => (focused.current = true)}
          onBlur={() => { focused.current = false; commit(); }}
          onKeyDown={(e) => { if (e.key === "Enter" && !multiline) e.currentTarget.blur(); }}
          onChange={(e) => setDraft(e.target.value)} />
      )}
      {official != null && official !== "" && official !== draft ? (
        <button type="button" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          onClick={() => { setDraft(official); onCommit(official); }}>
          <Layers className="h-3 w-3" /> 帶官方
        </button>
      ) : null}
    </div>
  );
}
