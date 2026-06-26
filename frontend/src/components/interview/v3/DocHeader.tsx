"use client";
import type { OcsDocument } from "@/types";
import { useHeaderMeta } from "@/hooks/useDocument";
import { categoryOptions, primaryOptions } from "@/lib/headerMeta";
import { setCategory, setOcsLevel, setOcsName, setPrimaryBasis, setProfileField } from "@/lib/ocsDoc";
import { FieldCombobox } from "./fields/FieldCombobox";
import { FieldText } from "./fields/FieldText";
import { FieldBoundSelect } from "./fields/FieldBoundSelect";

const TH = "border bg-muted/50 px-3 py-2 text-left align-top font-medium whitespace-nowrap";
const TD = "border p-2 align-top";

export function DocHeader({ document: doc, profileId, onChange }: {
  document: OcsDocument; profileId: string; onChange: (d: OcsDocument) => void;
}) {
  const p = doc.ocs_profile;
  const { data: meta } = useHeaderMeta(profileId, !!p.ocs_code);
  const opts = meta ? primaryOptions(meta) : [];
  const cur = opts.find((o) => o.ocs_code === p.ocs_code);
  const cats = (kind: "job_categories" | "occupations" | "industries") => meta ? categoryOptions(meta, kind) : [];

  return (
    <table className="w-full table-fixed border-collapse overflow-hidden rounded-lg border text-sm">
      <colgroup><col className="w-32" /><col /></colgroup>
      <tbody>
        <tr><th className={TH}>職能基準（代碼/名稱）</th><td className={TD}>
          <FieldBoundSelect
            value={{ ocs_code: p.ocs_code, name: p.ocs_name.occupation_name }}
            options={opts.map((o) => ({ ocs_code: o.ocs_code, name: o.occupation_name }))}
            onCommit={(o) => onChange(setPrimaryBasis(doc, { ocs_code: o.ocs_code, occupation_name: o.name, job_category_name: opts.find((x) => x.ocs_code === o.ocs_code)?.job_category_name || "" }))}
          />
        </td></tr>
        <tr><th className={TH}>職類名稱</th><td className={TD}>
          <FieldText value={p.ocs_name.job_category_name ?? ""} official={cur?.job_category_name ?? ""}
            onCommit={(v) => onChange(setOcsName(doc, "job_category_name", v))} />
        </td></tr>
        <tr><th className={TH}>所屬職類別</th><td className={TD}>
          <FieldCombobox label="選職類別" value={p.category.job_categories} options={cats("job_categories")}
            onCommit={(items) => onChange(setCategory(doc, "job_categories", items))} />
        </td></tr>
        <tr><th className={TH}>所屬職業別</th><td className={TD}>
          <FieldCombobox label="選職業別" value={p.category.occupations} options={cats("occupations")}
            onCommit={(items) => onChange(setCategory(doc, "occupations", items))} />
        </td></tr>
        <tr><th className={TH}>所屬行業別</th><td className={TD}>
          <FieldCombobox label="選行業別" value={p.category.industries} options={cats("industries")}
            onCommit={(items) => onChange(setCategory(doc, "industries", items))} />
        </td></tr>
        <tr><th className={TH}>工作描述</th><td className={TD}>
          <FieldText multiline value={p.job_description ?? ""} official={cur?.job_description ?? ""}
            onCommit={(v) => onChange(setProfileField(doc, "job_description", v))} />
        </td></tr>
        <tr><th className={TH}>基準級別</th><td className={TD}>
          <FieldText value={p.ocs_level != null ? String(p.ocs_level) : ""} official={cur?.ocs_level != null ? String(cur.ocs_level) : ""}
            onCommit={(v) => onChange(setOcsLevel(doc, v))} />
        </td></tr>
      </tbody>
    </table>
  );
}
