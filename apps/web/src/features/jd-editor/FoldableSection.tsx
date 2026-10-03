/**
 * A top-level JD section that folds to its heading and count (Notion's toggles, the GOV.UK accordion's
 * show/hide): the long, reference-like sections can be put away while the reader works elsewhere. They
 * start open, because everything in them is part of the formal JD. The section bar opens a folded section
 * it is asked to jump to (see use-fold).
 */
import { useRef } from 'react';
import type { ReactNode } from 'react';
import { Paper, Stack, Typography } from '@mui/material';
import { FoldToggle } from './FoldToggle';
import { useFold } from './use-fold';

interface Props {
  /** The section's anchor, which the section bar jumps to. */
  id: string;
  title: string;
  count: number;
  children: ReactNode;
}

export function FoldableSection({ id, title, count, children }: Props) {
  const section = useRef<HTMLDivElement>(null);
  const fold = useFold(section);
  return (
    <Paper
      component="section"
      ref={section}
      id={id}
      aria-label={title}
      variant="outlined"
      sx={{ p: { xs: 1.5, sm: 2 } }}
    >
      <Stack spacing={2}>
        <Stack
          direction="row"
          spacing={1}
          className="jd-fold-head"
          sx={{ alignItems: 'center', flexWrap: 'wrap' }}
        >
          <FoldToggle name={title} fold={fold} />
          <Typography component="h3" variant="h5">
            {title}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {String(count)} 項
          </Typography>
        </Stack>
        <div id={fold.bodyId} hidden={!fold.expanded}>
          <Stack spacing={2}>{children}</Stack>
        </div>
      </Stack>
    </Paper>
  );
}
