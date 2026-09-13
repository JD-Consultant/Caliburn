'use client';
import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Paper, Stack, Typography } from '@mui/material';
import { JdApi } from '../lib/api';
import { projectView } from '../lib/view';
import type { JdView } from '../lib/view';
import type { ChangeReadPage, RevisionRecord } from '../../../src/jd_relational/generated/jd-read';
import { message } from './Workspace';
import ChangeDetails from './ChangeDetails';

export default function HistoryPanel({ api, documentId, revisionRef, selectedChange }: { api: JdApi; documentId: string; revisionRef: string | null;
  selectedChange?: { ref: string; sequence: number } | null }) {
  const [history, setHistory] = useState<RevisionRecord[]>([]);
  const [selection, setSelection] = useState<{ change: ChangeReadPage; before: JdView; after: JdView } | null>(null);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const selectionGeneration = useRef(0);
  useEffect(() => () => { selectionGeneration.current++; }, [api, documentId]);
  useEffect(() => { if (selectedChange) void show(selectedChange.ref); }, [selectedChange, api, documentId]);
  useEffect(() => { let live = true;
    void api.read(documentId, { view: 'history', target_ref: null, cursor: null }).then(page => {
      if (live) setHistory(page.records.filter((item): item is RevisionRecord => item.type === 'revision'));
    }).catch(error => { if (live) setError(message(error)); });
    return () => { live = false; };
  }, [api, documentId, revisionRef]);
  async function show(ref: string) {
    const generation = ++selectionGeneration.current;
    setBusy(true); setError(''); setSelection(null);
    try {
      const change = await api.changes(documentId, ref);
      const [before, after] = await Promise.all([change.base_revision_ref, change.result_revision_ref].map(target_ref =>
        api.read(documentId, { view: 'history', target_ref, cursor: null }).then(projectView)));
      if (selectionGeneration.current === generation) setSelection({ change, before, after });
    } catch (error) { if (selectionGeneration.current === generation) setError(message(error)); }
    finally { if (selectionGeneration.current === generation) setBusy(false); }
  }
  return <Paper variant="outlined" sx={{ p: 3, mb: 3 }}><Typography variant="h6">改動與歷史</Typography>
    <Typography color="text.secondary" sx={{ my: 1 }}>查看每次實際保存的差異。收起或查看歷史，都不會更動目前 JD。</Typography>
    {error && <Alert severity="warning">{error}</Alert>}
    <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>{history.map(item => <Button key={item.revision_ref} disabled={busy || !item.change_ref}
      onClick={() => item.change_ref && void show(item.change_ref)}>{`第 ${item.revision_number} 版 · ${item.origin === 'ai' ? 'AI' : item.origin === 'manual' ? '手動' : '建立'} · ${new Date(item.created_at).toLocaleString('zh-TW')}`}</Button>)}</Stack>
    {busy && <Typography role="status">讀取這次完整差異…</Typography>}
    {selection && <ChangeDetails records={selection.change.records} before={selection.before} after={selection.after} />}
  </Paper>;
}
