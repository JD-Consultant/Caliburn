import { useRef, type ReactNode } from 'react';
import { IconButton, Paper, Stack, Typography } from '@mui/material';
import { ExpandLessIcon, ExpandMoreIcon } from '../../../shared/ui/icons';
import { useFold } from './useFold';

/** 收合只影響呈現，新增表單與未保存草稿始終保持掛載。 */
export function FoldableSection({
  id,
  title,
  count,
  actions,
  children,
}: {
  id: string;
  title: string;
  count?: number;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const section = useRef<HTMLElement>(null);
  const { bodyId, expanded, toggle } = useFold(section);
  return (
    <Paper
      component="section"
      ref={section}
      id={id}
      tabIndex={-1}
      aria-label={title}
      variant="outlined"
      className="jd-section jd-foldable-section"
    >
      <Stack
        direction="row"
        spacing={1}
        className="jd-collection-heading jd-fold-head"
        sx={{ alignItems: 'center' }}
      >
        <IconButton
          size="small"
          aria-label={`${expanded ? '收合' : '展開'}${title}`}
          aria-expanded={expanded}
          aria-controls={bodyId}
          onClick={toggle}
        >
          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
        <Typography component="h2" variant="h5">
          {title}
        </Typography>
        {count !== undefined && (
          <Typography variant="body2" color="text.secondary">
            {count} 項
          </Typography>
        )}
        {actions}
      </Stack>
      <div id={bodyId} hidden={!expanded} className="jd-section-body">
        {children}
      </div>
    </Paper>
  );
}
