/** Shared definitions and reverse usage derive from the same fixed JD projection. */
import { Box, Button, Link, Stack, Typography } from '@mui/material';
import type { Capability, JdWorkView } from '../../shared/api/generated/jd-work-view';
import type { WorkIntent } from './jd-work-api';
import type { WorkDialogContent } from './WorkDialog';
import { FoldableSection } from './FoldableSection';
import { InlineText } from './InlineText';
import { capabilityDescriptionField, capabilityNameField } from './inline-fields';
import { itemTarget, useSourceBadge } from './source-badge-context';
import { IconAction } from '../../shared/ui/IconAction';
import { AddIcon, ArrowDownIcon, ArrowUpIcon, CloseIcon } from '../../shared/ui/icons';

interface Props {
  kind: Capability['kind'];
  baseline: JdWorkView;
  disabled: boolean;
  onCreate: (content: WorkDialogContent) => void;
  onChange: (intent: WorkIntent) => void;
  onDelete: (capability: Capability) => void;
}

export function CapabilitiesSection({
  kind,
  baseline,
  disabled,
  onCreate,
  onChange,
  onDelete,
}: Props) {
  const label = kind === 'knowledge' ? '知識' : '技能';
  const badge = useSourceBadge();
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
    <FoldableSection id={`jd-${kind}`} title={`所需${label}`} count={group.length}>
      <Typography variant="body2" color="text.secondary">
        共用定義保留一份，在任務中選擇需要的{label}；修改定義，所有使用它的任務都會顯示新版。
        沒有關聯不代表已確認不需要。
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
            className="item jd-ruled-item"
            sx={{ scrollMarginTop: 16 }}
          >
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
              <InlineText field={capabilityNameField(capability)}>
                <Typography component="h4" variant="subtitle1" sx={{ overflowWrap: 'anywhere' }}>
                  {name}
                </Typography>
              </InlineText>
              {badge(itemTarget('capability', capability.capability_id))}
            </Stack>
            <InlineText field={capabilityDescriptionField(capability)}>
              <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                {capability.description ?? '說明尚未提供'}
              </Typography>
            </InlineText>
            <Typography variant="overline" component="p" className="jd-label" sx={{ mt: 1.5 }}>
              使用此項的任務
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
            <Stack
              direction="row"
              className="item-actions item-actions--corner"
              sx={{ flexWrap: 'wrap' }}
            >
              <IconAction
                label={`上移${label}`}
                disabled={disabled || index === 0}
                onClick={() =>
                  move(capability.capability_id, group[index - 1]?.capability_id ?? null)
                }
              >
                <ArrowUpIcon />
              </IconAction>
              <IconAction
                label={`下移${label}`}
                disabled={disabled || index === group.length - 1}
                onClick={() =>
                  move(capability.capability_id, group[index + 2]?.capability_id ?? null)
                }
              >
                <ArrowDownIcon />
              </IconAction>
              <IconAction
                label={`刪除${label}`}
                color="error"
                disabled={disabled || users.length > 0}
                onClick={() => onDelete(capability)}
              >
                <CloseIcon />
              </IconAction>
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
          size="small"
          className="add-action"
          startIcon={<AddIcon />}
          disabled={disabled}
          onClick={() => onCreate({ kind: 'capability', baseline, capabilityKind: kind })}
        >
          新增{label}
        </Button>
      </div>
    </FoldableSection>
  );
}
