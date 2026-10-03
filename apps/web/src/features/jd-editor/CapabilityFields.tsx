/** A new shared knowledge/skill definition; task usage is managed separately, and its text is edited in place. */
import { useState } from 'react';
import type { RefObject } from 'react';
import { Stack, TextField } from '@mui/material';
import type { Capability } from '../../shared/api/generated/jd-work-view';
import { isEditJdCapabilitiesRequest } from '../../shared/api/validation';
import type { WorkCommand } from './jd-work-api';

interface Props {
  revisionId: string;
  kind: Capability['kind'];
  titleInput: RefObject<HTMLInputElement | null>;
  disabled: boolean;
  onSubmit: (command: WorkCommand) => Promise<void>;
  onError: (message: string) => void;
}

export function CapabilityFields({
  revisionId,
  kind,
  titleInput,
  disabled,
  onSubmit,
  onError,
}: Props) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const label = kind === 'knowledge' ? '知識' : '技能';
  function submit(): void {
    const request = {
      command_id: crypto.randomUUID(),
      expected_revision_id: revisionId,
      change: {
        action: 'create_capability',
        kind,
        name: name || null,
        description: description || null,
      },
    };
    if (!isEditJdCapabilitiesRequest(request)) {
      onError(`${label}名稱或說明至少填一項，不能只填空白。`);
      return;
    }
    void onSubmit({ collection: 'capabilities', request });
  }
  return (
    <form
      id="jd-capability-form"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <Stack spacing={2} sx={{ pt: 1 }}>
        <TextField
          inputRef={titleInput}
          label={`${label}名稱`}
          value={name}
          disabled={disabled}
          onChange={(event) => setName(event.target.value)}
        />
        <TextField
          label={`${label}說明`}
          value={description}
          disabled={disabled}
          multiline
          minRows={3}
          onChange={(event) => setDescription(event.target.value)}
          helperText={
            kind === 'knowledge'
              ? '完成工作需要理解的概念、原理或規範；只記錄已知的範圍。'
              : '運用方法完成工作或解決問題的能力；不要只把任務換句話說。'
          }
        />
      </Stack>
    </form>
  );
}
