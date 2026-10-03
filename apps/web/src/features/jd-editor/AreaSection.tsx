/** One responsibility: a collapsible header with its own actions; its tasks arrive as children. */
import type { ReactNode } from 'react';
import { Paper, Stack, Typography } from '@mui/material';
import type { Area } from '../../shared/api/generated/jd-work-view';
import { IconAction } from '../../shared/ui/IconAction';
import { ArrowDownIcon, ArrowUpIcon, CloseIcon } from '../../shared/ui/icons';
import { FoldToggle } from './FoldToggle';
import { InlineText } from './InlineText';
import { areaScopeField, areaTitleField } from './inline-fields';
import { itemTarget, useSourceBadge } from './source-badge-context';
import { useFold } from './use-fold';

interface AreaSectionProps {
  area: Area;
  isFirst: boolean;
  isLast: boolean;
  taskCount: number;
  disabled: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDelete: () => void;
  children: ReactNode;
}

export function AreaSection({
  area,
  isFirst,
  isLast,
  taskCount,
  disabled,
  onMoveUp,
  onMoveDown,
  onDelete,
  children,
}: AreaSectionProps) {
  const fold = useFold();
  const { expanded } = fold;
  const badge = useSourceBadge();
  const title = area.title ?? '尚未命名的職責';
  return (
    <Paper
      variant="outlined"
      component="section"
      aria-label={title}
      className="jd-area"
      sx={{ p: { xs: 1.5, sm: 2 } }}
    >
      <Stack spacing={2} className="item">
        <Stack
          direction="row"
          spacing={1}
          className="jd-fold-head"
          sx={{ alignItems: 'center', flexWrap: 'wrap' }}
        >
          <FoldToggle name={`職責 ${title}`} fold={fold} />
          <InlineText field={areaTitleField(area)}>
            <Typography component="h3" variant="h6" className="jd-area-title">
              {title}
            </Typography>
          </InlineText>
          <Typography variant="body2" color="text.secondary">
            {String(taskCount)} 項任務
          </Typography>
          {badge(itemTarget('area', area.area_id))}
        </Stack>
        <div hidden={!expanded} className="jd-area-scope">
          <InlineText field={areaScopeField(area)}>
            <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
              {area.scope_text ?? '職責範圍尚未提供'}
            </Typography>
          </InlineText>
        </div>
        {expanded && (
          <Stack
            direction="row"
            className="item-actions item-actions--corner"
            sx={{ flexWrap: 'wrap' }}
          >
            <IconAction label="上移職責" disabled={disabled || isFirst} onClick={onMoveUp}>
              <ArrowUpIcon />
            </IconAction>
            <IconAction label="下移職責" disabled={disabled || isLast} onClick={onMoveDown}>
              <ArrowDownIcon />
            </IconAction>
            <IconAction label="刪除職責" color="error" disabled={disabled} onClick={onDelete}>
              <CloseIcon />
            </IconAction>
          </Stack>
        )}
        <div id={fold.bodyId} hidden={!expanded} className="jd-area-body">
          {children}
        </div>
      </Stack>
    </Paper>
  );
}
