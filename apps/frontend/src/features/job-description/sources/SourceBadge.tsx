import { Button } from '@mui/material';
import { useContext } from 'react';
import type { CitationResponse } from '../../../shared/api/generated/types.gen';
import { SourcesContext } from './sources-context';

export function SourceBadge({
  targetKind,
  targetId,
}: {
  targetKind: CitationResponse['target_kind'];
  targetId: string;
}) {
  const sources = useContext(SourcesContext);
  const citations =
    sources?.jobDescription.citations?.filter(
      (citation) =>
        citation.target_kind === targetKind && citation.target_id === targetId,
    ) ?? [];
  if (!sources || citations.length === 0) return null;
  const changed = citations.some((citation) => citation.jd_changed);
  return (
    <Button
      size="small"
      className="jd-source-badge"
      aria-label={`查看此項目的 ${String(citations.length)} 筆來源${changed ? '，JD 已變更待核對' : ''}`}
      onClick={(event) =>
        sources.show(event.currentTarget, { kind: targetKind, id: targetId })
      }
    >
      來源 {citations.length}
      {changed ? ' · 待核對' : ''}
    </Button>
  );
}
