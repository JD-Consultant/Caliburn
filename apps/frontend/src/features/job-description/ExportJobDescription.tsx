import { useState } from 'react';
import { Alert } from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { HttpError, requestBlob } from '../../shared/api/http';
import { IconAction } from '../../shared/ui/IconAction';
import { DownloadIcon } from '../../shared/ui/icons';
import { jobDescriptionPath } from './api-transport';
import { useJobDescriptionEditor } from './editing/useJobDescriptionEditor';

export function ExportJobDescription() {
  const editor = useJobDescriptionEditor();
  const [notice, setNotice] = useState<string | null>(null);
  const download = useMutation({
    mutationFn: () =>
      requestBlob(
        jobDescriptionPath(
          editor.jobDescription.workspace_id,
          editor.jobDescription.job_description_id,
        ) + '/export.pdf',
        {},
      ),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'job-description.pdf';
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    },
  });
  return (
    <>
      <IconAction
        label="下載 PDF"
        disabled={download.isPending}
        onClick={() => {
          void editor.waitForWrites().then((ready) => {
            if (!ready) {
              setNotice('請先處理尚未保存的輸入，再下載 PDF。');
              return;
            }
            setNotice(null);
            download.mutate();
          });
        }}
      >
        <DownloadIcon />
      </IconAction>
      {notice && <Alert severity="info">{notice}</Alert>}
      {download.isError && (
        <Alert severity="error">
          {download.error instanceof HttpError && download.error.status === 503
            ? 'PDF 列印目前無法使用，可能尚未設定字型或瀏覽器。請稍後重試。'
            : download.error instanceof HttpError && download.error.status === 504
              ? 'PDF 列印逾時，請稍後重試。'
              : '無法下載 PDF，請檢查連線後重試。'}
        </Alert>
      )}
    </>
  );
}
