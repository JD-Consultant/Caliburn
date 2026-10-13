/** Original arguments and outputs remain plain text, separate from formal JD effects. */
import { useId, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
} from '@mui/material';
import { describeReadError } from '../../shared/api/http';
import { turnToolsQuery } from './turn-tools-api';

export function TurnTools({ jobFileId, executionId }: { jobFileId: string; executionId: string }) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  return (
    <>
      <Button size="small" onClick={() => setOpen(true)}>
        查看這輪工具紀錄
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        aria-labelledby={titleId}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle id={titleId}>這輪工具紀錄</DialogTitle>
        <DialogContent>
          {open && (
            <ToolCalls
              key={`${jobFileId}:${executionId}`}
              jobFileId={jobFileId}
              executionId={executionId}
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setOpen(false)}>
            關閉
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

function ToolCalls({ jobFileId, executionId }: { jobFileId: string; executionId: string }) {
  const query = useQuery(turnToolsQuery(jobFileId, executionId));
  return (
    <>
      <Button
        size="small"
        aria-disabled={query.isFetching}
        onClick={() => {
          if (!query.isFetching) void query.refetch();
        }}
      >
        重新讀取工具紀錄
      </Button>
      {query.isPending ? (
        <p role="status">正在讀取這輪工具紀錄…</p>
      ) : query.isError ? (
        <Alert severity="error">{describeReadError(query.error)}</Alert>
      ) : (
        <>
          <p>
            依這輪保存的呼叫順序顯示。工具有回傳不代表修改已正式採用；JD 的結果可由「查看這輪 JD
            變更」核對。
          </p>
          {query.data.calls.length === 0 ? (
            <p>這輪沒有已保存的工具呼叫。</p>
          ) : (
            <Box component="ol" sx={{ pl: 3 }}>
              {query.data.calls.map((call) => (
                <Box component="li" key={`${call.request_id}:${call.call_id}`} sx={{ mb: 2 }}>
                  <Box component="details">
                    <Box
                      component="summary"
                      sx={{ cursor: 'pointer', overflowWrap: 'anywhere', py: 1 }}
                    >
                      <span>{call.name}</span>{' '}
                      <Chip
                        size="small"
                        variant="outlined"
                        label={call.result_state === 'recorded' ? '已保存回傳' : '回傳未保存'}
                      />
                    </Box>
                    <h4>參數</h4>
                    <OriginalText text={call.arguments} />
                    <h4>回傳</h4>
                    {call.result_state === 'recorded' && call.output !== null ? (
                      <OriginalText text={call.output} />
                    ) : (
                      <p>尚未保存回傳，不能據此判定工具沒有執行。</p>
                    )}
                  </Box>
                </Box>
              ))}
            </Box>
          )}
        </>
      )}
    </>
  );
}

function OriginalText({ text }: { text: string }) {
  return (
    <Box
      component="pre"
      sx={{
        m: 0,
        p: 1.5,
        bgcolor: 'action.hover',
        whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere',
        maxHeight: 360,
        overflowY: 'auto',
        fontSize: '0.8125rem',
      }}
    >
      {text}
    </Box>
  );
}
