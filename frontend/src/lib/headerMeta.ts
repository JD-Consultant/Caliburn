import type { HeaderMeta, HeaderMetaPrimaryOption, OptionItem } from "@/types";

export function categoryOptions(
  meta: HeaderMeta,
  kind: "job_categories" | "occupations" | "industries",
): OptionItem[] {
  return (meta[kind] ?? []).map((c) => ({ code: c.code, name: c.name, sources: c.sources }));
}

export function attitudeOptions(meta: HeaderMeta): OptionItem[] {
  return (meta.attitudes ?? []).map((a) => ({ code: a.code, name: a.name, sources: a.sources }));
}

export function noteOptions(meta: HeaderMeta, field: "prerequisites" | "supplements"): string[] {
  return (meta[field] ?? []).map((t) => t.text);
}

export function primaryOptions(meta: HeaderMeta): HeaderMetaPrimaryOption[] {
  return meta.primary_options ?? [];
}
