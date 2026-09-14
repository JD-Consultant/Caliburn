/** Presentation only: consume captured server changes; never diff or decode refs. */
import type { ChatRunChangePage, ChatRunState } from '../../../src/jd_relational/generated/jd-chat-http.ts';
import type { ChangeHeaderRecord, ChangeReadRecord } from '../../../src/jd_relational/generated/jd-read.ts';
import { fieldKey, fieldLabels, kindLabels, type JdView } from './view.ts';

export const changeKinds = { create: '新增', update: '修改', delete: '刪除', move: '移動', reorder: '順序調整', link: '加入引用', unlink: '移除引用' };
export const changeLabels: Record<string, string> = { ...fieldLabels, container_ref: '所屬分類', position: '順序', capability_ref: '知識／技能引用',
  source_ref: '依據', basis_digest: '依據對照', task_ref: '任務', kind: '類型', target_ref: '引用目標', related_capability_ref: '關聯知識／技能' };
export interface ChangeGroup { header: ChangeHeaderRecord; records: ChangeReadRecord[] }
export interface ChangeMarker { label: string; changeIndex: number }
export interface RunMarkers { fields: Record<string, ChangeMarker[]>; items: Record<string, ChangeMarker[]> }
export interface RunChangeScope { api: object; datasetId: string | null; documentId: string; key: string | null }
export interface LoadedRunChange extends RunChangeScope { page: ChatRunChangePage; before: JdView | null; after: JdView | null }

export function matchingRun(chat: { run: ChatRunState | null; runId: string | null }, originalRunId: string | null,
  scope: Pick<RunChangeScope, 'datasetId' | 'documentId'>): ChatRunState | null {
  const run = chat.run;
  return run && run.run_id === chat.runId && (!originalRunId || originalRunId === run.run_id)
    && run.dataset_id === scope.datasetId && run.document_id === scope.documentId ? run : null;
}
export function runChangeKey(run: ChatRunState | null): string | null {
  if (!run) return null;
  const operations = run.jd_effects.results.filter(result => result.status === 'committed').map(result => result.operation_ref).sort();
  if (!operations.length && run.jd_effects.state !== 'settled') return null;
  return JSON.stringify([run.dataset_id, run.document_id, run.run_id, run.jd_effects.state, operations]);
}
export function currentRunChanges(value: LoadedRunChange | null, scope: RunChangeScope): LoadedRunChange | null {
  return value && scope.key !== null && value.key === scope.key && value.api === scope.api
    && value.documentId === scope.documentId && value.datasetId === scope.datasetId
    && value.page.document_id === scope.documentId && value.page.dataset_id === scope.datasetId ? value : null;
}
export function groupChanges(records: ChangeReadRecord[]): ChangeGroup[] {
  return records.filter((record): record is ChangeHeaderRecord => record.type === 'change')
    .map(header => ({ header, records: records.filter(record => record.change_index === header.change_index) }));
}
export function referenceName(view: JdView, ref: string | null): string {
  if (!ref) return '無';
  const item = view.items.find(item => item.item_ref === ref);
  if (item) return item.fields.find(field => field.name === 'name')?.value
    || item.fields.find(field => ['text', 'description'].includes(field.name))?.value || kindLabels[item.kind];
  const field = view.fields.find(field => field.field_ref === ref);
  if (field) return fieldLabels[field.name];
  const container = view.containers.find(item => item.container_ref === ref);
  if (container) {
    // Use the already supplied ownership path. Equal task/detail text under
    // different duties must not make historical deletions indistinguishable.
    const names: string[] = [], seen = new Set<string>();
    let ownerRef = container.owner_ref;
    while (ownerRef !== null) {
      const owner = view.items.find(item => item.item_ref === ownerRef);
      const parent = owner && view.containers.find(item => item.container_ref === owner.container_ref);
      if (!owner || !parent || seen.has(ownerRef)) return '未提供完整可讀所屬';
      seen.add(ownerRef);
      names.unshift(`${kindLabels[owner.kind]}「${referenceName(view, ownerRef)}」`);
      ownerRef = parent.owner_ref;
    }
    return names.length ? names.join('／') : container.child_kind === 'task' ? '尚未歸入職責的任務' : kindLabels[container.child_kind];
  }
  return '未提供可讀名稱';
}
export function changeName(group: ChangeGroup, before: JdView, after: JdView): string {
  const side = group.header.after_exists ? 'after' : 'before', view = side === 'after' ? after : before;
  for (const record of group.records) {
    if (!('side' in record) || record.side !== side) continue;
    if (record.type === 'value') {
      const value = record.record;
      if (value.type === 'item') return `${kindLabels[value.kind]}：${referenceName(view, value.item_ref)}`;
      if (value.type === 'task_capability') return `任務「${referenceName(view, value.task_ref)}」的知識／技能引用`;
    }
    if (record.type === 'source_value') return `「${referenceName(view, record.record.target_ref)}」的依據`;
  }
  return group.header.changed_fields.map(field => changeLabels[field] ?? field).join('、') || '內容';
}
export function runChangeSummary(page: ChatRunChangePage): string {
  if (page.continuity === 'none') return page.effects_state === 'settled' ? '本輪沒有修改 JD。' : '本輪修改結果尚未全部確認。';
  if (page.continuity === 'discontinuous') return '這輪改動之間夾有其他修改，沒有單一連續比較；請查看各次實際改動。';
  if (page.total_changes === 0) return '這次範圍沒有淨變更，但曾有保存紀錄。';
  return '以下是這輪已確認範圍的修改前後；查看不會更動 JD。';
}
export type UndoOffer =
  | { available: true; runId: string; expectedResultRef: string }
  | { available: false; reason: string };

// Undoing is offered only when this turn can be taken back as one range: it has
// finished, its saved changes are unbroken, it really wrote something, and the
// document is still exactly where it left it. Anything else would risk
// discarding work done afterwards, so the reason is shown instead of a button.
export function undoOffer(page: ChatRunChangePage, currentRevisionRef: string | null): UndoOffer {
  if (page.effects_state !== 'settled') return { available: false, reason: '這輪還沒有全部確認，先查看結果再決定是否撤回。' };
  if (page.continuity === 'none' || page.total_changes === 0 || !page.result_revision_ref)
    return { available: false, reason: '這輪沒有對 JD 的淨變更，沒有可撤回的內容。' };
  if (page.continuity !== 'continuous')
    return { available: false, reason: '這輪改動之間夾有其他修改，無法整輪撤回；可在歷史逐次查看或直接修正目前稿。' };
  if (currentRevisionRef === null || currentRevisionRef !== page.result_revision_ref)
    return { available: false, reason: '這輪之後已有新的修改，整輪撤回會蓋掉後來的工作，因此不提供；可在歷史查看或直接修正目前稿。' };
  return { available: true, runId: page.run_id, expectedResultRef: page.result_revision_ref };
}

export function projectRunMarkers(records: ChangeReadRecord[], before: JdView, after: JdView): RunMarkers {
  const markers: RunMarkers = { fields: {}, items: {} };
  const add = (map: RunMarkers['fields'], key: string, label: string, changeIndex: number) => {
    const values = map[key] ??= [];
    if (!values.some(marker => marker.changeIndex === changeIndex)) values.push({ label, changeIndex });
  };
  const target = (view: JdView, ref: string | null, label: string, index: number) => {
    const item = view.items.find(item => item.item_ref === ref);
    if (item && after.items.some(current => current.item_id === item.item_id)) add(markers.items, item.item_id, label, index);
    const field = view.fields.find(field => field.field_ref === ref);
    if (field && after.fields.some(current => current.key === field.key)) add(markers.fields, field.key, label, index);
  };
  for (const group of groupChanges(records)) {
    const header = group.header, index = header.change_index;
    const label = header.entity_kind === 'source_link' ? `本輪${header.kind === 'delete' ? '移除' : '更新'}依據`
      : header.entity_kind === 'task_capability' && header.kind === 'reorder' ? '本輪引用順序調整'
      : header.kind === 'move' ? '本輪移入' : `本輪${changeKinds[header.kind]}`;
    for (const record of group.records) {
      if (record.type === 'value') {
        const value = record.record, view = record.side === 'after' ? after : before;
        if (value.type === 'task_capability') target(view, value.task_ref, label, index);
        // A deleted item has no current editor target. Only its history is shown.
        if (record.side !== 'after') continue;
        if (value.type === 'item') target(after, value.item_ref, label, index);
        if (value.type === 'field' && (header.kind === 'create' || header.changed_fields.includes(value.name))) {
          const actual = after.fields.find(field => field.field_ref === value.field_ref);
          if (actual) add(markers.fields, fieldKey(actual.itemId, actual.name), label, index);
        }
      } else if (record.type === 'source_value') {
        target(record.side === 'after' ? after : before, record.record.target_ref, label, index);
      } else if (record.type === 'affected_task' && header.entity_kind === 'capability') {
        target(after, record.after_task_ref, '本輪引用內容修改', index);
      }
    }
  }
  return markers;
}
export function visibleRunMarkers(value: LoadedRunChange | null, scope: RunChangeScope,
  current: { view: JdView | null; values: Record<string, string>; form: unknown | null; needsReview: boolean; dirty: boolean }): RunMarkers | null {
  const selected = currentRunChanges(value, scope);
  if (!selected || selected.page.continuity !== 'continuous' || !selected.before || !selected.after
      || !current.view || selected.page.result_revision_ref !== current.view.revisionRef
      || current.needsReview || current.dirty || current.form !== null || Object.keys(current.values).length) return null;
  return projectRunMarkers(selected.page.records, selected.before, selected.after);
}
