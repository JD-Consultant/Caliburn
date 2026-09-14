'use client';
import { useEffect, useState } from 'react';
import { Alert, Box, Button, Paper, Stack, Typography } from '@mui/material';
import { runChangeSummary, undoOffer, type LoadedRunChange } from '../lib/run-changes';
import ChangeDetails from './ChangeDetails';

export default function RunChangesPanel({ selection, loading, error, currentRevisionRef, onRetry, onUndo, undoing, onHold }: {
  selection: LoadedRunChange | null; loading: boolean; error: string | null; currentRevisionRef: string | null; onRetry: () => void;
  onUndo?: (runId: string, expectedResultRef: string) => void; undoing?: boolean;
  onHold?: (holding: boolean) => void;
}) {
  const page = selection?.page;
  const [confirming, setConfirming] = useState(false);
  useEffect(() => { onHold?.(confirming); }, [confirming, onHold]);
  useEffect(() => () => onHold?.(false), [onHold]);
  const offer = page ? undoOffer(page, currentRevisionRef) : null;
  return <Paper component="section" aria-label="本輪 JD 改動" variant="outlined" sx={{ p: 3, mb: 3 }}>
    <Typography variant="h6">本輪 JD 改動</Typography>
    {loading && <Typography role="status">讀取這輪已保存的修改…</Typography>}
    {error && <Alert severity="warning" sx={{ mt: 1 }} action={<Button onClick={onRetry}>重新查看改動</Button>}>{error}</Alert>}
    {page && <>
      <Typography sx={{ mt: 1 }}>{runChangeSummary(page)}</Typography>
      {page.captured_operation_count > 0 && <Typography variant="body2">這次比較涵蓋 {page.captured_operation_count} 次已保存修改。</Typography>}
      {page.effects_state === 'unconfirmed' && <Alert severity="info" sx={{ mt: 1 }}>本輪修改結果尚未全部確認；以下僅是目前已確認範圍，不代表整輪完成。</Alert>}
      {page.result_revision_ref && currentRevisionRef && page.result_revision_ref !== currentRevisionRef &&
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>這輪當時的改動；目前稿版本不同，已停用目前欄位標記。歷史仍可查看。</Typography>}
      {page.continuity === 'discontinuous' && <Typography variant="body2" sx={{ mt: 1 }}>左側「查看第幾次實際改動」保留各次確切內容。</Typography>}
      {selection.before && selection.after && <Box><ChangeDetails records={page.records} before={selection.before} after={selection.after} compact idPrefix="jd-run-change" /></Box>}
      {onUndo && offer && (offer.available
        ? <Stack sx={{ mt: 2, gap: 1 }}>
            {!confirming
              ? <Box><Button variant="outlined" disabled={undoing} onClick={() => setConfirming(true)}>撤回這輪 JD 改動</Button></Box>
              : <>
                  <Alert severity="info">一次取回這輪對 JD 的全部改動，不是只取消最後一項。這只會改 JD：這輪的對話、工作理解與案例都會保留，歷史也保留這輪的紀錄。</Alert>
                  <Stack direction="row" sx={{ gap: 1 }}>
                    <Button variant="contained" disabled={undoing}
                      onClick={() => onUndo(offer.runId, offer.expectedResultRef)}>確認撤回</Button>
                    <Button disabled={undoing} onClick={() => setConfirming(false)}>取消</Button>
                  </Stack>
                </>}
          </Stack>
        : <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>{offer.reason}</Typography>)}
    </>}
  </Paper>;
}
