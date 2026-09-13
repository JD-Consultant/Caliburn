'use client';
import { useEffect, useState } from 'react';
import { Alert, Box, Button, Divider, Paper, Stack, Typography } from '@mui/material';
import { JdApi } from '../lib/api';
import { fieldLabels, projectView, kindLabels } from '../lib/view';
import type { JdView } from '../lib/view';
import type { ChangeReadPage, RevisionRecord } from '../../../src/jd_relational/generated/jd-read';
import { message } from './Workspace';

const changes = { create: '新增', update: '修改', delete: '刪除', move: '移動', reorder: '順序調整', link: '加入引用', unlink: '移除引用' };
const changeLabels: Record<string, string> = { ...fieldLabels, container_ref: '所屬分類', position: '順序', capability_ref: '知識／技能引用',
  source_ref: '依據', basis_digest: '依據對照', task_ref: '任務', kind: '類型', target_ref: '引用目標', related_capability_ref: '關聯知識／技能' };
function name(view: JdView, ref: string | null): string {
  if (!ref) return '無';
  const item = view.items.find(item => item.item_ref === ref);
  if (item) return item.fields.find(field => field.name === 'name')?.value
    || item.fields.find(field => ['text', 'description'].includes(field.name))?.value || kindLabels[item.kind];
  const container = view.containers.find(item => item.container_ref === ref);
  if (container) return container.owner_ref ? name(view, container.owner_ref) :
    container.child_kind === 'task' ? '尚未歸入職責的任務' : kindLabels[container.child_kind];
  return '未提供可讀名稱';
}
export default function HistoryPanel({ api, documentId, revisionRef }: { api: JdApi; documentId: string; revisionRef: string | null }) {
  const [history, setHistory] = useState<RevisionRecord[]>([]);
  const [selection, setSelection] = useState<{ change: ChangeReadPage; before: JdView; after: JdView } | null>(null);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  useEffect(() => { let live = true;
    void api.read(documentId, { view: 'history', target_ref: null, cursor: null }).then(page => {
      if (live) setHistory(page.records.filter((item): item is RevisionRecord => item.type === 'revision'));
    }).catch(error => { if (live) setError(message(error)); });
    return () => { live = false; };
  }, [api, documentId, revisionRef]);
  async function show(ref: string) {
    setBusy(true); setError(''); setSelection(null);
    try {
      const change = await api.changes(documentId, ref);
      const [before, after] = await Promise.all([change.base_revision_ref, change.result_revision_ref].map(target_ref =>
        api.read(documentId, { view: 'history', target_ref, cursor: null }).then(projectView)));
      setSelection({ change, before, after });
    } catch (error) { setError(message(error)); } finally { setBusy(false); }
  }
  return <Paper variant="outlined" sx={{ p: 3, mb: 3 }}><Typography variant="h6">改動與歷史</Typography>
    <Typography color="text.secondary" sx={{ my: 1 }}>查看每次實際保存的差異。收起或查看歷史，都不會更動目前 JD。</Typography>
    {error && <Alert severity="warning">{error}</Alert>}
    <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>{history.map(item => <Button key={item.revision_ref} disabled={busy || !item.change_ref}
      onClick={() => item.change_ref && void show(item.change_ref)}>{`第 ${item.revision_number} 版 · ${item.origin === 'ai' ? 'AI' : item.origin === 'manual' ? '手動' : '建立'} · ${new Date(item.created_at).toLocaleString('zh-TW')}`}</Button>)}</Stack>
    {busy && <Typography role="status">讀取這次完整差異…</Typography>}
    {selection && selection.change.records.filter(record => record.type === 'change').map(header => <Box key={header.change_index} sx={{ mt: 3 }}>
      <Typography sx={{ fontWeight: 700 }}>{changes[header.kind]} · {header.changed_fields.map(field => changeLabels[field] ?? field).join('、')}</Typography>
      {selection.change.records.filter(record => record.type === 'affected_task' && record.change_index === header.change_index).map((record, index) =>
        record.type === 'affected_task' && <Typography key={index} variant="body2" className="jd-text">影響任務：{name(selection.before, record.before_task_ref)} → {name(selection.after, record.after_task_ref)}</Typography>)}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, mt: 1 }}>{(['before', 'after'] as const).map(side => {
        const view = selection[side];
        return <Paper key={side} variant="outlined" sx={{ p: 2 }}><Typography variant="subtitle2">{side === 'before' ? '修改前' : '修改後'}</Typography><Divider sx={{ my: 1 }} />
          {selection.change.records.filter(record => record.change_index === header.change_index).map((record, index) => {
            if (!('side' in record) || record.side !== side) return null;
            if (record.type === 'value') {
              const value = record.record;
              if (value.type === 'field') return <Box key={index} sx={{ mb: 1 }}><Typography variant="caption">{fieldLabels[value.name]}</Typography><Typography className="jd-text">{value.value ?? '（未填）'}</Typography></Box>;
              if (value.type === 'task_capability') return <Typography key={index} className="jd-text">{name(view, value.task_ref)} → {name(view, value.capability_ref)}</Typography>;
              return null;
            }
            if (record.type === 'item_placement') return <Typography key={index} className="jd-text">所屬：{name(view, record.container_ref)}。前一項：{name(view, record.previous_item_ref)}。後一項：{name(view, record.next_item_ref)}。</Typography>;
            if (record.type === 'relation_placement') return <Typography key={index} className="jd-text">任務：{name(view, record.task_ref)}；引用順序：{name(view, record.previous_capability_ref)} → 本項 → {name(view, record.next_capability_ref)}</Typography>;
            if (record.type === 'source_value') return <Box key={index}><Typography>依據關係：{record.record.basis_status === 'current' ? '對照仍相符' : '內容變更，待重新核對'}（原話回查尚未接合）</Typography>
              <details><summary>查看確切依據識別、順序與對照</summary><Box component="pre" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify({
                source: record.record.source_ref, target: record.record.target_ref, relatedCapability: record.record.related_capability_ref,
                order: record.position, basis: record.basis_digest, readability: record.record.readability }, null, 2)}</Box></details></Box>;
            if (record.type === 'source_placement') return <Box key={index}><Typography>依據順序已記錄（原話回查尚未接合）。</Typography>
              <details><summary>查看確切前後依據關係</summary><Box component="pre" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify({
                target: record.target_ref, relatedCapability: record.related_capability_ref,
                previous: record.previous_source_ref, next: record.next_source_ref }, null, 2)}</Box></details></Box>;
            return null;
          })}
          {!(side === 'before' ? header.before_exists : header.after_exists) && <Typography>（此項不存在）</Typography>}
        </Paper>;
      })}</Box></Box>)}
  </Paper>;
}
