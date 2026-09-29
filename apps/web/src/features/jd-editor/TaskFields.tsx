import { useState } from 'react';
import type { RefObject } from 'react';
import { Button, MenuItem, Stack, TextField, Typography } from '@mui/material';
import type { TaskChange } from '../../shared/api/generated/edit-jd-tasks-request';
import type { JdWorkView, WorkTask } from '../../shared/api/generated/jd-work-view';
import { isEditJdTasksRequest } from '../../shared/api/validation';
import type { WorkCommand } from './jd-work-api';
import { detailChanges, makeDetailDraft } from './task-draft';
import type { DetailDraft } from './task-draft';

function DetailFields({
  label,
  rows,
  onChange,
  disabled,
}: {
  label: string;
  rows: DetailDraft[];
  onChange: (rows: DetailDraft[]) => void;
  disabled: boolean;
}) {
  return (
    <Stack spacing={1}>
      <Typography component="h3" variant="subtitle1">
        {label}
      </Typography>
      {rows.map((row, index) => (
        <Stack key={row.key} direction="row" spacing={1} sx={{ alignItems: 'start' }}>
          <TextField
            fullWidth
            multiline
            label={`${label} ${String(index + 1)}`}
            value={row.text}
            disabled={disabled}
            onChange={(event) =>
              onChange(
                rows.map((item) =>
                  item.key === row.key ? { ...item, text: event.target.value } : item,
                ),
              )
            }
          />
          <Button
            disabled={disabled}
            aria-label={`移除${label} ${String(index + 1)}`}
            onClick={() => onChange(rows.filter((item) => item.key !== row.key))}
          >
            移除
          </Button>
        </Stack>
      ))}
      <Button
        disabled={disabled}
        onClick={() => onChange([...rows, { key: crypto.randomUUID(), text: '' }])}
      >
        新增{label}
      </Button>
    </Stack>
  );
}

interface Props {
  baseline: JdWorkView;
  task: WorkTask | undefined;
  areaId: string | null;
  titleInput: RefObject<HTMLInputElement | null>;
  disabled: boolean;
  onSubmit: (command: WorkCommand) => Promise<void>;
  onError: (message: string) => void;
}

export function TaskFields({
  baseline,
  task,
  areaId,
  titleInput,
  disabled,
  onSubmit,
  onError,
}: Props) {
  const [title, setTitle] = useState(task?.title ?? '');
  const [description, setDescription] = useState(task?.description ?? '');
  const [selectedArea, setSelectedArea] = useState(areaId ?? 'unassigned');
  const [outcomes, setOutcomes] = useState(() => makeDetailDraft(task?.outcomes ?? []));
  const [requirements, setRequirements] = useState(() => makeDetailDraft(task?.requirements ?? []));
  function submit(): void {
    const values = { title: title || null, description: description || null };
    const changes: TaskChange[] = (['title', 'description'] as const)
      .filter((field) => values[field] !== task?.[field])
      .map((field) => ({ action: 'set_field', field, value: values[field] }));
    changes.push(
      ...detailChanges(task?.outcomes ?? [], outcomes, 'outcome'),
      ...detailChanges(task?.requirements ?? [], requirements, 'requirement'),
    );
    const destination = selectedArea === 'unassigned' ? null : selectedArea;
    if (task && changes.length === 0 && task.area_id === destination) {
      onError('沒有修改任何欄位，尚未送出。');
      return;
    }
    let change: unknown;
    if (!task) {
      change = {
        action: 'create_task',
        area_id: destination,
        ...values,
        outcomes: outcomes.map((row) => row.text),
        requirements: requirements.map((row) => row.text),
      };
    } else if (destination !== task.area_id) {
      change = {
        action: 'move_task',
        task_id: task.task_id,
        area_id: destination,
        before_task_id: null,
        changes,
      };
    } else {
      change = { action: 'revise_task', task_id: task.task_id, changes };
    }
    const request = {
      command_id: crypto.randomUUID(),
      expected_revision_id: baseline.revision_id,
      change,
    };
    if (!isEditJdTasksRequest(request)) {
      onError('任務名稱或工作內容至少填一項；成果與要求不能留空白，未提供的項目請移除。');
      return;
    }
    void onSubmit({ collection: 'tasks', request });
  }
  return (
    <form
      id="jd-task-form"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <Stack spacing={2} sx={{ pt: 1 }}>
        <TextField
          select
          label="所屬職責"
          value={selectedArea}
          disabled={disabled}
          onChange={(event) => setSelectedArea(event.target.value)}
          helperText="移動會保留任務內容，放在目的職責末尾；需要的文字調整可一併保存。"
        >
          <MenuItem value="unassigned">未歸屬任務</MenuItem>
          {baseline.areas.map((area) => (
            <MenuItem key={area.area_id} value={area.area_id}>
              {area.title ?? area.scope_text}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          inputRef={titleInput}
          label="任務名稱"
          value={title}
          disabled={disabled}
          onChange={(event) => setTitle(event.target.value)}
        />
        <TextField
          multiline
          minRows={3}
          label="工作內容"
          value={description}
          disabled={disabled}
          onChange={(event) => setDescription(event.target.value)}
          helperText="描述實際做什麼、如何完成及適用情況。未知可留空。"
        />
        <Typography>工作成果與工作要求是兩組獨立項目，不需一一配對。</Typography>
        <DetailFields label="工作成果" rows={outcomes} onChange={setOutcomes} disabled={disabled} />
        <DetailFields
          label="工作要求"
          rows={requirements}
          onChange={setRequirements}
          disabled={disabled}
        />
      </Stack>
    </form>
  );
}
