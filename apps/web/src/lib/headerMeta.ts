import type { HeaderMeta, HeaderMetaPrimaryOption, OptionItem, SourceRef } from "@/types";

function srcRefs(meta: HeaderMeta, sources: string[] | undefined, code: string): SourceRef[] {
  const nameByCode = new Map((meta.primary_options ?? []).map((o) => [o.ocs_code, o.occupation_name]));
  return (sources ?? []).map((oc) => ({ ocs_code: oc, occupation_name: nameByCode.get(oc) ?? "", code }));
}

export function categoryOptions(
  meta: HeaderMeta,
  kind: "job_categories" | "occupations" | "industries",
): OptionItem[] {
  return (meta[kind] ?? []).map((c) => ({
    code: c.code, name: c.name, sources: c.sources, srcs: srcRefs(meta, c.sources, c.code),
  }));
}

export function attitudeOptions(meta: HeaderMeta): OptionItem[] {
  return (meta.attitudes ?? []).map((a) => ({
    code: a.code, name: a.name, sources: a.sources, srcs: srcRefs(meta, a.sources, a.code),
  }));
}

export function noteOptions(meta: HeaderMeta, field: "prerequisites" | "supplements"): string[] {
  return (meta[field] ?? []).map((t) => t.text);
}

export function primaryOptions(meta: HeaderMeta): HeaderMetaPrimaryOption[] {
  return meta.primary_options ?? [];
}
