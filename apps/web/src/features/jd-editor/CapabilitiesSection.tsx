/** Shared definitions and reverse usage derive from the same fixed JD projection. */
import { Box, Button, Link, Paper, Stack, Typography } from '@mui/material';
import type { Capability, JdWorkView } from '../../shared/api/generated/jd-work-view';
import type { WorkIntent } from './jd-work-api';
import type { WorkEditing } from './WorkEditDialog';

interface Props {
  kind: Capability['kind'];
  baseline: JdWorkView;
  disabled: boolean;
  onEdit: (editing: WorkEditing) => void;
  onChange: (intent: WorkIntent) => void;
  onDelete: (capability: Capability) => void;
}

export function CapabilitiesSection({
  kind,
  baseline,
  disabled,
  onEdit,
  onChange,
  onDelete,
}: Props) {
  const label = kind === 'knowledge' ? '知識' : '技能';
  const group = baseline.capabilities.filter((item) => item.kind === kind);
  function move(capabilityId: string, beforeId: string | null): void {
    onChange({
      collection: 'capabilities',
      change: {
        action: 'reorder_capability',
        capability_id: capabilityId,
        before_capability_id: beforeId,
      },
    });
  }
  return (
    <Paper
      component="section"
      aria-label={`所需${label}`}
      variant="outlined"
      sx={{ p: { xs: 1.5, sm: 2 } }}
    >
      <Stack spacing={2}>
        <Typography component="h3" variant="h6">
          所需{label}
        </Typography>
        <Typography color="text.secondary">
          共用定義保留一份，在任務中選擇需要的{label}。沒有關聯不代表已確認不需要。
        </Typography>
        {group.length === 0 && <p>尚未提供{label}</p>}
        {group.map((capability, index) => {
          const name = capability.name ?? `尚未命名的${label}`;
          const users = baseline.tasks.filter((task) =>
            baseline.task_links.some(
              (link) =>
                link.task_id === task.task_id && link.capability_id === capability.capability_id,
            ),
          );
          return (
            <Box
              component="article"
              aria-label={`${label}：${name}`}
              id={`jd-capability-${capability.capability_id}`}
              key={capability.capability_id}
              sx={{ borderTop: 1, borderColor: 'divider', pt: 2, scrollMarginTop: 16 }}
            >
              <Typography component="h4" variant="subtitle1" sx={{ overflowWrap: 'anywhere' }}>
                {name}
              </Typography>
              <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                {capability.description ?? '說明尚未提供'}
              </Typography>
              <Typography variant="body2" sx={{ mt: 1 }}>
                使用此項的任務：
              </Typography>
              {users.length === 0 ? (
                <Typography color="text.secondary">尚無關聯任務</Typography>
              ) : (
                <Box component="ul" sx={{ pl: 3, my: 0.5 }}>
                  {users.map((task) => (
                    <li key={task.task_id}>
                      <Link href={`#jd-task-${task.task_id}`} sx={{ overflowWrap: 'anywhere' }}>
                        {baseline.areas.find((area) => area.area_id === task.area_id)?.title ??
                          (task.area_id ? '尚未命名的職責' : '未歸屬任務')}
                        ／{task.title ?? task.description ?? '尚未命名的任務'}
                      </Link>
                    </li>
                  ))}
                </Box>
              )}
              <Stack direction="row" sx={{ flexWrap: 'wrap' }}>
                <Button
                  disabled={disabled}
                  onClick={() =>
                    onEdit({ kind: 'capability', baseline, capabilityKind: kind, capability })
                  }
                >
                  編輯{label}
                </Button>
                <Button
                  disabled={disabled || index === 0}
                  onClick={() =>
                    move(capability.capability_id, group[index - 1]?.capability_id ?? null)
                  }
                >
                  上移{label}
                </Button>
                <Button
                  disabled={disabled || index === group.length - 1}
                  onClick={() =>
                    move(capability.capability_id, group[index + 2]?.capability_id ?? null)
                  }
                >
                  下移{label}
                </Button>
                <Button
                  color="error"
                  disabled={disabled || users.length > 0}
                  onClick={() => onDelete(capability)}
                >
                  刪除{label}
                </Button>
              </Stack>
              {users.length > 0 && (
                <Typography variant="caption">
                  仍被任務使用；請先到上述任務解除關聯，才能刪除此共用定義。
                </Typography>
              )}
            </Box>
          );
        })}
        <div>
          <Button
            disabled={disabled}
            onClick={() => onEdit({ kind: 'capability', baseline, capabilityKind: kind })}
          >
            新增{label}
          </Button>
        </div>
      </Stack>
    </Paper>
  );
}
