import { Button } from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useJobDescriptionEditor } from './useJobDescriptionEditor';

export function EditorNavigation() {
  const editor = useJobDescriptionEditor();
  const navigate = useNavigate();
  const [notice, setNotice] = useState(false);
  return (
    <div className="jd-editor-navigation">
      <Button
        type="button"
        size="small"
        onClick={() => {
          void editor.waitForWrites().then((ready) => {
            if (ready)
              void navigate(
                `/workspaces/${editor.jobDescription.workspace_id}/jd/history`,
              );
            else setNotice(true);
          });
        }}
      >
        版本歷史
      </Button>
      {notice && <p role="status">請先處理保留的輸入，再開啟歷史。</p>}
    </div>
  );
}
