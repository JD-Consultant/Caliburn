/** Ordered usage links, not copies of shared capability text. */
import { Box, Link, MenuItem, Stack, TextField, Typography } from '@mui/material';
import type { Capability, JdWorkView } from '../../shared/api/generated/jd-work-view';
import type { WorkIntent } from './jd-work-api';
import { IconAction } from '../../shared/ui/IconAction';
import { ArrowDownIcon, ArrowUpIcon, CloseIcon } from '../../shared/ui/icons';

interface Props {
  taskId: string;
  baseline: JdWorkView;
  disabled: boolean;
  onChange: (intent: WorkIntent) => void;
}

export function TaskCapabilities({ taskId, baseline, disabled, onChange }: Props) {
  const links = baseline.task_links.filter((link) => link.task_id === taskId);
  function setLink(capabilityId: string, linked: boolean): void {
    onChange({
      collection: 'capabilities',
      change: {
        action: 'set_task_capability',
        task_id: taskId,
        capability_id: capabilityId,
        linked,
      },
    });
  }
  function move(capabilityId: string, beforeId: string | null): void {
    onChange({
      collection: 'capabilities',
      change: {
        action: 'reorder_task_capability',
        task_id: taskId,
        capability_id: capabilityId,
        before_capability_id: beforeId,
      },
    });
  }
  return (['knowledge', 'skill'] as const).map((kind) => {
    const label = kind === 'knowledge' ? '知識' : '技能';
    // Relation order is independent of overview order. Both come from the same revision.
    const linked = links.flatMap((link) => {
      const item = baseline.capabilities.find(
        (capability) => capability.capability_id === link.capability_id && capability.kind === kind,
      );
      return item ? [item] : [];
    });
    const available = baseline.capabilities.filter(
      (item) =>
        item.kind === kind && !links.some((link) => link.capability_id === item.capability_id),
    );
    function choiceLabel(item: Capability, index: number): string {
      return `${String(index + 1)}. ${item.name ?? `尚未命名的${label}`}${item.description ? ` — ${item.description}` : ''}`;
    }
    return (
      <Box component="section" aria-label={`${label}關聯`} key={kind} className="item">
        <Typography component="h5" variant="overline" className="jd-label">
          所需{label}
        </Typography>
        {linked.length === 0 ? (
          <Typography variant="body2" className="jd-empty">
            尚未關聯
          </Typography>
        ) : (
          <Box component="ol" sx={{ pl: 3, my: 1 }}>
            {linked.map((item, index) => {
              const name = item.name ?? `尚未命名的${label}`;
              return (
                <li key={item.capability_id} className="item">
                  <Link
                    href={`#jd-capability-${item.capability_id}`}
                    sx={{ overflowWrap: 'anywhere' }}
                  >
                    {name}
                  </Link>
                  {item.description && (
                    <Typography
                      variant="body2"
                      sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}
                    >
                      {item.description}
                    </Typography>
                  )}
                  <Stack direction="row" className="item-actions" sx={{ flexWrap: 'wrap' }}>
                    <IconAction
                      label={`上移${label}關聯 ${name}`}
                      disabled={disabled || index === 0}
                      onClick={() =>
                        move(item.capability_id, linked[index - 1]?.capability_id ?? null)
                      }
                    >
                      <ArrowUpIcon />
                    </IconAction>
                    <IconAction
                      label={`下移${label}關聯 ${name}`}
                      disabled={disabled || index === linked.length - 1}
                      onClick={() =>
                        move(item.capability_id, linked[index + 2]?.capability_id ?? null)
                      }
                    >
                      <ArrowDownIcon />
                    </IconAction>
                    <IconAction
                      label={`解除${label} ${name}`}
                      disabled={disabled}
                      onClick={() => setLink(item.capability_id, false)}
                    >
                      <CloseIcon />
                    </IconAction>
                  </Stack>
                </li>
              );
            })}
          </Box>
        )}
        {available.length > 0 ? (
          <div className="item-actions item-actions--float">
            <TextField
              select
              fullWidth
              size="small"
              id={`task-${taskId}-${kind}`}
              label={`新增${label}關聯`}
              value=""
              disabled={disabled}
              onChange={(event) => setLink(event.target.value, true)}
              helperText="選取後即保存關聯；解除關聯不會刪除共用定義。"
              // A compact one-line picker: the label stays as the accessible name (CSS hides it), and
              // the closed control reads as the action itself. A tall labelled field overlapped the
              // next section's picker when floated.
              slotProps={{
                select: {
                  displayEmpty: true,
                  renderValue: () => <span>＋ 新增{label}關聯</span>,
                },
              }}
              sx={{ mt: 1 }}
            >
              {available.map((item, index) => (
                <MenuItem
                  key={item.capability_id}
                  value={item.capability_id}
                  sx={{ whiteSpace: 'normal', overflowWrap: 'anywhere' }}
                >
                  {choiceLabel(item, index)}
                </MenuItem>
              ))}
            </TextField>
          </div>
        ) : (
          <Typography variant="caption">
            沒有其他可選{label}；可到下方所需{label}區新增。
          </Typography>
        )}
      </Box>
    );
  });
}
