/** One task with its outcomes, requirements and knowledge/skill links; intents go up unchanged. */
import { Box, Stack, Typography } from '@mui/material';
import type { Detail, JdWorkView, WorkTask } from '../../shared/api/generated/jd-work-view';
import { IconAction } from '../../shared/ui/IconAction';
import { ArrowDownIcon, ArrowUpIcon, CloseIcon } from '../../shared/ui/icons';
import { FoldToggle } from './FoldToggle';
import { UNASSIGNED, areaChoices } from './area-choice';
import type { WorkIntent } from './jd-work-api';
import { InlineText } from './InlineText';
import { taskDescriptionField, taskTitleField } from './inline-fields';
import { MoveMenu } from './MoveMenu';
import { itemTarget, useSourceBadge } from './source-badge-context';
import { TaskCapabilities } from './TaskCapabilities';
import { TaskDetails } from './TaskDetails';
import { useFold } from './use-fold';

interface TaskCardProps {
  task: WorkTask;
  index: number;
  group: WorkTask[];
  baseline: JdWorkView;
  disabled: boolean;
  onDelete: (task: WorkTask) => void;
  onDeleteDetail: (task: WorkTask, detail: Detail, label: string) => void;
  onChange: (intent: WorkIntent) => void;
}

export function TaskCard({
  task,
  index,
  group,
  baseline,
  disabled,
  onDelete,
  onDeleteDetail,
  onChange,
}: TaskCardProps) {
  const fold = useFold();
  const { expanded } = fold;
  const name = task.title ?? '尚未命名的任務';
  const badge = useSourceBadge();
  /** Reorders within the group, or (with another `areaId`) moves to the end of that responsibility. */
  function move(areaId: string | null, beforeId: string | null): void {
    onChange({
      collection: 'tasks',
      change: {
        action: 'move_task',
        task_id: task.task_id,
        area_id: areaId,
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
      sx={{ pt: 2.5, borderTop: 1, borderColor: 'divider', scrollMarginTop: 16 }}
    >
      <Stack spacing={1.5} className="item">
        <Stack
          direction="row"
          spacing={1}
          className="jd-fold-head"
          sx={{ alignItems: 'center', flexWrap: 'wrap' }}
        >
          <FoldToggle name={`任務 ${name}`} fold={fold} />
          <InlineText field={taskTitleField(task)}>
            <Typography variant="subtitle1" component="h4">
              {name}
            </Typography>
          </InlineText>
          {badge(itemTarget('task', task.task_id))}
        </Stack>
        <div hidden={!expanded}>
          <InlineText field={taskDescriptionField(task)}>
            <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
              {task.description ?? '工作內容尚未提供'}
            </Typography>
          </InlineText>
        </div>
        {expanded && (
          <Stack
            direction="row"
            className="item-actions item-actions--corner"
            sx={{ flexWrap: 'wrap' }}
          >
            <IconAction
              label="上移任務"
              disabled={disabled || index === 0}
              onClick={() => move(task.area_id, group[index - 1]?.task_id ?? null)}
            >
              <ArrowUpIcon />
            </IconAction>
            <IconAction
              label="下移任務"
              disabled={disabled || index === group.length - 1}
              onClick={() => move(task.area_id, group[index + 2]?.task_id ?? null)}
            >
              <ArrowDownIcon />
            </IconAction>
            <MoveMenu
              label="移到其他職責"
              heading="移到職責"
              destinations={areaChoices(baseline.areas)}
              current={task.area_id ?? UNASSIGNED}
              disabled={disabled}
              onMove={(value) => move(value === UNASSIGNED ? null : value, null)}
            />
            <IconAction
              label="刪除任務"
              color="error"
              disabled={disabled}
              onClick={() => onDelete(task)}
            >
              <CloseIcon />
            </IconAction>
          </Stack>
        )}
        <div id={fold.bodyId} hidden={!expanded}>
          <Stack spacing={1.5}>
            {(['outcome', 'requirement'] as const).map((kind) => (
              <TaskDetails
                key={kind}
                taskId={task.task_id}
                kind={kind}
                details={kind === 'outcome' ? task.outcomes : task.requirements}
                disabled={disabled}
                onMove={reorderDetail}
                onRemove={(detail, label) => onDeleteDetail(task, detail, label)}
              />
            ))}
            <TaskCapabilities
              taskId={task.task_id}
              baseline={baseline}
              disabled={disabled}
              onChange={onChange}
            />
          </Stack>
        </div>
      </Stack>
    </Box>
  );
}
