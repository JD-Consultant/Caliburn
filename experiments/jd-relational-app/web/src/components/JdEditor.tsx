'use client';
import { useState } from 'react';
import { Alert, Box, Button, Divider, Paper, Stack, TextField, Typography } from '@mui/material';
import type { ContainerRecord } from '../../../src/jd_relational/generated/jd-read.ts';
import type { ManualCommand } from '../../../src/jd_relational/generated/jd-manual-http.ts';
import { containerKey, fieldLabels, kindLabels, type FieldView, type ItemView, type JdView } from '../lib/view';
import ItemDialog, { itemText, manageItemForm, newItemForm, type CommandOptions } from './ItemDialog';
import type { ChangeMarker, RunMarkers } from '../lib/run-changes';

export interface JdEditorProps {
  view: JdView; disabled: boolean; commandsDisabled?: boolean;
  values: Record<string, string>;
  onField: (field: FieldView, text: string) => void;
  onComposition: (active: boolean) => void;
  onCommand: (command: ManualCommand, options?: CommandOptions) => Promise<void>;
  form: unknown | null; onFormChange: (value: unknown | null) => void;
  markers?: RunMarkers | null; onShowChange?: (changeIndex: number) => void;
}
export default function JdEditor({ view, disabled, commandsDisabled = false, values, onField,
  onComposition, onCommand, form, onFormChange, markers, onShowChange }: JdEditorProps) {
  const [error, setError] = useState(''); const [moving, setMoving] = useState(false);
  const structuralDisabled = disabled || commandsDisabled || moving || form !== null;
  const itemsFor = (container: ContainerRecord) => view.items.filter(item => item.container_ref === container.container_ref)
    .sort((a, b) => a.position - b.position);
  function openCreate(container: ContainerRecord) {
    if (!structuralDisabled) { setError(''); onFormChange(newItemForm(view, container)); }
  }
  function openManage(item: ItemView, mode: 'move' | 'delete' | 'revise' | 'capabilities') {
    if (!structuralDisabled) { setError(''); onFormChange(manageItemForm(view, item, mode)); }
  }
  async function reorder(item: ItemView, offset: -1 | 1) {
    if (structuralDisabled) return;
    const container = view.containers.find(row => row.container_ref === item.container_ref);
    if (!container) return;
    const siblings = itemsFor(container); const index = siblings.findIndex(row => row.item_id === item.item_id);
    if (index + offset < 0 || index + offset >= siblings.length) return;
    const anchor = offset === -1 ? siblings[index - 2] : siblings[index + 1];
    setError(''); setMoving(true);
    try { await onCommand({ tool: 'jd_move_item', arguments: { target_ref: item.item_ref,
      destination_container_ref: container.container_ref, after_ref: anchor?.item_ref ?? null, content_changes: [] } }); }
    catch { setError('排序尚未完成，請查看保存狀態。原保存結果未確認前，不會重做。'); }
    finally { setMoving(false); }
  }
  function markerLinks(values: ChangeMarker[] | undefined) {
    return values?.map(marker => <Button key={marker.changeIndex} size="small" variant="outlined"
      href={`#jd-run-change-${marker.changeIndex}`} onClick={() => onShowChange?.(marker.changeIndex)}>{marker.label} · 查看</Button>);
  }
  function fieldEditor(field: FieldView) {
    const text = Object.hasOwn(values, field.key) ? values[field.key] : field.value ?? '';
    return <Stack key={field.key} spacing={0.5}>
      {!!markers?.fields[field.key]?.length && <Stack direction="row" sx={{ gap: 0.5, flexWrap: 'wrap' }}>{markerLinks(markers.fields[field.key])}</Stack>}
      <TextField id={`jd-field-${field.itemId ?? 'profile'}-${field.name}`}
      label={fieldLabels[field.name]} multiline minRows={field.name === 'name' || field.name === 'job_title' ? 1 : 2}
      value={text} disabled={disabled} onChange={event => onField(field, event.target.value)}
      onCompositionStart={() => onComposition(true)} onCompositionEnd={event => {
        const target = event.target;
        if (target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement) onField(field, target.value);
        onComposition(false);
      }} /></Stack>;
  }
  function itemCard(item: ItemView, container: ContainerRecord, index: number, total: number) {
    const displayOrder: Partial<Record<FieldView['name'], number>> = { name: 0, description: 1, scope_text: 1, text: 2 };
    const displayFields = item.fields.toSorted((left, right) => (displayOrder[left.name] ?? 3) - (displayOrder[right.name] ?? 3));
    const childContainers = view.containers.filter(row => row.owner_ref === item.item_ref);
    const linked = view.relations.filter(relation => relation.task_ref === item.item_ref);
    const uses = view.relations.filter(relation => relation.capability_ref === item.item_ref);
    return <Box key={item.item_id} id={`jd-item-${item.item_id}`} className="jd-item" sx={{ scrollMarginTop: 100, py: 1 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap', mb: 1.5 }}>
        <Typography variant="subtitle2" sx={{ flex: 1 }}>{kindLabels[item.kind]} {index + 1}</Typography>
        {markerLinks(markers?.items[item.item_id])}
        <Button size="small" disabled={structuralDisabled || index === 0} aria-label={`${kindLabels[item.kind]} ${index + 1} 上移`} onClick={() => void reorder(item, -1)}>上移</Button>
        <Button size="small" disabled={structuralDisabled || index === total - 1} aria-label={`${kindLabels[item.kind]} ${index + 1} 下移`} onClick={() => void reorder(item, 1)}>下移</Button>
        {item.kind === 'task' && <><Button size="small" disabled={structuralDisabled} onClick={() => openManage(item, 'move')}>移動至職責</Button>
          <Button size="small" disabled={structuralDisabled} onClick={() => openManage(item, 'revise')}>完整修訂</Button></>}
        <Button size="small" color="error" disabled={structuralDisabled} aria-label={`刪除${kindLabels[item.kind]} ${index + 1}`} onClick={() => openManage(item, 'delete')}>刪除</Button>
      </Stack>
      <Stack spacing={2}>{displayFields.map(fieldEditor)}</Stack>
      {item.kind === 'task' && <Box sx={{ mt: 2 }}>
        <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="subtitle2">使用的知識與技能</Typography>
          <Button size="small" disabled={structuralDisabled} onClick={() => openManage(item, 'capabilities')}>選擇知識與技能</Button>
        </Stack>
        {!linked.length && <Typography color="text.secondary" variant="body2">尚未選擇</Typography>}
        {linked.map(relation => {
          const capability = view.items.find(row => row.item_ref === relation.capability_ref)!;
          return <Box key={capability.item_id} sx={{ mb: 1 }}>
            <Button href={`#jd-item-${capability.item_id}`} sx={{ textAlign: 'left', whiteSpace: 'pre-wrap' }}>
              {kindLabels[capability.kind]}：{capability.fields.find(field => field.name === 'name')?.value ?? '尚未命名'}</Button>
            <Typography variant="body2" className="jd-text" sx={{ pl: 1 }}>{capability.fields.find(field => field.name === 'description')?.value ?? '尚未填寫說明'}</Typography>
          </Box>;
        })}
      </Box>}
      {(item.kind === 'knowledge' || item.kind === 'skill') && <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle2">用於 {uses.length} 項任務</Typography>
        <Typography variant="body2" color="text.secondary">修改這個共用定義，所有引用任務都會讀到新內容。</Typography>
        {!uses.length && <Typography variant="body2" color="text.secondary">目前沒有任務引用。</Typography>}
        {uses.map((relation, useIndex) => {
          const task = view.items.find(row => row.item_ref === relation.task_ref)!;
          return <Stack key={task.item_id} direction="row" sx={{ alignItems: 'flex-start' }}>
            <Button href={`#jd-item-${task.item_id}`} sx={{ flex: 1, justifyContent: 'flex-start', textAlign: 'left', whiteSpace: 'pre-wrap' }}>任務 {useIndex + 1}：{itemText(task)}</Button>
            <Button size="small" disabled={structuralDisabled} onClick={() => openManage(task, 'capabilities')}>調整引用</Button>
          </Stack>;
        })}
      </Box>}
      {childContainers.map(child => containerGroup(child, true))}
    </Box>;
  }
  function containerGroup(container: ContainerRecord, nested = false) {
    const items = itemsFor(container);
    const label = container.child_kind === 'task' && container.owner_ref === null ? '尚未歸入職責的任務' : kindLabels[container.child_kind];
    return <Box key={containerKey(view, container)} sx={{ mt: nested ? 3 : 2 }}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 2 }}>
        <Typography variant={nested ? 'subtitle1' : 'h6'} sx={{ fontWeight: 650 }}>{label}</Typography>
        <Button disabled={structuralDisabled} onClick={() => openCreate(container)}>新增{kindLabels[container.child_kind]}</Button>
      </Stack>
      {items.length ? <Stack spacing={3}>{items.map((item, index) => itemCard(item, container, index, items.length))}</Stack>
        : <Typography color="text.secondary" variant="body2">尚未新增{kindLabels[container.child_kind]}。</Typography>}
    </Box>;
  }
  return <>
    <Paper component="nav" aria-label="JD 章節" variant="outlined" sx={{ p: 1, mb: 2 }}>
      <Stack direction="row" sx={{ flexWrap: 'wrap' }}>{view.sections.map((section, index) =>
        <Button key={section.section_key} href={`#jd-section-${section.section_key}`} size="small">{index + 1} {section.title}</Button>)}</Stack>
    </Paper>
    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
    <Stack spacing={3}>{view.sections.map((section, index) => <Paper key={section.section_key} component="section"
      id={`jd-section-${section.section_key}`} className="jd-section" variant="outlined" sx={{ p: { xs: 2, md: 3 } }}>
      <Typography variant="h5" sx={{ fontWeight: 700, mb: 2 }}>{index + 1}　{section.title}</Typography>
      {section.section_key === 'conditions' && <Typography color="text.secondary" sx={{ mb: 2 }}>在這裡記錄全職位共通的條件與邊界。只適用某項任務的範圍與條件，依內容寫在該任務的敘述或要求中。</Typography>}
      <Stack spacing={2}>{view.fields.filter(field => field.section_ref === section.section_ref && field.item_ref === null).map(fieldEditor)}</Stack>
      {view.containers.filter(container => container.section_ref === section.section_ref && container.owner_ref === null).map((container, index) =>
        <Box key={containerKey(view, container)}>{index > 0 && <Divider sx={{ my: 3 }} />}{containerGroup(container)}</Box>)}
    </Paper>)}</Stack>
    <ItemDialog view={view} form={form} disabled={disabled || commandsDisabled} onFormChange={onFormChange}
      onComposition={onComposition} onCommand={onCommand} />
  </>;
}
