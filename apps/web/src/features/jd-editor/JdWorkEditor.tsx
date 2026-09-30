/** Grouped manual editing over one formal revision; all mutations use original command recovery. */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Paper, Stack, Typography } from '@mui/material';
import { describeReadError } from '../../shared/api/http';
import { AddIcon } from '../../shared/ui/icons';
import { commandFor, jdWorkQuery } from './jd-work-api';
import type { WorkIntent } from './jd-work-api';
import { useWorkCommand } from './useWorkCommand';
import { WorkEditDialog } from './WorkEditDialog';
import type { WorkEditing } from './WorkEditDialog';
import { AreaSection } from './AreaSection';
import { CapabilitiesSection } from './CapabilitiesSection';
import { CollaboratorsSection } from './CollaboratorsSection';
import { ConditionsSection } from './ConditionsSection';
import { TaskCard } from './TaskCard';

export function JdWorkEditor({
  jobFileId,
  readOnly = false,
}: {
  jobFileId: string;
  /** A Turn owns the JD: show it, but offer no manual edit (the App also refuses writes). */
  readOnly?: boolean;
}) {
  const work = useQuery(jdWorkQuery(jobFileId));
  const [editing, setEditing] = useState<WorkEditing | null>(null);
  const command = useWorkCommand(jobFileId, () => setEditing(null));
  const current = work.data;
  const disabled = command.locked || work.isFetching || work.isError || readOnly;

  function submitIntent(intent: WorkIntent): void {
    if (current && !disabled) void command.send(commandFor(current.revision_id, intent));
  }
  function confirm(title: string, description: string, intent: WorkIntent): void {
    if (current)
      setEditing({
        kind: 'confirm',
        title,
        description,
        command: commandFor(current.revision_id, intent),
      });
  }
  function renderTasks(areaId: string | null) {
    if (!current) return null;
    const group = current.tasks.filter((task) => task.area_id === areaId);
    return (
      <Stack spacing={1}>
        {group.length === 0 && <Typography color="text.secondary">尚無任務</Typography>}
        {group.map((task, index) => (
          <TaskCard
            key={task.task_id}
            task={task}
            index={index}
            group={group}
            baseline={current}
            disabled={disabled}
            onEdit={setEditing}
            onChange={submitIntent}
            onDelete={(target) =>
              confirm(
                '刪除任務',
                `移除「${target.title ?? '尚未命名的任務'}」及其成果、要求；已保存的歷史不改寫。`,
                { collection: 'tasks', change: { action: 'delete_task', task_id: target.task_id } },
              )
            }
          />
        ))}
        <div>
          <Button
            size="small"
            startIcon={<AddIcon />}
            disabled={disabled}
            onClick={() => setEditing({ kind: 'task', baseline: current, areaId })}
          >
            新增任務
          </Button>
        </div>
      </Stack>
    );
  }

  return (
    <section id="jd-work" aria-labelledby="jd-work-heading">
      <Stack spacing={2}>
        <Typography variant="h6" component="h2" id="jd-work-heading">
          JD 職責與任務
        </Typography>
        {work.isPending && <p role="status">正在讀取職責與任務…</p>}
        {work.isError && (
          <Alert
            severity="error"
            action={
              <Button
                onClick={() => {
                  void work.refetch();
                }}
              >
                重新讀取職責與任務
              </Button>
            }
          >
            {describeReadError(work.error)}
          </Alert>
        )}
        {command.message && !editing && <Alert severity="warning">{command.message}</Alert>}
        {!editing && command.pending && (
          <Button
            disabled={command.isSending || command.blocked}
            onClick={() => {
              if (command.pending) void command.send(command.pending);
            }}
          >
            重新確認修改結果
          </Button>
        )}
        {!editing && command.blocked && <Button onClick={command.reload}>讀取目前 JD</Button>}
        {!editing && command.isSending && <p role="status">正在確認修改…</p>}
        {current && !work.isError && (
          <>
            <div>
              <Button
                size="small"
                startIcon={<AddIcon />}
                variant="outlined"
                disabled={disabled}
                onClick={() => setEditing({ kind: 'area', baseline: current })}
              >
                新增職責
              </Button>
            </div>
            {current.areas.length === 0 && <p>尚無職責。可先記錄任務，再整理歸屬。</p>}
            {current.areas.map((area, index) => (
              <AreaSection
                key={area.area_id}
                area={area}
                isFirst={index === 0}
                isLast={index === current.areas.length - 1}
                taskCount={current.tasks.filter((task) => task.area_id === area.area_id).length}
                disabled={disabled}
                onEdit={() => setEditing({ kind: 'area', baseline: current, area })}
                onMoveUp={() =>
                  submitIntent({
                    collection: 'areas',
                    change: {
                      action: 'reorder_area',
                      area_id: area.area_id,
                      before_area_id: current.areas[index - 1]?.area_id ?? null,
                    },
                  })
                }
                onMoveDown={() =>
                  submitIntent({
                    collection: 'areas',
                    change: {
                      action: 'reorder_area',
                      area_id: area.area_id,
                      before_area_id: current.areas[index + 2]?.area_id ?? null,
                    },
                  })
                }
                onDelete={() =>
                  confirm(
                    '刪除職責',
                    `移除「${area.title ?? '尚未命名的職責'}」。所屬任務會保留並移到未歸屬任務，不會刪除任務內容。`,
                    {
                      collection: 'areas',
                      change: { action: 'delete_area', area_id: area.area_id },
                    },
                  )
                }
              >
                {renderTasks(area.area_id)}
              </AreaSection>
            ))}
            <Paper
              variant="outlined"
              component="section"
              aria-label="未歸屬任務"
              sx={{ p: { xs: 1.5, sm: 2 } }}
            >
              <Stack spacing={2}>
                <Typography component="h3" variant="h6">
                  未歸屬任務
                </Typography>
                {renderTasks(null)}
              </Stack>
            </Paper>
            {(['knowledge', 'skill'] as const).map((kind) => (
              <CapabilitiesSection
                key={kind}
                kind={kind}
                baseline={current}
                disabled={disabled}
                onEdit={setEditing}
                onChange={submitIntent}
                onDelete={(capability) => {
                  const label = capability.kind === 'knowledge' ? '知識' : '技能';
                  confirm(
                    `刪除${label}`,
                    `移除「${capability.name ?? `尚未命名的${label}`}」；已保存的歷史不改寫。`,
                    {
                      collection: 'capabilities',
                      change: {
                        action: 'delete_capability',
                        capability_id: capability.capability_id,
                      },
                    },
                  );
                }}
              />
            ))}
            <CollaboratorsSection
              baseline={current}
              disabled={disabled}
              onEdit={setEditing}
              onChange={submitIntent}
              onDelete={(item) =>
                confirm(
                  '刪除協作對象',
                  `移除「${item.name ?? '名稱尚未提供的協作對象'}」及其協作範圍；已保存的歷史不改寫。`,
                  {
                    collection: 'collaborators',
                    change: {
                      action: 'delete_collaborator',
                      collaborator_id: item.collaborator_id,
                    },
                  },
                )
              }
            />
            <ConditionsSection
              baseline={current}
              disabled={disabled}
              onEdit={setEditing}
              onChange={submitIntent}
              onDelete={(item) =>
                confirm('刪除條件', `移除「${item.text}」；不改變任務內容或已保存的歷史。`, {
                  collection: 'conditions',
                  change: { action: 'delete_condition', condition_id: item.condition_id },
                })
              }
            />
          </>
        )}
      </Stack>
      {editing && (
        <WorkEditDialog
          editing={editing}
          locked={command.locked}
          isSending={command.isSending}
          canRetry={!command.blocked}
          message={command.message}
          pending={command.pending}
          onSubmit={command.send}
          onClose={() => setEditing(null)}
          onReload={command.reload}
        />
      )}
    </section>
  );
}
