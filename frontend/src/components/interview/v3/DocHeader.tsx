"use client";

// D27 官方職能基準「表頭」版型（可編輯，5 欄對齊）。代碼+職業由〔選職類〕自動帶，
// 其餘（職類別/職業別/行業別/工作描述/基準級別）indexer 不提供 → 留白讓使用者填。
// 所屬類別照官方：每列 = 子類別 | 名稱 | 子類別代碼 | 代碼值。變更經 onChange→PATCH。
import {
  addCategory,
  deleteCategory,
  setOcsLevel,
  setOcsName,
  setProfileField,
  upsertCategory,
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
      className={"w-full bg-transparent px-2 py-1 text-sm focus:bg-background focus:outline-none " + className}
    />
  );
}

const TH = "border bg-muted/50 px-3 py-2 text-left align-middle font-medium whitespace-nowrap";
const TD = "border align-middle";

const KINDS = [
  { key: "job_categories", label: "職類別", codeLabel: "職類別代碼" },
  { key: "occupations", label: "職業別", codeLabel: "職業別代碼" },
  { key: "industries", label: "行業別", codeLabel: "行業別代碼" },
] as const;

export function DocHeader({
  document: doc,
  onChange,
}: {
  document: OcsDocument;
  onChange: (d: OcsDocument) => void;
}) {
  const p = doc.ocs_profile;

  // 攤平成多列：每個子類別至少一列（空則顯示一列可填的虛擬列）。子類別/代碼標籤
  // 只在該類第一列出現並 rowSpan 蓋住整類（加列時不重複標籤）。
  const catRows = KINDS.flatMap((k) => {
    const entries = p.category?.[k.key] ?? [];
    const rows = entries.length ? entries : [{ name: "", code: "" }];
    return rows.map((e, i) => ({
      ...k,
      idx: i,
      name: e.name,
      code: e.code,
      real: i < entries.length,
      firstOfKind: i === 0,
      kindCount: rows.length,
    }));
  });

  return (
    <table className="w-full table-fixed border-collapse overflow-hidden rounded-lg border text-sm">
      <colgroup>
        <col className="w-28" />
        <col className="w-20" />
        <col />
        <col className="w-28" />
        <col className="w-28" />
      </colgroup>
      <tbody>
        <tr>
          <th className={TH} colSpan={2}>職能基準代碼</th>
          <td className={TD} colSpan={3}>
            <Cell value={p.ocs_code ?? ""} placeholder="（選職類後自動帶）" onCommit={(v) => onChange(setProfileField(doc, "ocs_code", v))} />
          </td>
        </tr>

        <tr>
          <th className={TH} rowSpan={2}>
            職能基準名稱
            <div className="text-xs font-normal text-muted-foreground">（擇一填寫）</div>
          </th>
          <th className={TH}>職類</th>
          <td className={TD} colSpan={3}>
            <Cell value={p.ocs_name?.job_category_name ?? ""} placeholder="職類名稱" onCommit={(v) => onChange(setOcsName(doc, "job_category_name", v))} />
          </td>
        </tr>
        <tr>
          <th className={TH}>職業</th>
          <td className={TD} colSpan={3}>
            <Cell value={p.ocs_name?.occupation_name ?? ""} placeholder="職業名稱" onCommit={(v) => onChange(setOcsName(doc, "occupation_name", v))} />
          </td>
        </tr>

        {catRows.map((r, gi) => (
          <tr key={`${r.key}-${r.idx}`}>
            {gi === 0 ? <th className={TH} rowSpan={catRows.length}>所屬類別</th> : null}
            {r.firstOfKind ? (
              <th className={TH} rowSpan={r.kindCount}>
                <div className="flex items-center justify-between gap-1">
                  <span>{r.label}</span>
                  <button type="button" className="text-muted-foreground hover:text-foreground" title="加一列" onClick={() => onChange(addCategory(doc, r.key))}>
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                </div>
              </th>
            ) : null}
            <td className={TD}>
              <Cell value={r.name} placeholder="名稱" onCommit={(v) => onChange(upsertCategory(doc, r.key, r.idx, "name", v))} />
            </td>
            {r.firstOfKind ? (
              <th className={TH} rowSpan={r.kindCount}>{r.codeLabel}</th>
            ) : null}
            <td className={TD}>
              <div className="flex items-center">
                <Cell value={r.code} placeholder="代碼" onCommit={(v) => onChange(upsertCategory(doc, r.key, r.idx, "code", v))} />
                {r.real ? (
                  <button type="button" className="shrink-0 pr-1 text-muted-foreground hover:text-destructive" onClick={() => onChange(deleteCategory(doc, r.key, r.idx))}>
                    <X className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </div>
            </td>
          </tr>
        ))}

        <tr>
          <th className={TH} colSpan={2}>工作描述</th>
          <td className={TD} colSpan={3}>
            <Cell value={p.job_description ?? ""} placeholder="（可填：本職務的工作描述）" onCommit={(v) => onChange(setProfileField(doc, "job_description", v))} />
          </td>
        </tr>
        <tr>
          <th className={TH} colSpan={2}>基準級別</th>
          <td className={TD} colSpan={3}>
            <Cell value={p.ocs_level != null ? String(p.ocs_level) : ""} placeholder="—" type="number" onCommit={(v) => onChange(setOcsLevel(doc, v))} />
          </td>
        </tr>
      </tbody>
    </table>
  );
}
