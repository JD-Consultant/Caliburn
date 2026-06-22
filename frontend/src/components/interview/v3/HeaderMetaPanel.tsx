"use client";

// D29 V2 表頭分類面板：讀 /header-meta（多 OCS 官方 metadata 聯集候選），讓使用者
// 勾選所屬職類別/職業別/行業別（多值）、態度、應備資格/補充說明，並切換「主基準」
// （職能基準代碼↔名稱綁定、預設第一順位）。預設全勾（官方事實）；套用走現有 PATCH。
// 候選 = indexer 聯集 ∪ 文件現有列（保留使用者手動加的列，不會被洗掉）。
import { useMemo, useState } from "react";
import { Layers, Loader2, X } from "lucide-react";
import type {
  CodeName,
  HeaderMeta,
  HeaderMetaCandidate,
  OcsDocument,
} from "@/types";
import { useHeaderMeta } from "@/hooks/useDocument";
import {
  setAttitudes,
  setCategory,
  setNotes,
  setOcsLevel,
  setPrimaryBasis,
  setProfileField,
  type CatKind,
} from "@/lib/ocsDoc";
import { Button } from "@/components/ui/button";

const keyOf = (code: string, name: string) => (code || "").trim() || "name:" + (name || "").trim();

type Row = { code: string; name: string; sources: string[] };

// 候選 ∪ 文件現有列（依 code|name 去重，保序：候選先、現有列補在後）。
function mergeRows(candidates: HeaderMetaCandidate[], existing: CodeName[]): Row[] {
  const out: Row[] = candidates.map((c) => ({ code: c.code, name: c.name, sources: c.sources }));
  const seen = new Set(out.map((r) => keyOf(r.code, r.name)));
  for (const e of existing) {
    const k = keyOf(e.code, e.name);
    if (!seen.has(k)) {
      seen.add(k);
      out.push({ code: e.code, name: e.name, sources: [] });
    }
  }
  return out;
}

function Checklist({
  rows,
  ticked,
  onToggle,
}: {
  rows: Row[];
  ticked: Set<string>;
  onToggle: (k: string) => void;
}) {
  if (!rows.length) return <p className="px-1 py-2 text-xs text-muted-foreground">（無候選）</p>;
  return (
    <div className="space-y-1">
      {rows.map((r) => {
        const k = keyOf(r.code, r.name);
        return (
          <label key={k} className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 text-sm hover:bg-muted/50">
            <input type="checkbox" className="mt-1" checked={ticked.has(k)} onChange={() => onToggle(k)} />
            {r.code ? <span className="mt-0.5 shrink-0 font-mono text-xs text-muted-foreground">{r.code}</span> : null}
            <span className="flex-1">{r.name || <span className="text-muted-foreground">（未命名）</span>}</span>
            {r.sources.length > 1 ? (
              <span className="shrink-0 rounded bg-sky-100 px-1 py-0.5 text-[10px] text-sky-700" title={"來自：" + r.sources.join("、")}>
                共 {r.sources.length}
              </span>
            ) : null}
          </label>
        );
      })}
    </div>
  );
}

function TextChecklist({
  items,
  ticked,
  onToggle,
}: {
  items: string[];
  ticked: Set<string>;
  onToggle: (t: string) => void;
}) {
  if (!items.length) return <p className="px-1 py-2 text-xs text-muted-foreground">（無候選）</p>;
  return (
    <div className="space-y-1">
      {items.map((t) => (
        <label key={t} className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 text-sm hover:bg-muted/50">
          <input type="checkbox" className="mt-1" checked={ticked.has(t)} onChange={() => onToggle(t)} />
          <span className="flex-1">{t}</span>
        </label>
      ))}
    </div>
  );
}

export function HeaderMetaPanel({
  profileId,
  document: doc,
  saving,
  onApply,
  onClose,
}: {
  profileId: string;
  document: OcsDocument;
  saving: boolean;
  onApply: (doc: OcsDocument) => void;
  onClose: () => void;
}) {
  const { data: meta, isLoading, isError } = useHeaderMeta(profileId, true);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div className="h-full w-full max-w-lg overflow-y-auto bg-background p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="flex items-center gap-1.5 text-sm font-semibold">
            <Layers className="h-4 w-4 text-sky-500" />
            表頭分類（從職類帶入）
          </h3>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            載入官方分類中…
          </div>
        ) : isError || !meta ? (
          <p className="py-10 text-sm text-destructive">載入失敗（indexer 可能未啟動）。</p>
        ) : (
          <Body meta={meta} doc={doc} saving={saving} onApply={onApply} />
        )}
      </div>
    </div>
  );
}

function Body({
  meta,
  doc,
  saving,
  onApply,
}: {
  meta: HeaderMeta;
  doc: OcsDocument;
  saving: boolean;
  onApply: (doc: OcsDocument) => void;
}) {
  const cat = doc.ocs_profile.category;
  const rows = useMemo(
    () => ({
      job_categories: mergeRows(meta.job_categories, cat?.job_categories ?? []),
      occupations: mergeRows(meta.occupations, cat?.occupations ?? []),
      industries: mergeRows(meta.industries, cat?.industries ?? []),
      attitudes: mergeRows(meta.attitudes, doc.ocs_attitude?.attitudes ?? []),
    }),
    [meta, cat, doc.ocs_attitude],
  );
  const prereqItems = useMemo(
    () => Array.from(new Set([...meta.prerequisites.map((p) => p.text), ...(doc.notes?.prerequisites ?? [])])),
    [meta.prerequisites, doc.notes],
  );
  const supplItems = useMemo(
    () => Array.from(new Set([...meta.supplements.map((s) => s.text), ...(doc.notes?.supplements ?? [])])),
    [meta.supplements, doc.notes],
  );

  // 預設全勾（官方事實）。
  const allKeys = (rs: Row[]) => new Set(rs.map((r) => keyOf(r.code, r.name)));
  const [tCats, setTCats] = useState(() => allKeys(rows.job_categories));
  const [tOccs, setTOccs] = useState(() => allKeys(rows.occupations));
  const [tInds, setTInds] = useState(() => allKeys(rows.industries));
  const [tAtts, setTAtts] = useState(() => allKeys(rows.attitudes));
  const [tPre, setTPre] = useState(() => new Set(prereqItems));
  const [tSup, setTSup] = useState(() => new Set(supplItems));

  const defaultPrimary =
    meta.primary_options.find((o) => o.ocs_code === doc.ocs_profile.ocs_code)?.ocs_code ||
    meta.primary.ocs_code;
  const [primaryCode, setPrimaryCode] = useState(defaultPrimary);
  const [fillDesc, setFillDesc] = useState(!doc.ocs_profile.job_description?.trim());
  const [fillLevel, setFillLevel] = useState(doc.ocs_profile.ocs_level == null);

  const toggle = (set: React.Dispatch<React.SetStateAction<Set<string>>>) => (k: string) =>
    set((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });

  const picked = (rs: Row[], t: Set<string>): CodeName[] =>
    rs.filter((r) => t.has(keyOf(r.code, r.name))).map((r) => ({ code: r.code, name: r.name }));

  const apply = () => {
    let next = doc;
    const opt = meta.primary_options.find((o) => o.ocs_code === primaryCode);
    if (opt) {
      next = setPrimaryBasis(next, {
        ocs_code: opt.ocs_code,
        occupation_name: opt.occupation_name,
        job_category_name: opt.job_category_name,
      });
      if (fillDesc && opt.job_description) next = setProfileField(next, "job_description", opt.job_description);
      if (fillLevel && opt.ocs_level != null) next = setOcsLevel(next, String(opt.ocs_level));
    }
    next = setCategory(next, "job_categories" as CatKind, picked(rows.job_categories, tCats));
    next = setCategory(next, "occupations" as CatKind, picked(rows.occupations, tOccs));
    next = setCategory(next, "industries" as CatKind, picked(rows.industries, tInds));
    next = setAttitudes(next, picked(rows.attitudes, tAtts));
    next = setNotes(next, "prerequisites", prereqItems.filter((t) => tPre.has(t)));
    next = setNotes(next, "supplements", supplItems.filter((t) => tSup.has(t)));
    onApply(next);
  };

  return (
    <div className="space-y-5">
      {/* 主基準（單選） */}
      <section>
        <h4 className="mb-1 text-xs font-semibold text-muted-foreground">主基準（職能基準代碼／名稱，擇一）</h4>
        <div className="space-y-1">
          {meta.primary_options.map((o) => (
            <label key={o.ocs_code} className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-muted/50">
              <input type="radio" name="primary" checked={primaryCode === o.ocs_code} onChange={() => setPrimaryCode(o.ocs_code)} />
              <span className="font-mono text-xs text-muted-foreground">{o.ocs_code}</span>
              <span className="flex-1">{o.occupation_name}</span>
            </label>
          ))}
        </div>
        <div className="mt-2 space-y-1 pl-1">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input type="checkbox" checked={fillDesc} onChange={(e) => setFillDesc(e.target.checked)} />
            帶入官方工作描述
          </label>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input type="checkbox" checked={fillLevel} onChange={(e) => setFillLevel(e.target.checked)} />
            帶入官方基準級別
          </label>
        </div>
      </section>

      <Section title="所屬職類別">
        <Checklist rows={rows.job_categories} ticked={tCats} onToggle={toggle(setTCats)} />
      </Section>
      <Section title="所屬職業別">
        <Checklist rows={rows.occupations} ticked={tOccs} onToggle={toggle(setTOccs)} />
      </Section>
      <Section title="所屬行業別">
        <Checklist rows={rows.industries} ticked={tInds} onToggle={toggle(setTInds)} />
      </Section>
      <Section title="職能內涵（態度 A）">
        <Checklist rows={rows.attitudes} ticked={tAtts} onToggle={toggle(setTAtts)} />
      </Section>
      <Section title="應具備之資格條件">
        <TextChecklist items={prereqItems} ticked={tPre} onToggle={toggle(setTPre)} />
      </Section>
      <Section title="補充說明事項">
        <TextChecklist items={supplItems} ticked={tSup} onToggle={toggle(setTSup)} />
      </Section>

      <div className="sticky bottom-0 -mx-5 flex justify-end gap-2 border-t bg-background px-5 py-3">
        <Button size="sm" onClick={apply} disabled={saving}>
          {saving ? "套用中…" : "套用到表頭"}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        勾選＝寫入表頭；取消勾選的官方項目不會出現在文件。手動加的列已併入清單並預設保留。
      </p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h4 className="mb-1 text-xs font-semibold text-muted-foreground">{title}</h4>
      {children}
    </section>
  );
}
