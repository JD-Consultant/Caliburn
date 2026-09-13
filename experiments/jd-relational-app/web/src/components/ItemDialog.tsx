'use client';
import { useEffect, useState } from 'react';
import { Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle,
  Divider, FormControlLabel, MenuItem, Stack, TextField, Typography } from '@mui/material';
import type { ContainerRecord } from '../../../src/jd_relational/generated/jd-read.ts';
import { kindLabels, fieldLabels, type ItemView } from '../lib/view';
import { parseItemForm, itemText, containerFor, itemFor, formSummary, structuralFields, siblings, children,
  addressOf, nullable, commandForForm, commandForNewCapability, type ItemDialogProps, type ItemForm, type FormField, type FormDetail } from '../lib/item-form';
export type { ItemForm, CommandOptions } from '../lib/item-form';
export { itemText, newItemForm, manageItemForm } from '../lib/item-form';
export default function ItemDialog({ view, form: unknownForm, disabled, onFormChange, onComposition, onCommand }: ItemDialogProps) {
  const [error, setError] = useState(''); const [saving, setSaving] = useState(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  useEffect(() => {
    if (unknownForm === null) { setError(''); setConfirmDiscard(false); }
  }, [unknownForm]);
  if (unknownForm === null) return null;
  const form = parseItemForm(unknownForm);
  const busy = disabled || saving;
  const discard = () => { onComposition(false); onFormChange(null); setConfirmDiscard(false); setError(''); };
  if (!form) return <Dialog open fullWidth maxWidth="sm"><DialogTitle>找回的表單需要處理</DialogTitle>
    <DialogContent><Alert severity="warning">這份未提交內容的格式無法辨認，已保留。請勿將它視為已保存的 JD。</Alert>
      <Typography component="pre" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', fontSize: 13 }}>{JSON.stringify(unknownForm, null, 2)}</Typography>
      {confirmDiscard && <Alert severity="warning">捨棄後，這份未提交表單將無法找回。已保存的 JD 不受影響。</Alert>}</DialogContent>
    <DialogActions><Button disabled={busy} color="error" onClick={() => confirmDiscard ? discard() : setConfirmDiscard(true)}>
      {confirmDiscard ? '確定捨棄這份表單' : '捨棄無法辨認的表單'}</Button></DialogActions></Dialog>;
  let container: ContainerRecord | null = null; let item: ItemView | null = null;
  try {
    if (form.itemId) item = itemFor(view, form.itemId);
    container = form.mode === 'create' || form.mode === 'move' ? containerFor(view, form.container)
      : view.containers.find(row => row.container_ref === item?.container_ref) ?? null;
  } catch { /* Preserve the draft and show a safe explanation below. */ }
  const stale = form.baseRevisionRef !== view.revisionRef;
  const missing = !container || (form.itemId !== null && !item);
  const update = (patch: Partial<ItemForm>) => { setError(''); onFormChange({ ...form, ...patch }); };
  const fieldInput = (field: FormField, index: number) => {
    const owner = field.itemId === null ? null : view.items.find(item => item.item_id === field.itemId);
    const prefix = (form.mode === 'move' || form.mode === 'delete') && owner ? `${kindLabels[owner.kind]}：${itemText(owner)}／` : '';
    return <TextField key={JSON.stringify([field.itemId, field.name])} multiline minRows={field.name === 'name' ? 1 : 2}
      label={`${prefix}${fieldLabels[field.name]}`} value={field.text} disabled={busy}
      onChange={event => update({ fields: form.fields.map((row, at) => at === index ? { ...row, text: event.target.value } : row) })}
      onCompositionStart={() => onComposition(true)} onCompositionEnd={() => onComposition(false)} />;
  };
  const detailInputs = (kind: FormDetail['kind'], taskId: string | null) => <Stack spacing={1.5}>
    {form.details.filter(detail => detail.kind === kind && detail.taskId === taskId).map((detail, index) => <Stack key={detail.key} direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
      <TextField multiline minRows={2} label={`${kindLabels[kind]} ${index + 1}`} value={detail.text} disabled={busy}
        onChange={event => update({ details: form.details.map(row => row.key === detail.key ? { ...row, text: event.target.value } : row) })}
        onCompositionStart={() => onComposition(true)} onCompositionEnd={() => onComposition(false)} />
      <Button disabled={busy} color="error" aria-label={`移除${kindLabels[kind]} ${index + 1}`} onClick={() => update({ details: form.details.filter(row => row.key !== detail.key) })}>移除</Button>
    </Stack>)}
    <Button sx={{ alignSelf: 'flex-start' }} disabled={busy} onClick={() => update({ details: [...form.details,
      { key: crypto.randomUUID(), itemId: null, taskId, kind, baseValue: null, text: '' }] })}>新增一筆{kindLabels[kind]}</Button>
  </Stack>;
  const capabilityOptions = view.items.filter(row => row.kind === 'knowledge' || row.kind === 'skill');
  const taskForm = (form.mode === 'create' && form.container.kind === 'task') || form.mode === 'revise';
  const currentChildren = item?.kind === 'duty' ? children(view, item).filter(row => row.kind === 'task') : [];
  const canAdjust = (form.mode === 'delete' && item?.kind === 'duty')
    || (form.mode === 'move' && item?.kind === 'task' && container?.container_ref !== item.container_ref);
  const moveDestinations = item?.kind === 'task' ? view.containers.filter(row => row.child_kind === 'task')
    : view.containers.filter(row => row.container_ref === item?.container_ref);
  const containerOwner = view.items.find(row => row.item_ref === container?.owner_ref);
  const title = form.mode === 'create' ? `新增${kindLabels[form.container.kind]}` : form.mode === 'revise' ? '完整修訂任務'
    : form.mode === 'move' ? `移動或排序${item ? kindLabels[item.kind] : '項目'}` : form.mode === 'delete' ? '刪除項目' : '選擇知識與技能';
  async function submit() {
    if (!form || busy || stale || missing) return;
    setError(''); setSaving(true);
    try {
      const command = commandForForm(view, form);
      if (!command) { setError('這份表單尚無改動。可以繼續編輯，或捨棄表單返回。'); return; }
      await onCommand(command);
      // Only the parent can retire the exact acknowledged form generation.
    } catch { setError('尚未完成保存，表單已保留。請查看保存狀態，確認目標及內容後再繼續。'); }
    finally { setSaving(false); }
  }
  async function saveNewCapability() {
    if (!form || busy || stale || missing || !form.newCapability) return;
    setError(''); setSaving(true);
    try { await onCommand(commandForNewCapability(view, form), { preserveForm: true }); }
    catch { setError('新增知識或技能的保存結果尚待處理。請先查看原保存狀態；任務表單已保留。'); }
    finally { setSaving(false); }
    // The original receipt settles only the nested candidate in the same IDB transaction.
  }
  return <Dialog open fullWidth maxWidth="md" onClose={(_, reason) => { if (reason !== 'escapeKeyDown') setConfirmDiscard(true); }}>
    <DialogTitle>{title}</DialogTitle><DialogContent dividers><Stack spacing={2.5}>
      <Typography color="text.secondary">填入目前已知的內容；文字可換行。按完成後，這次操作才會一起保存。</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      {missing && <Alert severity="warning">原項目或位置目前不存在，表單已保留。請先查看目前稿，不會依同名文字另找目標。</Alert>}
      {stale && <Alert severity="warning">表單建立後，已保存內容有變動。請比較原內容與目前內容，再明示繼續。</Alert>}
      {(stale || form.mode === 'delete') && <Box><Typography variant="subtitle2">{stale ? '建立表單時的內容' : '本次影響項目'}</Typography>
        <Typography className="jd-text">{form.baselineText}</Typography></Box>}
      {stale && <><Box><Typography variant="subtitle2">目前保存的內容</Typography><Typography className="jd-text">{formSummary(view, form)}</Typography></Box>
        <Button disabled={busy || missing} variant="outlined" onClick={() => update({ baseRevisionRef: view.revisionRef, baselineText: formSummary(view, form) })}>已比較，沿原修改範圍繼續</Button></>}
      {form.mode === 'delete' && <Alert severity="warning">{item?.kind === 'duty' ? `此職責會刪除；${currentChildren.length} 項任務會保留並移到「尚未歸入職責」。成果、要求及知識技能引用會保留。請把仍適用的職責範圍補進相關任務。`
        : item?.kind === 'task' ? '此任務及其成果、要求、知識技能引用會一起刪除；共用知識與技能定義仍保留。'
        : item?.kind === 'knowledge' || item?.kind === 'skill' ? '這是共用定義。仍有任務引用時，保存會拒絕刪除；請先解除相關任務的引用。' : '這個項目會從目前 JD 刪除。'}</Alert>}
      {(form.mode === 'create' || form.mode === 'move') && container && <>
        {form.mode === 'create' && containerOwner && <Box><Typography variant="subtitle2">新增至{kindLabels[containerOwner.kind]}：{itemText(containerOwner)}</Typography>
          <Typography className="jd-text" color="text.secondary">{containerOwner.fields.find(field => field.name === 'scope_text' || field.name === 'description')?.value}</Typography></Box>}
        {form.mode === 'create' && !containerOwner && container.child_kind === 'task' && <Typography>位置：尚未歸入職責的任務</Typography>}
        {form.mode === 'move' && <TextField select label="目標職責" value={JSON.stringify(form.container)} disabled={busy}
          onChange={event => {
            const destination = moveDestinations.find(row => JSON.stringify(addressOf(view, row)) === event.target.value);
            if (!destination || !item) return;
            if (form.fields.some(field => nullable(field.text) !== field.baseValue) || form.details.length) {
              setError('請先保留目前目標，或清除下方內容調整後再改選位置。'); return;
            }
            update({ container: addressOf(view, destination), afterId: siblings(view, destination).filter(row => row.item_id !== item.item_id).at(-1)?.item_id ?? null,
              fields: structuralFields(view, item, destination) });
          }}>{moveDestinations.map(row => {
            const owner = view.items.find(item => item.item_ref === row.owner_ref);
            return <MenuItem key={JSON.stringify(addressOf(view, row))} value={JSON.stringify(addressOf(view, row))} sx={{ whiteSpace: 'normal' }}>
              <Box>{owner ? `職責：${itemText(owner)}` : row.child_kind === 'task' ? '尚未歸入職責' : kindLabels[row.child_kind]}
                {owner && <Typography variant="body2" className="jd-text" color="text.secondary">{owner.fields.find(field => field.name === 'scope_text')?.value}</Typography>}</Box></MenuItem>;
          })}</TextField>}
        <TextField select label="放置位置" value={form.afterId ?? ''} disabled={busy} onChange={event => update({ afterId: event.target.value || null })}>
          <MenuItem value="">最前面</MenuItem>{siblings(view, container).filter(row => row.item_id !== form.itemId).map((row, index) =>
            <MenuItem key={row.item_id} value={row.item_id} sx={{ whiteSpace: 'normal' }}>第 {index + 1} 項之後：{itemText(row)}</MenuItem>)}</TextField>
      </>}
      {canAdjust && <><Divider /><Typography variant="h6">隨本次操作保存的內容調整</Typography>
        <Typography color="text.secondary">只補充這些相關工作的必要範圍。沒有改動的欄位會保持原樣。</Typography>
        <Button disabled={busy} onClick={() => update({ fields: form.fields.map(field => ({ ...field, text: field.baseValue ?? '' })), details: [] })}>清除這些內容調整</Button></>}
      {(form.mode === 'create' || form.mode === 'revise' || canAdjust) && form.fields.map(fieldInput)}
      {taskForm && <><Divider /><Typography variant="h6">成果</Typography>{detailInputs('outcome', form.itemId)}
        <Typography variant="h6">要求</Typography>{detailInputs('requirement', form.itemId)}</>}
      {canAdjust && (item?.kind === 'duty' ? currentChildren : item ? [item] : []).map(task => <Box key={task.item_id}>
        <Typography variant="subtitle1" className="jd-text">為「{itemText(task)}」補充</Typography>
        {detailInputs('outcome', task.item_id)}{detailInputs('requirement', task.item_id)}</Box>)}
      {(taskForm || form.mode === 'capabilities') && <><Divider /><Typography variant="h6">此任務使用的知識與技能</Typography>
        <Typography color="text.secondary">勾選共用定義；同名項目請依完整說明區分。完成時一起保存選擇。</Typography>
        {!capabilityOptions.length && <Typography>目前尚未建立知識或技能。</Typography>}
        {form.newCapability ? <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}><Stack spacing={2}>
          <Typography variant="subtitle1">另建共用{kindLabels[form.newCapability.kind]}</Typography>
          <Typography color="text.secondary">這一項會先獨立保存，任務表單繼續保留。保存後，請在下方清單選取正確項目。</Typography>
          <TextField multiline label="共用項目名稱" value={form.newCapability.name} disabled={busy}
            onChange={event => update({ newCapability: { ...form.newCapability!, name: event.target.value } })}
            onCompositionStart={() => onComposition(true)} onCompositionEnd={() => onComposition(false)} />
          <TextField multiline minRows={3} label="共用項目完整說明" value={form.newCapability.description} disabled={busy}
            onChange={event => update({ newCapability: { ...form.newCapability!, description: event.target.value } })}
            onCompositionStart={() => onComposition(true)} onCompositionEnd={() => onComposition(false)} />
          <Stack direction="row" spacing={1}><Button variant="outlined" disabled={busy || stale || missing} onClick={() => void saveNewCapability()}>先保存這項{kindLabels[form.newCapability.kind]}</Button>
            <Button disabled={busy} onClick={() => update({ newCapability: null })}>捨棄這項新增候選</Button></Stack>
        </Stack></Box> : <Stack direction="row" spacing={1}>
          <Button disabled={busy} onClick={() => update({ newCapability: { kind: 'knowledge', name: '', description: '' } })}>另建共用知識</Button>
          <Button disabled={busy} onClick={() => update({ newCapability: { kind: 'skill', name: '', description: '' } })}>另建共用技能</Button>
        </Stack>}
        {capabilityOptions.map((capability, index) => <Box key={capability.item_id} sx={{ borderBottom: '1px solid', borderColor: 'divider', pb: 1 }}>
          <FormControlLabel control={<Checkbox checked={form.capabilityIds.includes(capability.item_id)} disabled={busy}
            onChange={event => update({ capabilityIds: event.target.checked ? [...form.capabilityIds, capability.item_id] : form.capabilityIds.filter(itemId => itemId !== capability.item_id) })} />}
            label={`${kindLabels[capability.kind]} ${index + 1}：${capability.fields.find(field => field.name === 'name')?.value ?? '尚未命名'}`} />
          <Typography className="jd-text" sx={{ ml: 4 }}>{capability.fields.find(field => field.name === 'description')?.value ?? '尚未填寫說明'}</Typography>
        </Box>)}</>}
      {confirmDiscard && <Alert severity="warning">確定捨棄這份未提交表單？已保存的 JD 不受影響。
        <Stack direction="row" spacing={1}><Button color="error" disabled={busy} onClick={discard}>確定捨棄表單</Button>
          <Button onClick={() => setConfirmDiscard(false)}>繼續編輯</Button></Stack></Alert>}
    </Stack></DialogContent><DialogActions><Button disabled={busy} onClick={() => setConfirmDiscard(true)}>捨棄表單</Button>
      <Button variant="contained" color={form.mode === 'delete' ? 'error' : 'primary'} disabled={busy || stale || missing || form.newCapability !== null} onClick={() => void submit()}>
        {saving ? '處理中…' : form.mode === 'delete' ? '確認刪除' : '完成並保存'}</Button></DialogActions>
  </Dialog>;
}
