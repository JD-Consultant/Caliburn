/** One responsibility: a collapsible header with its own actions; its tasks arrive as children. */
import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import { Paper, Stack, Typography } from '@mui/material';
import type { Area } from '../../shared/api/generated/jd-work-view';
import { IconAction } from '../../shared/ui/IconAction';
import {
  ArrowDownIcon,
  ArrowUpIcon,
  DeleteIcon,
  EditIcon,
  ExpandLessIcon,
  ExpandMoreIcon,
} from '../../shared/ui/icons';
import { itemTarget, useSourceBadge } from './source-badge-context';

interface AreaSectionProps {
  area: Area;
  isFirst: boolean;
  isLast: boolean;
  taskCount: number;
  disabled: boolean;
  onEdit: () => void;
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
  onEdit,
  onMoveUp,
  onMoveDown,
  onDelete,
  children,
}: AreaSectionProps) {
  // Collapsing is presentation only; the tasks stay mounted so nothing reloads or resets.
  const [expanded, setExpanded] = useState(true);
  const badge = useSourceBadge();
  const bodyId = useId();
  const title = area.title ?? '尚未命名的職責';
  return (
    <Paper variant="outlined" component="section" aria-label={title} sx={{ p: { xs: 1.5, sm: 2 } }}>
      <Stack spacing={2} className="item">
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <IconAction
            label={`${expanded ? '收合' : '展開'}職責 ${title}`}
            aria-expanded={expanded}
            aria-controls={bodyId}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconAction>
          <Typography component="h3" variant="h6">
            {title}
          </Typography>
          {badge(itemTarget('area', area.area_id))}
          {!expanded && (
            <Typography variant="body2" color="text.secondary">
              {String(taskCount)} 項任務
            </Typography>
          )}
        </Stack>
        {expanded && (
          <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
            {area.scope_text ?? '職責範圍尚未提供'}
          </Typography>
        )}
        {expanded && (
          <Stack
            direction="row"
            className="item-actions item-actions--corner"
            sx={{ flexWrap: 'wrap' }}
          >
            <IconAction label="編輯職責" disabled={disabled} onClick={onEdit}>
              <EditIcon />
            </IconAction>
            <IconAction label="上移職責" disabled={disabled || isFirst} onClick={onMoveUp}>
              <ArrowUpIcon />
            </IconAction>
            <IconAction label="下移職責" disabled={disabled || isLast} onClick={onMoveDown}>
              <ArrowDownIcon />
            </IconAction>
            <IconAction label="刪除職責" color="error" disabled={disabled} onClick={onDelete}>
              <DeleteIcon />
            </IconAction>
          </Stack>
        )}
        <div id={bodyId} hidden={!expanded}>
          {children}
        </div>
      </Stack>
    </Paper>
  );
}
