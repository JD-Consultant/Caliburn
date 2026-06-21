"use client";

// D27 官方職能基準「表頭」版型（可編輯）。代碼+職業由〔選職類〕自動帶，其餘
// （職類別/職業別/行業別/工作描述/基準級別）indexer 不提供 → 留白讓使用者填。
// 變更經 onChange(newDoc) 交回上層 PATCH（自動儲存）。
import {
  addCategory,
  deleteCategory,
  setOcsLevel,
  setOcsName,
  setProfileField,
  updateCategory,
  type CatKind,
} from "@/lib/ocsDoc";
import type { OcsDocument } from "@/types";
import { Plus, X } from "lucide-react";

function Cell({
  value,
  onCommit,
  placeholder,
  className = "",
  type = "text",
}: {
  value: string;
  onCommit: (v: string) => void;
  placeholder?: string;
  className?: string;
  type?: string;
}) {
  return (
    <input
      key={value}
      type={type}
      defaultValue={value}
      placeholder={placeholder}
      onBlur={(e) => {
        if (e.target.value !== value) onCommit(e.target.value);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
      }}
      className={
        "w-full bg-transparent px-2 py-1 text-sm focus:bg-background focus:outline-none " + className
      }
    />
  );
}

function CategoryCell({
  doc,
  onChange,
  kind,
}: {
  doc: OcsDocument;
  onChange: (d: OcsDocument) => void;
  kind: CatKind;
}) {
  const rows = doc.ocs_profile.category?.[kind] ?? [];
  return (
    <div className="divide-y">
      {rows.map((r, i) => (
        <div key={i} className="flex items-center gap-1 px-1">
          <Cell value={r.name} placeholder="名稱" className="flex-1" onCommit={(v) => onChange(updateCategory(doc, kind, i, "name", v))} />
          <span className="shrink-0 text-xs text-muted-foreground">代碼</span>
          <Cell value={r.code} placeholder="—" className="w-20" onCommit={(v) => onChange(updateCategory(doc, kind, i, "code", v))} />
          <button type="button" className="shrink-0 text-muted-foreground hover:text-destructive" onClick={() => onChange(deleteCategory(doc, kind, i))}>
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
      <button
        type="button"
        className="inline-flex items-center gap-1 px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
        onClick={() => onChange(addCategory(doc, kind))}
      >
        <Plus className="h-3 w-3" />
        加一列
      </button>
    </div>
  );
}

const TH = "border bg-muted/50 px-3 py-2 text-left align-top font-medium whitespace-nowrap";
const TD = "border align-top";

export function DocHeader({
  document: doc,
  onChange,
}: {
  document: OcsDocument;
  onChange: (d: OcsDocument) => void;
}) {
  const p = doc.ocs_profile;
  return (
    <table className="w-full border-collapse overflow-hidden rounded-lg border text-sm">
      <tbody>
        <tr>
          <th className={TH}>職能基準代碼</th>
          <td className={TD} colSpan={3}>
            <Cell value={p.ocs_code ?? ""} placeholder="（選職類後自動帶）" onCommit={(v) => onChange(setProfileField(doc, "ocs_code", v))} />
          </td>
        </tr>
        <tr>
          <th className={TH} rowSpan={2}>職能基準名稱</th>
          <th className={TH}>職類</th>
          <td className={TD} colSpan={2}>
            <Cell value={p.ocs_name?.job_category_name ?? ""} placeholder="（擇一填寫）" onCommit={(v) => onChange(setOcsName(doc, "job_category_name", v))} />
          </td>
        </tr>
        <tr>
          <th className={TH}>職業</th>
          <td className={TD} colSpan={2}>
            <Cell value={p.ocs_name?.occupation_name ?? ""} placeholder="職業名稱" onCommit={(v) => onChange(setOcsName(doc, "occupation_name", v))} />
          </td>
        </tr>
        <tr>
          <th className={TH} rowSpan={3}>所屬類別</th>
          <th className={TH}>職類別</th>
          <td className={TD} colSpan={2}><CategoryCell doc={doc} onChange={onChange} kind="job_categories" /></td>
        </tr>
        <tr>
          <th className={TH}>職業別</th>
          <td className={TD} colSpan={2}><CategoryCell doc={doc} onChange={onChange} kind="occupations" /></td>
        </tr>
        <tr>
          <th className={TH}>行業別</th>
          <td className={TD} colSpan={2}><CategoryCell doc={doc} onChange={onChange} kind="industries" /></td>
        </tr>
        <tr>
          <th className={TH}>工作描述</th>
          <td className={TD} colSpan={3}>
            <Cell value={p.job_description ?? ""} placeholder="（可填：本職務的工作描述）" onCommit={(v) => onChange(setProfileField(doc, "job_description", v))} />
          </td>
        </tr>
        <tr>
          <th className={TH}>基準級別</th>
          <td className={TD} colSpan={3}>
            <Cell value={p.ocs_level != null ? String(p.ocs_level) : ""} placeholder="—" type="number" onCommit={(v) => onChange(setOcsLevel(doc, v))} />
          </td>
        </tr>
      </tbody>
    </table>
  );
}
