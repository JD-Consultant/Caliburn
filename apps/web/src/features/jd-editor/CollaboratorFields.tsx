/** A new collaborator: the name may stay empty, a name is never invented. */
import { useState } from 'react';
import type { RefObject } from 'react';
import { Stack, TextField } from '@mui/material';
import { isEditJdCollaboratorsRequest } from '../../shared/api/validation';
import type { WorkCommand } from './jd-work-api';

interface Props {
  revisionId: string;
  titleInput: RefObject<HTMLInputElement | null>;
  disabled: boolean;
  onSubmit: (command: WorkCommand) => Promise<void>;
  onError: (message: string) => void;
}

export function CollaboratorFields({ revisionId, titleInput, disabled, onSubmit, onError }: Props) {
  const [name, setName] = useState('');
  const [scopeText, setScopeText] = useState('');
  function submit(): void {
    const request = {
      command_id: crypto.randomUUID(),
      expected_revision_id: revisionId,
      change: {
        action: 'create_collaborator',
        name: name || null,
        scope_text: scopeText || null,
      },
    };
    if (!isEditJdCollaboratorsRequest(request)) {
      onError('協作對象名稱或範圍至少填一項，不能只填空白。');
      return;
    }
    void onSubmit({ collection: 'collaborators', request });
  }
  return (
    <form
      id="jd-collaborator-form"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <Stack spacing={2} sx={{ pt: 1 }}>
        <TextField
          inputRef={titleInput}
          label="協作對象名稱"
          value={name}
          disabled={disabled}
          onChange={(event) => setName(event.target.value)}
          helperText="填已知的角色、部門或單位；名稱未知可先留空。"
        />
        <TextField
          label="協作範圍"
          value={scopeText}
          disabled={disabled}
          multiline
          minRows={3}
          onChange={(event) => setScopeText(event.target.value)}
          helperText="交接或配合哪些事項、各自負責到哪裡；協作不表示主管關係。"
        />
      </Stack>
    </form>
  );
}
