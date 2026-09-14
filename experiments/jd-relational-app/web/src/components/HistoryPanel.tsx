'use client';
import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Paper, Stack, Typography } from '@mui/material';
import { JdApi } from '../lib/api';
import { projectView } from '../lib/view';
import type { JdView } from '../lib/view';
import type { ChangeReadPage, RestorePreviewPage, RevisionRecord } from '../../../src/jd_relational/generated/jd-read';
import { message } from './Workspace';
import ChangeDetails from './ChangeDetails';

export default function HistoryPanel({ api, documentId, revisionRef, selectedChange, onRestored, onHold }: { api: JdApi; documentId: string; revisionRef: string | null;
  selectedChange?: { ref: string; sequence: number } | null; onRestored?: () => void;
  onHold?: (holding: boolean) => void }) {
  const [history, setHistory] = useState<RevisionRecord[]>([]);
  const [selection, setSelection] = useState<{ change: ChangeReadPage; before: JdView; after: JdView } | null>(null);
  const [proposal, setProposal] = useState<
    { preview: RestorePreviewPage; target: RevisionRecord; before: JdView; after: JdView } | null>(null);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const selectionGeneration = useRef(0);
  useEffect(() => () => { selectionGeneration.current++; }, [api, documentId]);
  // A comparison the employee is still deciding on holds editing and new
  // turns, so the JD cannot move under the version they are looking at.
  useEffect(() => { onHold?.(proposal !== null); }, [proposal, onHold]);
  useEffect(() => () => onHold?.(false), [onHold]);
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
  async function propose(target: RevisionRecord) {
    const generation = ++selectionGeneration.current;
    setBusy(true); setError(''); setSelection(null); setProposal(null);
    try {
      const preview = await api.restorePreview(documentId, target.revision_ref);
      const [before, after] = await Promise.all([preview.base_revision_ref, preview.target_revision_ref].map(
        target_ref => api.read(documentId, { view: 'history', target_ref, cursor: null }).then(projectView)));
      if (selectionGeneration.current === generation) setProposal({ preview, target, before, after });
    } catch (error) { if (selectionGeneration.current === generation) setError(message(error)); }
    finally { if (selectionGeneration.current === generation) setBusy(false); }
  }
  async function confirmRestore() {
    if (!proposal) return;
    const generation = ++selectionGeneration.current;
    setBusy(true); setError('');
    try {
      // The head this comparison was read at goes back with the request, so a
      // head that moved meanwhile is refused instead of being overwritten.
      const result = await api.save(documentId, { operation_id: crypto.randomUUID(),
        base_revision_ref: proposal.preview.base_revision_ref,
        command: { tool: 'restore_revision', arguments: { target_revision_ref: proposal.target.revision_ref } } });
      if (selectionGeneration.current !== generation) return;
      if (result.status === 'committed' || result.status === 'no_change') { setProposal(null); onRestored?.(); }
      else setError(result.error?.message ?? '這次還原未套用；請重新查看目前 JD。');
    } catch (error) { if (selectionGeneration.current === generation) setError(message(error)); }
    finally { if (selectionGeneration.current === generation) setBusy(false); }
  }
  return <Paper variant="outlined" sx={{ p: 3, mb: 3 }}><Typography variant="h6">改動與歷史</Typography>
    <Typography color="text.secondary" sx={{ my: 1 }}>查看每次實際保存的差異。收起或查看歷史，都不會更動目前 JD。</Typography>
    {error && <Alert severity="warning">{error}</Alert>}
    <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>{history.map(item => <Button key={item.revision_ref} disabled={busy || !item.change_ref}
      onClick={() => item.change_ref && void show(item.change_ref)}>{`第 ${item.revision_number} 版 · ${item.origin === 'ai' ? 'AI' : item.origin === 'manual' ? '手動' : '建立'} · ${new Date(item.created_at).toLocaleString('zh-TW')}`}</Button>)}</Stack>
    <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1, mt: 1 }}>{history.map(item => <Button key={`restore-${item.revision_ref}`}
      size="small" variant="outlined" disabled={busy} onClick={() => void propose(item)}>{`還原到第 ${item.revision_number} 版`}</Button>)}</Stack>
    {busy && <Typography role="status">讀取這次完整差異…</Typography>}
    {proposal && <Stack sx={{ mt: 2, gap: 1 }}>
      <Alert severity="info">{`以第 ${proposal.target.revision_number} 版的內容取代目前 JD；之後的內容仍可在歷史找到。這只會改 JD，不會動到訪談、工作理解或案例。`}</Alert>
      <Typography color="text.secondary">{proposal.preview.total_changes === 0
        ? '這一版的內容與目前完全相同，還原不會產生新版本。'
        : `會有 ${proposal.preview.total_changes} 處變動；以下逐項列出將回復與移除的內容。`}</Typography>
      <ChangeDetails records={proposal.preview.records} before={proposal.before} after={proposal.after} />
      <Stack direction="row" sx={{ gap: 1 }}>
        <Button variant="contained" disabled={busy} onClick={() => void confirmRestore()}>確認還原</Button>
        <Button disabled={busy} onClick={() => setProposal(null)}>取消</Button>
      </Stack>
    </Stack>}
    {selection && <ChangeDetails records={selection.change.records} before={selection.before} after={selection.after} />}
  </Paper>;
}
