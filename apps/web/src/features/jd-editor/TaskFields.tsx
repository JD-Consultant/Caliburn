/** A new task with its first outcomes and requirements; once it exists, each of them is edited in place. */
import { useState } from 'react';
import type { RefObject } from 'react';
import { Button, MenuItem, Stack, TextField, Typography } from '@mui/material';
import type { JdWorkView } from '../../shared/api/generated/jd-work-view';
import { isEditJdTasksRequest } from '../../shared/api/validation';
import { AddIcon } from '../../shared/ui/icons';
import { UNASSIGNED, areaChoices } from './area-choice';
import type { WorkCommand } from './jd-work-api';

/** A row typed in this form; `key` only tells rows apart while editing, it never becomes a server ID. */
interface DetailDraft {
  key: string;
  text: string;
}

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
        <Stack key={row.key} direction="row" spacing={1} useFlexGap sx={{ alignItems: 'start' }}>
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
          {/* Add another / Remove are both secondary buttons (MoJ "Add another"). 32px = label 20 +
              gap 6 + half the 12px by which the 40px field is taller than the 28px button. */}
          <Button
            variant="outlined"
            size="small"
            disabled={disabled}
            aria-label={`移除${label} ${String(index + 1)}`}
            onClick={() => onChange(rows.filter((item) => item.key !== row.key))}
            sx={{ mt: '32px', flex: 'none' }}
          >
            移除
          </Button>
        </Stack>
      ))}
      <Button
        variant="outlined"
        size="small"
        disabled={disabled}
        startIcon={<AddIcon />}
        onClick={() => onChange([...rows, { key: crypto.randomUUID(), text: '' }])}
        sx={{ alignSelf: 'flex-start' }}
      >
        新增{label}
      </Button>
    </Stack>
  );
}

interface Props {
  baseline: JdWorkView;
  /** The responsibility the task was added from; null starts it unassigned. */
  areaId: string | null;
  titleInput: RefObject<HTMLInputElement | null>;
  disabled: boolean;
  onSubmit: (command: WorkCommand) => Promise<void>;
  onError: (message: string) => void;
}

export function TaskFields({ baseline, areaId, titleInput, disabled, onSubmit, onError }: Props) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [selectedArea, setSelectedArea] = useState(areaId ?? UNASSIGNED);
  const [outcomes, setOutcomes] = useState<DetailDraft[]>([]);
  const [requirements, setRequirements] = useState<DetailDraft[]>([]);
  function submit(): void {
    const request = {
      command_id: crypto.randomUUID(),
      expected_revision_id: baseline.revision_id,
      change: {
        action: 'create_task',
        area_id: selectedArea === UNASSIGNED ? null : selectedArea,
        title: title || null,
        description: description || null,
        outcomes: outcomes.map((row) => row.text),
        requirements: requirements.map((row) => row.text),
      },
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
        >
          {areaChoices(baseline.areas).map((choice) => (
            <MenuItem key={choice.value} value={choice.value}>
              {choice.label}
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
        <Typography variant="body2" color="text.secondary">
          工作成果與工作要求是兩組獨立項目，不需一一配對。
        </Typography>
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
