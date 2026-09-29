/** Shared knowledge/skill text is edited once; task usage is managed separately. */
import { useState } from 'react';
import type { RefObject } from 'react';
import { Stack, TextField } from '@mui/material';
import type { Capability } from '../../shared/api/generated/jd-work-view';
import { isEditJdCapabilitiesRequest } from '../../shared/api/validation';
import type { WorkCommand } from './jd-work-api';

interface Props {
  revisionId: string;
  kind: Capability['kind'];
  capability: Capability | undefined;
  titleInput: RefObject<HTMLInputElement | null>;
  disabled: boolean;
  onSubmit: (command: WorkCommand) => Promise<void>;
  onError: (message: string) => void;
}

export function CapabilityFields({
  revisionId,
  kind,
  capability,
  titleInput,
  disabled,
  onSubmit,
  onError,
}: Props) {
  const [name, setName] = useState(capability?.name ?? '');
  const [description, setDescription] = useState(capability?.description ?? '');
  const label = kind === 'knowledge' ? '知識' : '技能';
  function submit(): void {
    const values = { name: name || null, description: description || null };
    const changes = (['name', 'description'] as const)
      .filter((field) => values[field] !== capability?.[field])
      .map((field) => ({ field, value: values[field] }));
    if (capability && changes.length === 0) {
      onError('沒有修改任何欄位，尚未送出。');
      return;
    }
    const request = {
      command_id: crypto.randomUUID(),
      expected_revision_id: revisionId,
      change: capability
        ? { action: 'revise_capability', capability_id: capability.capability_id, changes }
        : { action: 'create_capability', kind, ...values },
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
        <p>修改共用定義後，所有使用此項的任務都會顯示新版；不改變使用關係。</p>
      </Stack>
    </form>
  );
}
