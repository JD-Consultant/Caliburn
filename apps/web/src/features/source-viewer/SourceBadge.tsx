/** "N sources / needs recheck" for one JD item. Needing recheck is not a claim that it is wrong. */
import { LinkIcon } from '../../shared/ui/icons';
import type { SourceSummary } from './source-index';

export function SourceBadge({
  summary,
  onOpen,
}: {
  summary: SourceSummary;
  onOpen: (citationIds: string[], trigger: HTMLButtonElement) => void;
}) {
  const label = summary.needsRecheck
    ? `來源 ${String(summary.count)} 筆，待核對`
    : `來源 ${String(summary.count)} 筆`;
  return (
    <button
      type="button"
      className={summary.needsRecheck ? 'source-badge source-badge--recheck' : 'source-badge'}
      aria-label={label}
      title={label}
      onClick={(event) => onOpen(summary.citationIds, event.currentTarget)}
    >
      <LinkIcon />
      <span aria-hidden="true">{summary.count}</span>
      {summary.needsRecheck && <span aria-hidden="true">待核對</span>}
    </button>
  );
}
