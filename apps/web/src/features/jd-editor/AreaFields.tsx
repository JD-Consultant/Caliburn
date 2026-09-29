import { useState } from 'react';
import type { RefObject } from 'react';
import { Stack, TextField } from '@mui/material';
import type { Area } from '../../shared/api/generated/jd-work-view';
import { isEditJdAreasRequest } from '../../shared/api/validation';
import type { WorkCommand } from './jd-work-api';

interface Props {
  revisionId: string;
  area: Area | undefined;
  titleInput: RefObject<HTMLInputElement | null>;
  disabled: boolean;
  onSubmit: (command: WorkCommand) => Promise<void>;
  onError: (message: string) => void;
}

export function AreaFields({ revisionId, area, titleInput, disabled, onSubmit, onError }: Props) {
  const [title, setTitle] = useState(area?.title ?? '');
  const [scope, setScope] = useState(area?.scope_text ?? '');
  function submit(): void {
    const values = { title: title || null, scope_text: scope || null };
    const changes = (['title', 'scope_text'] as const)
      .filter((field) => values[field] !== area?.[field])
      .map((field) => ({ field, value: values[field] }));
    if (area && changes.length === 0) {
      onError('沒有修改任何欄位，尚未送出。');
      return;
    }
    const request = {
      command_id: crypto.randomUUID(),
      expected_revision_id: revisionId,
      change: area
        ? { action: 'revise_area', area_id: area.area_id, changes }
        : { action: 'create_area', ...values },
    };
    if (!isEditJdAreasRequest(request)) {
      onError('職責名稱或範圍至少填一項，不能只填空白。');
      return;
    }
    void onSubmit({ collection: 'areas', request });
  }
  return (
    <form
      id="jd-area-form"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <Stack spacing={2} sx={{ pt: 1 }}>
        <TextField
          inputRef={titleInput}
          label="職責名稱"
          value={title}
          disabled={disabled}
          onChange={(event) => setTitle(event.target.value)}
        />
        <TextField
          label="職責範圍"
          value={scope}
          disabled={disabled}
          multiline
          minRows={3}
          onChange={(event) => setScope(event.target.value)}
          helperText="說明這類工作的責任、邊界與目的。未知可留空，不需自行猜測。"
        />
      </Stack>
    </form>
  );
}
