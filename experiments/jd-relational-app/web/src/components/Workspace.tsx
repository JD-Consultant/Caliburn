'use client';
import { useEffect, useMemo, useState } from 'react';
import { Alert, AppBar, Box, Button, Chip, CircularProgress, Container, Dialog, DialogActions,
  DialogContent, DialogTitle, Divider, MenuItem, Paper, Stack, TextField, Toolbar, Typography } from '@mui/material';
import { ApiError, JdApi } from '../lib/api';
import { openDraftStore, readCreation, storeCreation, clearCreation } from '../lib/drafts';
import type { CatalogCreateInput, CatalogDocument } from '../../../src/jd_relational/generated/jd-catalog-http';
import DocumentWorkspace from './DocumentWorkspace';

export function message(error: unknown): string {
  return error instanceof ApiError ? error.message : '目前無法完成操作，已保留內容。請重新查看狀態。';
}

export default function Workspace({ apiOrigin }: { apiOrigin: string | null }) {
  const api = useMemo(() => { try { return apiOrigin ? new JdApi(apiOrigin) : null; } catch { return null; } }, [apiOrigin]);
  const [documents, setDocuments] = useState<CatalogDocument[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [showArchived, setShowArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [safeToLeave, setSafeToLeave] = useState(true);
  const [error, setError] = useState('');
  const [dialog, setDialog] = useState<'create' | 'rename' | 'archive' | null>(null);
  const [title, setTitle] = useState('');
  const [creation, setCreation] = useState<CatalogCreateInput | null>(null);
  const current = documents.find(item => item.document_id === selected);

  async function refresh() {
    if (!api) return;
    const page = await api.list('all');
    setDocuments(page.documents);
    const store = await openDraftStore();
    try { setCreation(await readCreation(store, api.origin, page.dataset_id)); } finally { store.close(); }
    setError('');
  }
  useEffect(() => {
    let disposed = false;
    if (!api) { setLoading(false); return; }
    void refresh().catch(error => { if (!disposed) setError(message(error)); }).finally(() => { if (!disposed) setLoading(false); });
    return () => { disposed = true; };
  }, [api]); // The API instance fixes one service/dataset for this page lifetime.

  async function createDocument(recover: boolean) {
    if (!api?.datasetId || busy) return;
    setBusy(true); setError('');
    try {
      if (!navigator.locks) throw new ApiError('browser_unsupported', '此瀏覽器無法保護同時操作，請使用新版 Chrome 或 Edge。');
      await navigator.locks.request(JSON.stringify(['jd-create', api.origin, api.datasetId]), { ifAvailable: true }, async lock => {
        if (!lock) throw new ApiError('busy', '另一個分頁正在建立文件，請稍後重新查看。');
        const store = await openDraftStore();
        try {
          const old = await readCreation(store, api.origin, api.datasetId!);
          const request = old ?? { request_key: crypto.randomUUID(), dataset_id: api.datasetId!, title };
          if (!old && recover) throw new ApiError('creation_missing', '原建立操作已由其他分頁處理，請重新查看文件列表。');
          await storeCreation(store, api.origin, request);
          setCreation(request);
          // A missing lookup is not proof that the request never ran; same key only.
          const found = await api.lookupCreation(request);
          const result = found.state === 'found' ? found : await api.create(request);
          await clearCreation(store, api.origin, request.dataset_id, request.request_key);
          setCreation(null); setDialog(null); setTitle('');
          await refresh(); if (!selected) setSelected(result.document_id); setShowArchived(false);
        } finally { store.close(); }
      });
    } catch (error) { setError(message(error)); } finally { setBusy(false); }
  }

  async function changeMetadata() {
    if (!api || !current || !safeToLeave || (dialog !== 'rename' && dialog !== 'archive')) return;
    setBusy(true); setError('');
    try {
      const original = await api.metadata(current.document_id);
      if (original.document.metadata_version !== current.metadata_version) {
        await refresh(); throw new ApiError('metadata_changed', '文件資料已變更，請查看後再操作。');
      }
      const updated = await api.updateMetadata(current.document_id,
        dialog === 'rename' ? { title } : { archived: !current.archived }, original.etag);
      setDocuments(items => items.map(item => item.document_id === updated.document_id ? updated : item));
      setDialog(null);
      if (updated.archived) setShowArchived(true);
    } catch (error) { setError(message(error)); } finally { setBusy(false); }
  }

  if (!api) return <Container maxWidth="sm" sx={{ py: 8 }}><Paper sx={{ p: 4 }}>
    <Typography variant="h4" gutterBottom>Caliburn</Typography>
    <Typography variant="h6">尚未連接本機資料服務</Typography>
    <Typography sx={{ mt: 2 }}>請從已完成設定的 App 入口開啟。文件保存在本機資料庫，設定完成後即可建立與管理。</Typography>
  </Paper></Container>;

  return <><AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: '1px solid #dce2df' }}><Toolbar sx={{ gap: 2, flexWrap: 'wrap', py: 1 }}>
    <Typography variant="h6" sx={{ fontWeight: 800 }}>Caliburn</Typography>
    <Typography color="text.secondary">我的職務說明書</Typography><Box sx={{ flex: 1 }} />
    <Button onClick={() => { setTitle(''); setDialog('create'); }} disabled={busy || !safeToLeave || !!creation}>建立文件</Button>
  </Toolbar></AppBar>
  <Container maxWidth="xl" sx={{ py: 3 }}>
    {error && <Alert severity="error" sx={{ mb: 2 }} action={<Button disabled={busy} onClick={() => void refresh().catch(e => setError(message(e)))}>重新查看</Button>}>{error}</Alert>}
    {creation && <Alert severity="warning" sx={{ mb: 2 }} action={<Button disabled={busy} onClick={() => void createDocument(true)}>查回並繼續原建立</Button>}>
      「{creation.title}」的建立結果尚待確認。原操作已保留，可查回或繼續同一次建立。
    </Alert>}
    {loading ? <CircularProgress aria-label="讀取文件" /> : <>
      <Stack direction="row" spacing={2} sx={{ mb: 3, alignItems: 'center' }}>
        <TextField select label="文件" value={selected} sx={{ minWidth: 260, flex: 1 }} disabled={!safeToLeave || busy}
          onChange={event => setSelected(event.target.value)}>
          <MenuItem value="">選擇一份文件</MenuItem>
          {documents.filter(item => item.archived === showArchived || item.document_id === selected).map(item =>
            <MenuItem key={item.document_id} value={item.document_id}>{item.title}{item.archived ? '（已封存）' : ''}</MenuItem>)}
        </TextField>
        <Button onClick={() => setShowArchived(value => !value)}>{showArchived ? '顯示使用中文件' : '查看封存'}</Button>
        {current && <><Button disabled={!safeToLeave || busy} onClick={() => { setTitle(current.title); setDialog('rename'); }}>更名</Button>
          <Button disabled={!safeToLeave || busy} onClick={() => setDialog('archive')}>{current.archived ? '恢復' : '封存'}</Button></>}
      </Stack>
      {current ? <DocumentWorkspace key={JSON.stringify([api.origin, api.datasetId, current.document_id])}
        api={api} document={current} onSafeToLeave={setSafeToLeave} /> : <Paper sx={{ p: { xs: 3, md: 6 } }}>
        <Chip label="從你的實際工作開始" color="primary" variant="outlined" />
        <Typography variant="h4" sx={{ mt: 2, mb: 2 }}>把你的工作，整理成自己的職務說明書。</Typography>
        <Typography color="text.secondary" sx={{ maxWidth: 650 }}>先建立一份文件，再逐步整理職責、任務、成果與所需專業。已知的先寫下，尚未釐清的可以日後補充。</Typography>
        <Divider sx={{ my: 3 }} /><Button variant="contained" disabled={busy || !!creation} onClick={() => { setTitle(''); setDialog('create'); }}>建立第一份文件</Button>
      </Paper>}
    </>}
  </Container>
  {dialog !== null && <Dialog open onClose={() => { if (!busy) setDialog(null); }} fullWidth maxWidth="sm">
    <DialogTitle>{dialog === 'create' ? '建立職務說明書' : dialog === 'rename' ? '更改文件名稱' : current?.archived ? '恢復這份文件' : '封存這份文件'}</DialogTitle>
    <DialogContent>{dialog === 'archive' ? <Typography>「{current?.title}」{current?.archived ? '恢復後可以繼續編輯。' : '會保留全部內容與歷史，日後可從封存列表恢復。'}</Typography> :
      <TextField autoFocus fullWidth label="文件名稱" value={title} disabled={busy} sx={{ mt: 1 }} onChange={event => setTitle(event.target.value)} helperText="例如：王小明的工作說明。職稱可在文件內另外填寫。" />}</DialogContent>
    <DialogActions><Button disabled={busy} onClick={() => setDialog(null)}>取消</Button>
      <Button variant="contained" disabled={busy || (dialog !== 'archive' && !title.trim())} onClick={() => void (dialog === 'create' ? createDocument(false) : changeMetadata())}>
        {busy ? '處理中…' : dialog === 'create' ? '建立' : dialog === 'rename' ? '儲存名稱' : current?.archived ? '恢復' : '封存'}</Button></DialogActions>
  </Dialog>}</>;
}
