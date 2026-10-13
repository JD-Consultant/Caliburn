/** Per-item source summary, joined to the JD only by target identity (never by label). */
import type { Reference, Target } from '../../shared/api/generated/http/types.gen';

export interface SourceSummary {
  count: number;
  needsRecheck: boolean;
  citationIds: string[];
}

export function targetKey(target: Target): string {
  return [target.kind, target.field ?? '', target.item_id ?? ''].join(':');
}

export function buildSourceIndex(
  references: readonly Reference[] | undefined,
): Map<string, SourceSummary> {
  const index = new Map<string, SourceSummary>();
  for (const reference of references ?? []) {
    const key = targetKey(reference.target);
    const summary = index.get(key) ?? { count: 0, needsRecheck: false, citationIds: [] };
    summary.count += 1;
    summary.needsRecheck ||= reference.needs_recheck;
    summary.citationIds.push(reference.citation_id);
    index.set(key, summary);
  }
  return index;
}
