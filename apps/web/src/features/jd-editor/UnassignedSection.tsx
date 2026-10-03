/** The tasks that belong to no responsibility: folds like a responsibility does, but has no name to edit. */
import type { ReactNode } from 'react';
import { Paper, Stack, Typography } from '@mui/material';
import { FoldToggle } from './FoldToggle';
import { useFold } from './use-fold';

export function UnassignedSection({
  taskCount,
  children,
}: {
  taskCount: number;
  children: ReactNode;
}) {
  const fold = useFold();
  return (
    <Paper
      variant="outlined"
      component="section"
      aria-label="未歸屬任務"
      className="jd-area"
      sx={{ p: { xs: 1.5, sm: 2 } }}
    >
      <Stack spacing={2}>
        <Stack
          direction="row"
          spacing={1}
          className="jd-fold-head"
          sx={{ alignItems: 'center', flexWrap: 'wrap' }}
        >
          <FoldToggle name="未歸屬任務" fold={fold} />
          <Typography component="h3" variant="h6" className="jd-area-title">
            未歸屬任務
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {String(taskCount)} 項任務
          </Typography>
        </Stack>
        <div id={fold.bodyId} hidden={!fold.expanded} className="jd-area-body">
          {children}
        </div>
      </Stack>
    </Paper>
  );
}
