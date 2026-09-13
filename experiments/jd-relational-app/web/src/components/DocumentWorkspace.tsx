'use client';
import { useEffect, useRef, useState } from 'react';
import { Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  Divider, Paper, Stack, Typography } from '@mui/material';
import { JdApi } from '../lib/api';
import { JdSession, emptySession } from '../lib/session';
import type { JsonValue } from '../lib/drafts';
import { fieldLabels } from '../lib/view';
import type { CatalogDocument } from '../../../src/jd_relational/generated/jd-catalog-http';
import JdEditor from './JdEditor';
import HistoryPanel from './HistoryPanel';

export default function DocumentWorkspace({ api, document, onSafeToLeave }: {
  api: JdApi; document: CatalogDocument; onSafeToLeave: (value: boolean) => void;
}) {
  const [snapshot, setSnapshot] = useState(emptySession);
  const session = useRef<JdSession | null>(null);
  const [history, setHistory] = useState(false);
  const [restoreChoice, setRestoreChoice] = useState<'continue' | 'discard' | null>(null);
  const [restoreBusy, setRestoreBusy] = useState(false);
  const previousArchive = useRef(document.archived);
  useEffect(() => {
    const active = new JdSession(api, document.document_id, setSnapshot); session.current = active;
    void active.start();
    return () => { session.current = null; void active.dispose(); };
  }, [api, document.document_id]);
  useEffect(() => {
    if (previousArchive.current !== document.archived) {
      previousArchive.current = document.archived; void session.current?.refreshStatus();
    }
  }, [document.archived]);
  useEffect(() => {
    onSafeToLeave(!snapshot.dirty && !snapshot.submitting);
    if (!snapshot.dirty && !snapshot.submitting) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [snapshot.dirty, snapshot.submitting, onSafeToLeave]);

  const restore = async () => {
    setRestoreBusy(true);
    try { await session.current?.resume(restoreChoice === 'discard'); setRestoreChoice(null); }
    finally { setRestoreBusy(false); }
  };
  // Only the redundant clean-archive notice is replaced by the archive explanation.
  const archiveNoticeOnly = document.archived && !snapshot.dirty && !snapshot.needsReview && !snapshot.row?.submission
    && snapshot.error === '服務目前暫停編輯，請稍後再查看；尚未保存的內容繼續保留。';
  return <div className="work-grid"><Paper sx={{ p: 3, alignSelf: 'start' }}>
    <Chip label="你的工作顧問" size="small" variant="outlined" />
    <Typography variant="h6" sx={{ mt: 2 }}>從實際工作，逐步整理。</Typography>
    <Typography color="text.secondary" sx={{ mt: 2 }}>你可以先寫下平常負責什麼，再加入成果、執行要求，以及所需的知識與技能。</Typography>
    <Divider sx={{ my: 3 }} /><Alert severity="info" icon={false}>AI 訪談正在接合中。目前可以手動完整建立與管理這份 JD。</Alert>
    <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>不用一次填完。只填已知內容，日後可以繼續補充與更正。</Typography>
  </Paper><Box sx={{ minWidth: 0 }}>
    <Stack direction="row" sx={{ mb: 2, gap: 2, alignItems: 'center' }}>
      <Typography variant="h5" component="h1" sx={{ flex: 1, overflowWrap: 'anywhere' }}>{document.title}</Typography>
      <Chip label={document.archived ? '已封存' : snapshot.status} color={snapshot.dirty ? 'warning' : 'default'} variant="outlined" aria-live="polite" />
      <Button onClick={() => setHistory(value => !value)}>{history ? '收起歷史' : '改動與歷史'}</Button>
    </Stack>
    {document.archived && <Alert severity="info" sx={{ mb: 2 }}>這份文件已封存，恢復後可以繼續編輯。</Alert>}
    {snapshot.error && !archiveNoticeOnly && <Alert severity="warning" sx={{ mb: 2 }} action={<Button disabled={snapshot.submitting} onClick={() => void session.current?.refreshStatus()}>重新查看狀態</Button>}>{snapshot.error}</Alert>}
    {snapshot.row?.submission && <Alert severity="warning" sx={{ mb: 2 }}>
      原操作尚待確認，暫停新的保存。內容與原操作都保留在此瀏覽器。
      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
        <Button disabled={snapshot.submitting} onClick={() => void session.current?.reconcile()}>查回原保存</Button>
        <Button disabled={snapshot.submitting} onClick={() => void session.current?.reconcile(true)}>繼續原操作</Button>
      </Stack>
    </Alert>}
    {snapshot.needsReview && !snapshot.row?.submission && <Paper variant="outlined" sx={{ p: 3, mb: 3, borderColor: 'warning.main' }}>
      <Typography variant="h6">找回尚未完成的內容</Typography>
      <Typography color="text.secondary" sx={{ my: 1 }}>下方顯示資料庫目前內容。請先比較找回的文字，再決定是否繼續編輯。</Typography>
      {Object.entries(snapshot.recoveryFields).map(([key, candidate]) => <Box key={key} sx={{ py: 2, borderTop: '1px solid #eee' }}>
        <Typography sx={{ fontWeight: 700 }}>{fieldLabels[candidate.fieldName as keyof typeof fieldLabels] ?? candidate.fieldName}</Typography>
        <Typography variant="caption">目前已保存</Typography><Typography className="jd-text">{snapshot.view?.fields.find(item => item.key === key)?.value ?? '（尚無內容或項目已移除）'}</Typography>
        <Typography variant="caption">找回的文字</Typography><Typography className="jd-text">{candidate.text ?? '（清空）'}</Typography>
      </Box>)}
      {!!Object.keys(snapshot.row?.forms ?? {}).length && <Typography sx={{ my: 2 }}>另有尚未完成的管理表單，選擇繼續後可查看。</Typography>}
      <Stack direction="row" spacing={1}><Button variant="contained" onClick={() => setRestoreChoice('continue')}>使用找回內容繼續</Button>
        <Button color="inherit" onClick={() => setRestoreChoice('discard')}>捨棄未提交內容</Button></Stack>
    </Paper>}
    {history && <HistoryPanel api={api} documentId={document.document_id} revisionRef={snapshot.view?.revisionRef ?? null} />}
    {snapshot.loading ? <CircularProgress aria-label="讀取職務說明書" /> : snapshot.view && <JdEditor view={snapshot.view}
      disabled={document.archived || snapshot.readOnly} commandsDisabled={snapshot.submitting || !!Object.keys(snapshot.row?.fields ?? {}).length}
      values={snapshot.values} onField={(field, text) => session.current?.edit(field, text)}
      onComposition={active => session.current?.composition(active)} form={snapshot.form}
      onFormChange={value => session.current?.form(value as JsonValue | null)}
      onCommand={async (command, options) => { await session.current?.command(command, options); }} />}
  </Box><Dialog open={restoreChoice !== null} onClose={() => { if (!restoreBusy) setRestoreChoice(null); }}>
    <DialogTitle>{restoreChoice === 'discard' ? '捨棄找回的內容？' : '繼續這些修改？'}</DialogTitle>
    <DialogContent><Typography>{restoreChoice === 'discard' ? '只會捨棄尚未提交的文字與表單。資料庫中的 JD 與歷史保持保存。' :
      '找回的文字會套用至目前對應欄位，並開始自動保存。若目前內容已有變更，請先確認上述比較。未完成表單仍需你完成操作。'}</Typography></DialogContent>
    <DialogActions><Button disabled={restoreBusy} onClick={() => setRestoreChoice(null)}>返回比較</Button><Button disabled={restoreBusy} onClick={() => void restore()}>確認</Button></DialogActions>
  </Dialog></div>;
}
