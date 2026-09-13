/** Real React/MUI static HTML. Effects, clicks, scrolling and browser I/O are not exercised. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type RunChangesPanelType from '../src/components/RunChangesPanel.tsx';
import type JdEditorType from '../src/components/JdEditor.tsx';
import type ChangeDetailsType from '../src/components/ChangeDetails.tsx';
import type { ChatRunChangePage } from '../../src/jd_relational/generated/jd-chat-http.ts';
import type { ChangeReadRecord } from '../../src/jd_relational/generated/jd-read.ts';
import { projectView, type JdView } from '../src/lib/view.ts';
import { visibleRunMarkers, type LoadedRunChange } from '../src/lib/run-changes.ts';

const require = createRequire(import.meta.url);
const babel = require('next/dist/compiled/babel/core');
const modules = new Map<string, { exports: Record<string, unknown> }>();
function load(file: string): Record<string, unknown> {
  const cached = modules.get(file); if (cached) return cached.exports;
  const native = createRequire(file), module = { exports: {} as Record<string, unknown> };
  modules.set(file, module);
  const output = babel.transformSync(readFileSync(file, 'utf8'), { filename: file, babelrc: false, configFile: false,
    presets: [[require('next/babel'), { 'preset-env': { modules: 'commonjs' }, 'preset-react': { runtime: 'automatic' } }]] }).code;
  const local = (name: string) => {
    if (name.startsWith('.')) {
      const resolved = path.resolve(path.dirname(file), name);
      if (existsSync(`${resolved}.tsx`)) return load(`${resolved}.tsx`);
      if (existsSync(`${resolved}.ts`)) return native(`${resolved}.ts`);
    }
    return native(name);
  };
  new Function('require', 'module', 'exports', output)(local, module, module.exports);
  return module.exports;
}
const component = (name: string) => load(fileURLToPath(new URL(`../src/components/${name}.tsx`, import.meta.url))).default;
const RunChangesPanel = component('RunChangesPanel') as typeof RunChangesPanelType;
const JdEditor = component('JdEditor') as typeof JdEditorType;
const ChangeDetails = component('ChangeDetails') as typeof ChangeDetailsType;

function fixture() {
  const view = (revision: string, includeTask: boolean): JdView => {
    const section = { type: 'section' as const, section_ref: `${revision}-section`, section_key: 'duties_tasks' as const, title: '職責與任務' };
    const container = { type: 'container' as const, container_ref: `${revision}-duties`, section_ref: section.section_ref, owner_ref: null, child_kind: 'duty' as const };
    const duty = { type: 'item' as const, item_ref: `${revision}-duty`, item_id: 'duty-id', section_ref: section.section_ref, container_ref: container.container_ref, kind: 'duty' as const, position: 0 };
    const tasks = { type: 'container' as const, container_ref: `${revision}-tasks`, section_ref: section.section_ref, owner_ref: duty.item_ref, child_kind: 'task' as const };
    const task = { type: 'item' as const, item_ref: `${revision}-task`, item_id: 'task-id', section_ref: section.section_ref, container_ref: tasks.container_ref, kind: 'task' as const, position: 0 };
    const records = [section, container, duty, tasks,
      { type: 'field' as const, field_ref: `${revision}-duty-name`, section_ref: section.section_ref, item_ref: duty.item_ref, name: 'name' as const, value: '舊維護職責' },
      ...(includeTask ? [task, { type: 'field' as const, field_ref: `${revision}-task-name`, section_ref: section.section_ref, item_ref: task.item_ref, name: 'name' as const, value: '即將刪除的任務' },
        { type: 'field' as const, field_ref: `${revision}-task-text`, section_ref: section.section_ref, item_ref: task.item_ref, name: 'description' as const, value: '原始完整責任\n僅限合約系統🙂' }] : [])];
    return projectView({ format_version: 2, view: 'history', access: 'history', revision_ref: revision, records,
      start_index: 0, total_records: records.length, has_more: false, next_cursor: null, oversized_unit: false });
  };
  const before = view('S', true), after = view('E', false), task = before.items.find(row => row.item_id === 'task-id')!;
  const records: ChangeReadRecord[] = [
    { type: 'change', change_index: 0, kind: 'delete', entity_kind: 'task', before_exists: true, after_exists: false, changed_fields: ['name', 'description'] },
    { type: 'value', change_index: 0, side: 'before', record: task },
    ...task.fields.map(record => ({ type: 'value' as const, change_index: 0, side: 'before' as const, record })),
  ];
  const page: ChatRunChangePage = { format_version: 1, view: 'run_change', access: 'history', dataset_id: 'dataset', document_id: 'doc', run_id: 'A',
    capture_ref: 'opaque', effects_state: 'settled', continuity: 'continuous', captured_operation_count: 1, base_revision_ref: 'S', result_revision_ref: 'E', records,
    total_records: records.length, total_changes: 1, start_index: 0, has_more: false, next_cursor: null, oversized_unit: false };
  const scope = { api: {}, datasetId: 'dataset', documentId: 'doc', key: 'A' };
  const selection: LoadedRunChange = { ...scope, page, before, after };
  return { before, after, page, scope, selection };
}
const panel = (selection: LoadedRunChange, currentRevisionRef = 'E') => renderToStaticMarkup(React.createElement(RunChangesPanel,
  { selection, currentRevisionRef, loading: false, error: null, onRetry() {} }));

test('deleted full text and old owner are visible outside every collapsed details', () => {
  const html = panel(fixture().selection);
  const visible = html.replace(/<details\b[^>]*>[\s\S]*?<\/details>/g, '');
  assert.match(visible, /已刪除的原內容/); assert.match(visible, /原所屬：.*舊維護職責/);
  assert.match(visible, /即將刪除的任務/); assert.match(visible, /原始完整責任\n僅限合約系統🙂/);
  assert.doesNotMatch(visible, /接受|核准|href="#jd-item-task-id"/);
});
test('pending zero does not claim no changes and changed-back run retains saving fact', () => {
  const { selection } = fixture();
  const pending = panel({ ...selection, before: null, after: null, page: { ...selection.page, effects_state: 'unconfirmed', continuity: 'none',
    captured_operation_count: 0, base_revision_ref: null, result_revision_ref: null, records: [], total_changes: 0, total_records: 0 } });
  assert.match(pending, /尚未全部確認/); assert.doesNotMatch(pending, /沒有修改 JD/);
  const reverted = panel({ ...selection, page: { ...selection.page, captured_operation_count: 2, records: [], total_records: 0, total_changes: 0 } });
  assert.match(reverted, /沒有淨變更.*保存/); assert.match(reverted, /2.*次已保存修改/);
});
test('discontinuous run names the limitation and keeps original operation path', () => {
  const { selection } = fixture();
  const html = panel({ ...selection, before: null, after: null, page: { ...selection.page, continuity: 'discontinuous',
    base_revision_ref: null, result_revision_ref: null, records: [], total_changes: 0, total_records: 0 } });
  assert.match(html, /夾有其他修改/); assert.match(html, /各次實際改動/);
  assert.doesNotMatch(html, /沒有修改 JD|已刪除的原內容/);
});
test('later current version preserves historical deletion but explicitly stops current labels', () => {
  const html = panel(fixture().selection, 'manual-later');
  assert.match(html, /目前稿版本不同/); assert.match(html, /停用目前欄位標記/); assert.match(html, /原始完整責任/);
});
test('actual editor labels are absent for late A, new B or unsaved manual candidate', () => {
  const { selection, scope, before } = fixture();
  const value = { ...selection, after: before, page: { ...selection.page, result_revision_ref: 'S', records: [
    { type: 'change' as const, change_index: 0, kind: 'update' as const, entity_kind: 'task' as const, before_exists: true, after_exists: true, changed_fields: ['name' as const] },
    { type: 'value' as const, change_index: 0, side: 'after' as const, record: before.items.find(row => row.item_id === 'task-id')! },
  ] } };
  const current = { view: before, values: {}, form: null, needsReview: false, dirty: false };
  const html = (readScope = scope, viewState = current) => renderToStaticMarkup(React.createElement(JdEditor, {
    view: before, values: viewState.values, disabled: false, form: null, onFormChange() {}, onField() {}, onComposition() {}, async onCommand() {},
    markers: visibleRunMarkers(value, readScope, viewState),
  }));
  assert.match(html(), /本輪修改.*查看/);
  assert.doesNotMatch(html({ ...scope, key: 'new-B' }), /本輪修改/);
  assert.doesNotMatch(html({ ...scope, api: {} }), /本輪修改/);
  assert.doesNotMatch(html(scope, { ...current, dirty: true }), /本輪修改/);
});
test('shared renderer retains source identity/basis/order and affected tasks with placements', () => {
  const { before, after } = fixture();
  const records: ChangeReadRecord[] = [
    { type: 'change', change_index: 0, kind: 'reorder', entity_kind: 'source_link', before_exists: true, after_exists: true, changed_fields: ['position', 'basis_digest'] },
    { type: 'source_value', change_index: 0, side: 'before', record: { type: 'source', section_ref: 's', target_ref: 'S-task', related_capability_ref: null,
      source_ref: 'exact-source-identity', basis_status: 'needs_recheck', readability: 'not_checked' }, basis_digest: 'exact-basis', position: 3 },
    { type: 'source_placement', change_index: 0, side: 'after', target_ref: 'E-duty', related_capability_ref: null, previous_source_ref: 'exact-previous', next_source_ref: 'exact-next' },
    { type: 'affected_task', change_index: 0, before_task_ref: 'S-task', after_task_ref: null },
  ];
  const html = renderToStaticMarkup(React.createElement(ChangeDetails, { records, before, after }));
  for (const text of ['exact-source-identity', 'exact-basis', 'exact-previous', 'exact-next', '影響任務', '即將刪除的任務', '原話回查尚未接合']) assert.ok(html.includes(text), text);
  assert.match(html, /order[^<]*3/);
});
test('deleted identical requirements under identical tasks remain distinguishable by their duty path', () => {
  function removedRequirement(which: 'a' | 'b') {
    const side = (revision: string, deleted: string | null) => {
      const r = (key: string) => `${revision}-${key}`;
      const section = { type: 'section' as const, section_ref: r('section'), section_key: 'duties_tasks' as const, title: '職責與任務' };
      const root = { type: 'container' as const, container_ref: r('duties'), section_ref: section.section_ref, owner_ref: null, child_kind: 'duty' as const };
      const records: import('../../src/jd_relational/generated/jd-read.ts').ReadRecord[] = [section, root];
      for (const [index, key] of ['a', 'b'].entries()) {
        const duty = { type: 'item' as const, item_id: `${key}-duty`, item_ref: r(`${key}-duty`), section_ref: section.section_ref, container_ref: root.container_ref, kind: 'duty' as const, position: index };
        const tasks = { type: 'container' as const, container_ref: r(`${key}-tasks`), section_ref: section.section_ref, owner_ref: duty.item_ref, child_kind: 'task' as const };
        const task = { type: 'item' as const, item_id: `${key}-task`, item_ref: r(`${key}-task`), section_ref: section.section_ref, container_ref: tasks.container_ref, kind: 'task' as const, position: 0 };
        const requirements = { type: 'container' as const, container_ref: r(`${key}-requirements`), section_ref: section.section_ref, owner_ref: task.item_ref, child_kind: 'requirement' as const };
        records.push(duty, tasks, task, requirements,
          { type: 'field', field_ref: r(`${key}-duty-name`), section_ref: section.section_ref, item_ref: duty.item_ref, name: 'name', value: `職責 ${key.toUpperCase()}` },
          { type: 'field', field_ref: r(`${key}-task-name`), section_ref: section.section_ref, item_ref: task.item_ref, name: 'name', value: '驗證' });
        if (deleted !== key) records.push({ type: 'item', item_id: `${key}-requirement`, item_ref: r(`${key}-requirement`), section_ref: section.section_ref,
          container_ref: requirements.container_ref, kind: 'requirement', position: 0 },
          { type: 'field', field_ref: r(`${key}-text`), section_ref: section.section_ref, item_ref: r(`${key}-requirement`), name: 'text', value: '完成檢查' });
      }
      return projectView({ format_version: 2, view: 'history', access: 'history', revision_ref: revision, records, start_index: 0,
        total_records: records.length, has_more: false, next_cursor: null, oversized_unit: false });
    };
    const before = side('S', null), after = side('E', which), removed = before.items.find(item => item.item_id === `${which}-requirement`)!;
    const records: ChangeReadRecord[] = [
      { type: 'change', change_index: 0, kind: 'delete', entity_kind: 'detail', before_exists: true, after_exists: false, changed_fields: ['text'] },
      { type: 'value', change_index: 0, side: 'before', record: removed },
      ...removed.fields.map(record => ({ type: 'value' as const, change_index: 0, side: 'before' as const, record })),
    ];
    return renderToStaticMarkup(React.createElement(ChangeDetails, { records, before, after, compact: true }));
  }
  const a = removedRequirement('a'), b = removedRequirement('b');
  assert.notEqual(a, b);
  const visibleA = a.replace(/<details\b[^>]*>[\s\S]*?<\/details>/g, '');
  const visibleB = b.replace(/<details\b[^>]*>[\s\S]*?<\/details>/g, '');
  assert.match(visibleA, /職責 A/); assert.doesNotMatch(visibleA, /職責 B/);
  assert.match(visibleB, /職責 B/); assert.doesNotMatch(visibleB, /職責 A/);
  assert.match(visibleA, /驗證/); assert.match(visibleA, /完成檢查/);
});
