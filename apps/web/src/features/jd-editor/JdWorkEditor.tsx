/** Grouped manual editing over one formal revision; all mutations use original command recovery. */
import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Stack, Typography } from '@mui/material';
import { describeReadError } from '../../shared/api/http';
import { AddIcon } from '../../shared/ui/icons';
import { commandFor, isWorkCommand, jdWorkQuery } from './jd-work-api';
import type { WorkIntent } from './jd-work-api';
import { useEditSlot } from './edit-slots-context';
import { InlineEditContext } from './inline-edit-context';
import { draftNoticeOf, statusOf } from './inline-session';
import type { InlineEdit, InlineSaveResult } from './inline-edit-context';
import type { InlineIntent } from './inline-fields';
import { useFold } from './use-fold';
import { useWorkCommand } from './useWorkCommand';
import { WorkDialog } from './WorkDialog';
import type { WorkDialogContent } from './WorkDialog';
import { WorkStatus } from './WorkStatus';
import { AddArea } from './AddArea';
import { AreaSection } from './AreaSection';
import { CapabilitiesSection } from './CapabilitiesSection';
import { CollaboratorsSection } from './CollaboratorsSection';
import { ConditionsSection } from './ConditionsSection';
import { FoldToggle } from './FoldToggle';
import { TaskCard } from './TaskCard';
import { UnassignedSection } from './UnassignedSection';

export function JdWorkEditor({
  jobFileId,
  readOnly = false,
}: {
  jobFileId: string;
  /** A Turn owns the JD: show it, but offer no manual edit (the App also refuses writes). */
  readOnly?: boolean;
}) {
  const work = useQuery(jdWorkQuery(jobFileId));
  // The responsibilities and the unassigned tasks fold together; the sections below them fold on their own.
  const section = useRef<HTMLElement>(null);
  const fold = useFold(section);
  const [dialog, setDialog] = useState<WorkDialogContent | null>(null);
  const [inlineKey, setInlineKey] = useState<string | null>(null);
  // True while an inline editor is on screen; the editor reports its own mount and unmount, so a field
  // that vanished mid-edit cannot leave the page waiting on an editor that no longer exists.
  const [inlineEditorOpen, setInlineEditorOpen] = useState(false);
  const command = useWorkCommand(jobFileId, () => {
    setDialog(null);
    setInlineKey(null);
  });
  const current = work.data;
  // One edit at a time, here and in the basic data: an open editor froze its revision, so any other write
  // would make its save conflict.
  const { heldByAnother } = useEditSlot(inlineEditorOpen || command.locked);
  const disabled =
    command.locked ||
    work.isFetching ||
    work.isError ||
    readOnly ||
    inlineEditorOpen ||
    heldByAnother;
  const status = statusOf(command);
  // What an open draft (dialog or inline) is told; the page banner shows only the command's own message.
  const draftMessage = draftNoticeOf(command.message, readOnly);

  function saveInline(revisionId: string, intent: InlineIntent): InlineSaveResult {
    // The basic data has its own editor and command; a collection field never asks for that.
    if (intent.collection === 'profile') return 'invalid';
    const next = commandFor(revisionId, intent);
    if (!isWorkCommand(next)) return 'invalid';
    void command.send(next);
    return 'submitted';
  }
  const inlineEdit: InlineEdit | null = current
    ? {
        activeKey: inlineKey,
        open: (key) => setInlineKey(key),
        close: () => setInlineKey(null),
        revisionId: current.revision_id,
        save: saveInline,
        canOpen: !disabled,
        canEdit: !command.locked && !readOnly && !work.isError,
        status: { ...status, message: draftMessage },
        setEditorOpen: setInlineEditorOpen,
      }
    : null;

  function submitIntent(intent: WorkIntent): void {
    if (current && !disabled) void command.send(commandFor(current.revision_id, intent));
  }
  function confirm(title: string, description: string, intent: WorkIntent): void {
    if (current)
      setDialog({
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
      <Stack spacing={2}>
        {group.length === 0 && <Typography color="text.secondary">尚無任務</Typography>}
        {group.map((task, index) => (
          <TaskCard
            key={task.task_id}
            task={task}
            index={index}
            group={group}
            baseline={current}
            disabled={disabled}
            onChange={submitIntent}
            onDelete={(target) =>
              confirm(
                '刪除任務',
                `移除「${target.title ?? '尚未命名的任務'}」及其成果、要求；已保存的歷史不改寫。`,
                { collection: 'tasks', change: { action: 'delete_task', task_id: target.task_id } },
              )
            }
            onDeleteDetail={(target, detail, label) =>
              confirm(`刪除${label}`, `移除「${detail.text}」；已保存的歷史不改寫。`, {
                collection: 'tasks',
                change: {
                  action: 'revise_task',
                  task_id: target.task_id,
                  changes: [{ action: 'remove_detail', detail_id: detail.detail_id }],
                },
              })
            }
          />
        ))}
        <div>
          <Button
            size="small"
            className="add-action"
            startIcon={<AddIcon />}
            disabled={disabled}
            onClick={() => setDialog({ kind: 'task', baseline: current, areaId })}
          >
            新增任務
          </Button>
        </div>
      </Stack>
    );
  }

  return (
    <section ref={section} id="jd-work" aria-labelledby="jd-work-heading">
      <InlineEditContext.Provider value={inlineEdit}>
        <Stack spacing={3}>
          <Stack
            direction="row"
            spacing={1}
            className="jd-fold-head"
            sx={{ alignItems: 'center', flexWrap: 'wrap' }}
          >
            <FoldToggle name="職責與任務" fold={fold} />
            <Typography variant="h5" component="h2" id="jd-work-heading">
              JD 職責與任務
            </Typography>
            {current && (
              <Typography variant="body2" color="text.secondary">
                {String(current.areas.length)} 項職責・{String(current.tasks.length)} 項任務
              </Typography>
            )}
          </Stack>
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
          {/* An open dialog or inline editor shows this itself, next to the draft it belongs to. */}
          {!dialog && !inlineEditorOpen && <WorkStatus {...status} />}
          {current && (
            <>
              <div id={fold.bodyId} hidden={!fold.expanded}>
                <Stack spacing={3}>
                  <Typography variant="body2" color="text.secondary" className="jd-edit-hint">
                    點任何文字即可直接修改。
                  </Typography>
                  {current.areas.length === 0 && <p>尚無職責。可先記錄任務，再整理歸屬。</p>}
                  {current.areas.map((area, index) => (
                    <AreaSection
                      key={area.area_id}
                      area={area}
                      isFirst={index === 0}
                      isLast={index === current.areas.length - 1}
                      taskCount={
                        current.tasks.filter((task) => task.area_id === area.area_id).length
                      }
                      disabled={disabled}
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
                  <AddArea />
                  <UnassignedSection
                    taskCount={current.tasks.filter((task) => task.area_id === null).length}
                  >
                    {renderTasks(null)}
                  </UnassignedSection>
                </Stack>
              </div>
              {(['knowledge', 'skill'] as const).map((kind) => (
                <CapabilitiesSection
                  key={kind}
                  kind={kind}
                  baseline={current}
                  disabled={disabled}
                  onCreate={setDialog}
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
                onCreate={setDialog}
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
                onCreate={setDialog}
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
      </InlineEditContext.Provider>
      {dialog && (
        <WorkDialog
          content={dialog}
          locked={command.locked}
          readOnly={readOnly}
          isSending={command.isSending}
          canRetry={!command.blocked}
          message={draftMessage}
          pending={command.pending}
          onSubmit={async (requested) => {
            // Original-command reconciliation remains available; only new changes are blocked.
            if (readOnly && requested !== command.pending) return;
            await command.send(requested);
          }}
          onClose={() => setDialog(null)}
          onReload={command.reload}
        />
      )}
    </section>
  );
}
