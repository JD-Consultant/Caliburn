/** One task with its outcomes, requirements and knowledge/skill links; intents go up unchanged. */
import { Box, Stack, Typography } from '@mui/material';
import type { Detail, JdWorkView, WorkTask } from '../../shared/api/generated/jd-work-view';
import { IconAction } from '../../shared/ui/IconAction';
import { ArrowDownIcon, ArrowUpIcon, DeleteIcon, EditIcon } from '../../shared/ui/icons';
import type { WorkIntent } from './jd-work-api';
import { detailTarget, itemTarget, useSourceBadge } from './source-badge-context';
import { TaskCapabilities } from './TaskCapabilities';
import type { WorkEditing } from './WorkEditDialog';

function TaskDetails({
  taskId,
  label,
  details,
  disabled,
  onMove,
}: {
  taskId: string;
  label: string;
  details: Detail[];
  disabled: boolean;
  onMove: (detailId: string, beforeId: string | null) => void;
}) {
  const badge = useSourceBadge();
  return (
    <Box>
      <Typography component="h5" variant="subtitle2">
        {label}
      </Typography>
      {details.length === 0 ? (
        <Typography color="text.secondary">尚未提供</Typography>
      ) : (
        <Box component="ol" sx={{ pl: 3, my: 1 }}>
          {details.map((detail, index) => (
            <li key={detail.detail_id} className="item">
              <Typography
                sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', display: 'inline' }}
              >
                {detail.text}
              </Typography>
              {badge(detailTarget(taskId, detail.detail_id))}
              <span className="item-actions">
                <IconAction
                  label={`上移${label} ${String(index + 1)}`}
                  disabled={disabled || index === 0}
                  onClick={() => onMove(detail.detail_id, details[index - 1]?.detail_id ?? null)}
                >
                  <ArrowUpIcon />
                </IconAction>
                <IconAction
                  label={`下移${label} ${String(index + 1)}`}
                  disabled={disabled || index === details.length - 1}
                  onClick={() => onMove(detail.detail_id, details[index + 2]?.detail_id ?? null)}
                >
                  <ArrowDownIcon />
                </IconAction>
              </span>
            </li>
          ))}
        </Box>
      )}
    </Box>
  );
}

interface TaskCardProps {
  task: WorkTask;
  index: number;
  group: WorkTask[];
  baseline: JdWorkView;
  disabled: boolean;
  onEdit: (editing: WorkEditing) => void;
  onDelete: (task: WorkTask) => void;
  onChange: (intent: WorkIntent) => void;
}

export function TaskCard({
  task,
  index,
  group,
  baseline,
  disabled,
  onEdit,
  onDelete,
  onChange,
}: TaskCardProps) {
  const name = task.title ?? '尚未命名的任務';
  const badge = useSourceBadge();
  function move(beforeId: string | null): void {
    onChange({
      collection: 'tasks',
      change: {
        action: 'move_task',
        task_id: task.task_id,
        area_id: task.area_id,
        before_task_id: beforeId,
        changes: [],
      },
    });
  }
  function reorderDetail(detailId: string, beforeId: string | null): void {
    onChange({
      collection: 'tasks',
      change: {
        action: 'reorder_detail',
        task_id: task.task_id,
        detail_id: detailId,
        before_detail_id: beforeId,
      },
    });
  }
  return (
    <Box
      component="article"
      id={`jd-task-${task.task_id}`}
      aria-label={name}
      sx={{ pt: 2, borderTop: 1, borderColor: 'divider', scrollMarginTop: 16 }}
    >
      <Stack spacing={1} className="item">
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography variant="subtitle1" component="h4">
            {name}
          </Typography>
          {badge(itemTarget('task', task.task_id))}
        </Stack>
        <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
          {task.description ?? '工作內容尚未提供'}
        </Typography>
        <Stack
          direction="row"
          className="item-actions item-actions--corner"
          sx={{ flexWrap: 'wrap' }}
        >
          <IconAction
            label="編輯任務"
            disabled={disabled}
            onClick={() => onEdit({ kind: 'task', baseline, task, areaId: task.area_id })}
          >
            <EditIcon />
          </IconAction>
          <IconAction
            label="上移任務"
            disabled={disabled || index === 0}
            onClick={() => move(group[index - 1]?.task_id ?? null)}
          >
            <ArrowUpIcon />
          </IconAction>
          <IconAction
            label="下移任務"
            disabled={disabled || index === group.length - 1}
            onClick={() => move(group[index + 2]?.task_id ?? null)}
          >
            <ArrowDownIcon />
          </IconAction>
          <IconAction
            label="刪除任務"
            color="error"
            disabled={disabled}
            onClick={() => onDelete(task)}
          >
            <DeleteIcon />
          </IconAction>
        </Stack>
        <TaskDetails
          taskId={task.task_id}
          label="工作成果"
          details={task.outcomes}
          disabled={disabled}
          onMove={reorderDetail}
        />
        <TaskDetails
          taskId={task.task_id}
          label="工作要求"
          details={task.requirements}
          disabled={disabled}
          onMove={reorderDetail}
        />
        <TaskCapabilities
          taskId={task.task_id}
          baseline={baseline}
          disabled={disabled}
          onChange={onChange}
        />
      </Stack>
    </Box>
  );
}
