/** A new job-wide condition: the category is chosen explicitly, never guessed, and never fills task requirements. */
import { useState } from 'react';
import type { RefObject } from 'react';
import { MenuItem, Stack, TextField } from '@mui/material';
import { isEditJdConditionsRequest } from '../../shared/api/validation';
import type { WorkCommand } from './jd-work-api';
import { conditionLabels } from './condition-labels';

interface Props {
  revisionId: string;
  titleInput: RefObject<HTMLInputElement | null>;
  disabled: boolean;
  onSubmit: (command: WorkCommand) => Promise<void>;
  onError: (message: string) => void;
}

export function ConditionFields({ revisionId, titleInput, disabled, onSubmit, onError }: Props) {
  const [kind, setKind] = useState('');
  const [text, setText] = useState('');
  function submit(): void {
    const request = {
      command_id: crypto.randomUUID(),
      expected_revision_id: revisionId,
      change: { action: 'create_condition', kind, text },
    };
    if (!isEditJdConditionsRequest(request)) {
      onError('請選擇條件分類並填寫內容，不能只填空白。');
      return;
    }
    void onSubmit({ collection: 'conditions', request });
  }
  return (
    <form
      id="jd-condition-form"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <Stack spacing={2} sx={{ pt: 1 }}>
        <TextField
          label="條件分類"
          select
          value={kind}
          disabled={disabled}
          onChange={(event) => setKind(event.target.value)}
        >
          {Object.entries(conditionLabels).map(([value, label]) => (
            <MenuItem key={value} value={value}>
              {label}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          inputRef={titleInput}
          label="條件內容"
          value={text}
          disabled={disabled}
          multiline
          minRows={4}
          onChange={(event) => setText(event.target.value)}
          helperText="只填已知且適用於整體職務的條件；特定任務的限制留在該任務。"
        />
        <p>此處不會自動加入每項任務的要求。</p>
      </Stack>
    </form>
  );
}
