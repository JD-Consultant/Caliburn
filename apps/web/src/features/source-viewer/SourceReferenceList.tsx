/**
 * Group by saved JD identity; presentation never resolves a source by its label. A row is an action
 * list item (Primer ActionList): leading kind icon, the source label, a trailing chevron, and — when the
 * source needs recheck — the reason and a secondary action beneath it.
 */
import { useEffect, useId, useRef } from 'react';
import { Button, Chip } from '@mui/material';
import type { Reference } from '../../shared/api/generated/jd-sources-view';
import { ChevronRightIcon } from '../../shared/ui/icons';
import { changeLabel } from './source-labels';
import { SourceKindIcon } from './SourceKindIcon';
import type { SourceSelection } from './source-selection';
import { targetKey } from './source-index';

interface Props {
  references: readonly Reference[];
  /** The source the reader just came back from: it takes focus when the list is shown again. */
  focusCitationId: string | null;
  onOpen: (selection: SourceSelection) => void;
}

export function SourceReferenceList({ references, focusCitationId, onOpen }: Props) {
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (focusCitationId === null) return;
    const row = [...(list.current?.querySelectorAll('[data-citation-id]') ?? [])].find(
      (item) => item.getAttribute('data-citation-id') === focusCitationId,
    );
    row?.querySelector<HTMLButtonElement>('.source-row__main')?.focus();
  }, [focusCitationId]);

  const groups = new Map<string, Reference[]>();
  for (const reference of references) {
    // Legacy references without a target stay separate, even if their labels match.
    const key = reference.target ? targetKey(reference.target) : reference.citation_id;
    const group = groups.get(key) ?? [];
    group.push(reference);
    groups.set(key, group);
  }
  return (
    <div ref={list} className="source-list">
      {[...groups].map(([key, group]) => (
        <section key={key} className="source-group">
          <h4 className="source-group__title">{group[0]?.target_label}</h4>
          <ul className="source-group__rows">
            {group.map((reference) => (
              <SourceRow key={reference.citation_id} reference={reference} onOpen={onOpen} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function SourceRow({
  reference,
  onOpen,
}: {
  reference: Reference;
  onOpen: (selection: SourceSelection) => void;
}) {
  const statusId = useId();
  const citationId = reference.citation_id;
  return (
    <li className="source-row" aria-label={reference.source_label} data-citation-id={citationId}>
      <button
        type="button"
        className="source-row__main"
        aria-describedby={reference.needs_recheck ? statusId : undefined}
        onClick={() => onOpen({ citationId, view: 'content' })}
      >
        <SourceKindIcon kind={reference.source_kind} />
        <span className="source-row__label">{reference.source_label}</span>
      </button>
      <ChevronRightIcon className="source-row__chevron" aria-hidden="true" />
      {reference.needs_recheck && (
        <span className="source-row__meta">
          <Chip id={statusId} label={changeLabel(reference)} size="small" color="warning" />
          <Button size="small" onClick={() => onOpen({ citationId, view: 'changes' })}>
            查看差異
          </Button>
        </span>
      )}
    </li>
  );
}
