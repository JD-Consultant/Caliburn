'use client';
import { Box, Divider, Paper, Typography } from '@mui/material';
import type { ChangeReadRecord } from '../../../src/jd_relational/generated/jd-read';
import type { JdView } from '../lib/view';
import { fieldLabels, kindLabels } from '../lib/view';
import { changeKinds, changeLabels, changeName, groupChanges, referenceName, type ChangeGroup } from '../lib/run-changes';

function DeletedContent({ group, before }: { group: ChangeGroup; before: JdView }) {
  return <Box role="note" sx={{ my: 1, p: 2, borderLeft: '3px solid', borderColor: 'error.main', bgcolor: 'action.hover' }}>
    <Typography sx={{ fontWeight: 700 }}>已刪除的原內容</Typography>
    {group.records.map((record, index) => {
      if (record.type !== 'value' || record.side !== 'before') return null;
      if (record.record.type === 'item') return <Typography key={index} className="jd-text">原所屬：{referenceName(before, record.record.container_ref)}</Typography>;
      if (record.record.type === 'field') return <Box key={index} sx={{ mt: 1 }}><Typography variant="caption">{fieldLabels[record.record.name]}</Typography>
        <Typography className="jd-text">{record.record.value ?? '（未填）'}</Typography></Box>;
      return null;
    })}
    {group.header.entity_kind === 'source_link' && <Typography>這筆依據關係已移除；下方保留原目標與確切依據識別。原話回查尚未接合。</Typography>}
  </Box>;
}
function Pair({ group, before, after }: { group: ChangeGroup; before: JdView; after: JdView }) {
  return <>
    {group.records.map((record, index) => record.type === 'affected_task' && <Typography key={index} variant="body2" className="jd-text">
      影響任務：{referenceName(before, record.before_task_ref)} → {referenceName(after, record.after_task_ref)}</Typography>)}
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, mt: 1 }}>{(['before', 'after'] as const).map(side => {
      const view = side === 'before' ? before : after;
      return <Paper key={side} variant="outlined" sx={{ p: 2 }}><Typography variant="subtitle2">{side === 'before' ? '修改前' : '修改後'}</Typography><Divider sx={{ my: 1 }} />
        {group.records.map((record, index) => {
          if (!('side' in record) || record.side !== side) return null;
          if (record.type === 'value') {
            const value = record.record;
            if (value.type === 'field') return <Box key={index} sx={{ mb: 1 }}><Typography variant="caption">{fieldLabels[value.name]}</Typography><Typography className="jd-text">{value.value ?? '（未填）'}</Typography></Box>;
            if (value.type === 'item') return <Typography key={index} className="jd-text">{kindLabels[value.kind]}；所屬：{referenceName(view, value.container_ref)}</Typography>;
            if (value.type === 'task_capability') return <Typography key={index} className="jd-text">{referenceName(view, value.task_ref)} → {referenceName(view, value.capability_ref)}</Typography>;
            return null;
          }
          if (record.type === 'item_placement') return <Typography key={index} className="jd-text">所屬：{referenceName(view, record.container_ref)}。前一項：{referenceName(view, record.previous_item_ref)}。後一項：{referenceName(view, record.next_item_ref)}。</Typography>;
          if (record.type === 'relation_placement') return <Typography key={index} className="jd-text">任務：{referenceName(view, record.task_ref)}；引用順序：{referenceName(view, record.previous_capability_ref)} → 本項 → {referenceName(view, record.next_capability_ref)}</Typography>;
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
        {!(side === 'before' ? group.header.before_exists : group.header.after_exists) && <Typography>（此項不存在）</Typography>}
      </Paper>;
    })}</Box>
  </>;
}
export default function ChangeDetails({ records, before, after, compact = false, idPrefix = 'jd-history-change' }: {
  records: ChangeReadRecord[]; before: JdView; after: JdView; compact?: boolean; idPrefix?: string;
}) {
  return <>{groupChanges(records).map(group => <Box key={group.header.change_index} id={`${idPrefix}-${group.header.change_index}`} sx={{ mt: 3, scrollMarginTop: 100 }}>
    <Typography sx={{ fontWeight: 700 }}>{changeKinds[group.header.kind]} · {changeName(group, before, after)}</Typography>
    <Typography variant="body2" color="text.secondary">{group.header.changed_fields.map(field => changeLabels[field] ?? field).join('、')}</Typography>
    {compact && group.header.kind === 'delete' && <DeletedContent group={group} before={before} />}
    {compact ? <details id={`${idPrefix}-detail-${group.header.change_index}`}><summary>查看完整修改前後</summary><Pair group={group} before={before} after={after} /></details>
      : <Pair group={group} before={before} after={after} />}
  </Box>)}</>;
}
