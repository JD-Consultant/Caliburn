/** Group by saved JD identity; presentation never resolves a source by its label. */
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import type { Reference } from '../../shared/api/generated/jd-sources-view';
import { targetKey } from './source-index';

export interface SourceSelection {
  citationId: string;
  view: 'content' | 'changes';
}

interface Props {
  references: readonly Reference[];
  selected: SourceSelection | null;
  onSelect: (selection: SourceSelection) => void;
}

function changeLabel(reference: Reference): string {
  if (reference.jd_changed && reference.source_changed) return 'JD 與來源皆有變更';
  if (reference.jd_changed) return 'JD 已修改';
  if (reference.source_changed) return '來源已更新';
  return '待核對';
}

export function SourceReferenceList({ references, selected, onSelect }: Props) {
  const groups = new Map<string, Reference[]>();
  for (const reference of references) {
    // Legacy references without a target stay separate, even if their labels match.
    const key = reference.target ? targetKey(reference.target) : reference.citation_id;
    const group = groups.get(key) ?? [];
    group.push(reference);
    groups.set(key, group);
  }
  return (
    <Stack>
      {[...groups].map(([key, group]) => (
        <Box key={key} className="source-ref">
          <Typography component="h3" variant="subtitle2" sx={{ overflowWrap: 'anywhere' }}>
            {group[0]?.target_label}
          </Typography>
          <Stack component="ul" spacing={1.5} sx={{ listStyle: 'none', m: 0, p: 0 }}>
            {group.map((reference) => (
              <Stack
                component="li"
                key={reference.citation_id}
                aria-label={reference.source_label}
                spacing={0.5}
              >
                <Button
                  size="small"
                  aria-pressed={
                    selected?.citationId === reference.citation_id && selected.view === 'content'
                  }
                  onClick={() => onSelect({ citationId: reference.citation_id, view: 'content' })}
                  sx={{ alignSelf: 'flex-start', textAlign: 'left', overflowWrap: 'anywhere' }}
                >
                  {reference.source_label}
                </Button>
                {reference.needs_recheck && (
                  <Stack
                    direction="row"
                    useFlexGap
                    spacing={1}
                    sx={{ alignItems: 'center', flexWrap: 'wrap' }}
                  >
                    <Chip label={changeLabel(reference)} size="small" color="warning" />
                    <Button
                      size="small"
                      aria-pressed={
                        selected?.citationId === reference.citation_id &&
                        selected.view === 'changes'
                      }
                      onClick={() =>
                        onSelect({ citationId: reference.citation_id, view: 'changes' })
                      }
                    >
                      查看差異
                    </Button>
                  </Stack>
                )}
              </Stack>
            ))}
          </Stack>
        </Box>
      ))}
    </Stack>
  );
}
