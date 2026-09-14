import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { ChatRunState, ChatRunChangePage } from '../../src/jd_relational/generated/jd-chat-http.ts';
import type { ChangeReadRecord } from '../../src/jd_relational/generated/jd-read.ts';
import { fieldKey, type JdView } from '../src/lib/view.ts';
import { matchingRun, runChangeKey, groupChanges, projectRunMarkers, visibleRunMarkers, currentRunChanges, runChangeSummary, undoOffer } from '../src/lib/run-changes.ts';

const api = {};
const scope = { api, datasetId: 'dataset', documentId: 'doc', key: 'capture-key' };
const emptyView = (revisionRef: string): JdView => ({ revisionRef, sections: [], items: [], fields: [], containers: [], relations: [], sources: [] });
const state = (runId = 'A', effects = 'unconfirmed', operations: string[] = ['op-a']): ChatRunState => ({
  dataset_id: 'dataset', document_id: 'doc', run_id: runId, run_status: 'running', input_state: 'saved',
  response_message_id: null, stop_requested: false, write_state: {}, jd_effects: { state: effects,
    results: operations.map(operation_ref => ({ status: 'committed', operation_ref })) },
} as ChatRunState);
const page = (patch: Partial<ChatRunChangePage> = {}): ChatRunChangePage => ({ format_version: 1, view: 'run_change', access: 'history',
  dataset_id: 'dataset', document_id: 'doc', run_id: 'A', capture_ref: 'opaque', effects_state: 'settled', continuity: 'continuous',
  captured_operation_count: 2, base_revision_ref: 'S', result_revision_ref: 'E', records: [], total_changes: 0, total_records: 0,
  start_index: 0, has_more: false, next_cursor: null, oversized_unit: false, ...patch } as ChatRunChangePage);
const loaded = (value = page()) => ({ ...scope, page: value, before: emptyView('S'), after: emptyView('E') });
const clean = { view: emptyView('E'), values: {}, form: null, needsReview: false, dirty: false };

test('old A never supplies labels while B is selected or its original request is pending', () => {
  assert.equal(matchingRun({ run: state('A'), runId: 'B' }, null, scope), null);
  assert.equal(matchingRun({ run: state('A'), runId: 'A' }, 'B', scope), null);
  assert.equal(matchingRun({ run: state('A'), runId: 'A' }, null, { ...scope, documentId: 'other' }), null);
  assert.equal(matchingRun({ run: state('A'), runId: 'A' }, null, { ...scope, datasetId: 'other' }), null);
  assert.equal(matchingRun({ run: state('A'), runId: 'A' }, 'A', scope)?.run_id, 'A');
});
test('polls with identical committed set do not request another capture; settled change does', () => {
  assert.equal(runChangeKey(state('A', 'unconfirmed', [])), null);
  assert.equal(runChangeKey(state('A', 'unconfirmed', ['b', 'a'])), runChangeKey(state('A', 'unconfirmed', ['a', 'b'])));
  assert.notEqual(runChangeKey(state()), runChangeKey(state('A', 'settled')));
  assert.notEqual(runChangeKey(state()), runChangeKey(state('A', 'unconfirmed', ['op-a', 'op-b'])));
});
test('late capture A is hidden for new key, API, dataset or document before effects run', () => {
  assert.equal(currentRunChanges(loaded(), scope)?.page.capture_ref, 'opaque');
  for (const changed of [{ key: 'new-B' }, { api: {} }, { datasetId: 'new' }, { documentId: 'other' }])
    assert.equal(currentRunChanges(loaded(), { ...scope, ...changed }), null);
});
test('current markers require exact E and a clean saved view in the final render', () => {
  assert.ok(visibleRunMarkers(loaded(), scope, clean));
  for (const changed of [{ view: emptyView('later-manual') }, { values: { typed: 'B' } }, { form: {} }, { needsReview: true }, { dirty: true }])
    assert.equal(visibleRunMarkers(loaded(), scope, { ...clean, ...changed }), null);
  assert.equal(visibleRunMarkers(loaded(page({ continuity: 'discontinuous', base_revision_ref: null, result_revision_ref: null })), scope, clean), null);
});
test('empty pending capture never claims no modification; changed back preserves saving facts', () => {
  assert.match(runChangeSummary(page({ continuity: 'none', captured_operation_count: 0, effects_state: 'unconfirmed' })), /尚未全部確認/);
  assert.doesNotMatch(runChangeSummary(page({ continuity: 'none', captured_operation_count: 0, effects_state: 'unconfirmed' })), /沒有修改/);
  assert.match(runChangeSummary(page({ continuity: 'none', captured_operation_count: 0 })), /沒有修改 JD/);
  assert.match(runChangeSummary(page()), /沒有淨變更.*保存/);
});

function item(view: JdView, id: string, ref: string, name: string, kind: 'task' | 'knowledge' = 'task') {
  const row = { type: 'item' as const, item_id: id, item_ref: ref, section_ref: 's', container_ref: 'c', kind, position: 0, fields: [] };
  const field = { type: 'field' as const, field_ref: `${ref}-name`, section_ref: 's', item_ref: ref, itemId: id,
    name: 'name' as const, value: name, key: fieldKey(id, 'name') };
  view.items.push({ ...row, fields: [field] }); view.fields.push(field); return { row, field };
}
test('grouping retains all values, affected tasks, source metadata and placements without diffing', () => {
  const records: ChangeReadRecord[] = [
    { type: 'change', change_index: 4, kind: 'update', entity_kind: 'source_link', before_exists: true, after_exists: true, changed_fields: ['basis_digest'] },
    { type: 'source_value', change_index: 4, side: 'before', record: { type: 'source', section_ref: 's', target_ref: 't', related_capability_ref: null, source_ref: 'r', basis_status: 'current', readability: 'not_checked' }, basis_digest: 'a', position: 0 },
    { type: 'source_placement', change_index: 4, side: 'after', target_ref: 't', related_capability_ref: null, previous_source_ref: null, next_source_ref: 'next' },
    { type: 'affected_task', change_index: 4, before_task_ref: 'old', after_task_ref: 'new' },
  ];
  assert.deepEqual(groupChanges(records)[0].records, records);
});
test('stable IDs keep identical task names separate; only changed fields receive a marker', () => {
  const before = emptyView('S'), after = emptyView('E');
  item(before, 'id-one', 'old-one', '同名');
  const one = item(after, 'id-one', 'new-one', '同名'), two = item(after, 'id-two', 'new-two', '同名');
  const records: ChangeReadRecord[] = [
    { type: 'change', change_index: 0, kind: 'update', entity_kind: 'task', before_exists: true, after_exists: true, changed_fields: ['name'] },
    { type: 'value', change_index: 0, side: 'after', record: one.row },
    { type: 'value', change_index: 0, side: 'after', record: one.field },
  ];
  const markers = projectRunMarkers(records, before, after);
  assert.equal(markers.items['id-one'][0].changeIndex, 0);
  assert.equal(markers.fields[one.field.key][0].label, '本輪修改');
  assert.equal(markers.items['id-two'], undefined); assert.equal(markers.fields[two.field.key], undefined);
});
test('shared definition, unlinked relation and removed source mark exact surviving targets only', () => {
  const before = emptyView('S'), after = emptyView('E');
  item(before, 'task', 'old-task', '任務'); item(after, 'task', 'new-task', '任務');
  item(after, 'other', 'new-other', '任務');
  const capability = item(after, 'knowledge', 'new-knowledge', '規則', 'knowledge');
  const records: ChangeReadRecord[] = [
    { type: 'change', change_index: 0, kind: 'update', entity_kind: 'capability', before_exists: true, after_exists: true, changed_fields: ['name'] },
    { type: 'value', change_index: 0, side: 'after', record: capability.row },
    { type: 'affected_task', change_index: 0, before_task_ref: 'old-task', after_task_ref: 'new-task' },
    { type: 'change', change_index: 1, kind: 'unlink', entity_kind: 'task_capability', before_exists: true, after_exists: false, changed_fields: ['task_ref', 'capability_ref'] },
    { type: 'value', change_index: 1, side: 'before', record: { type: 'task_capability', task_ref: 'old-task', capability_ref: 'old-k', capability_kind: 'knowledge', section_ref: 's', position: 0 } },
    { type: 'change', change_index: 2, kind: 'delete', entity_kind: 'source_link', before_exists: true, after_exists: false, changed_fields: ['source_ref'] },
    { type: 'source_value', change_index: 2, side: 'before', record: { type: 'source', target_ref: 'old-task', related_capability_ref: null, section_ref: 's', source_ref: 'evidence', basis_status: 'current', readability: 'not_checked' }, position: 0, basis_digest: 'a' },
  ];
  const markers = projectRunMarkers(records, before, after);
  assert.deepEqual(markers.items.task.map(marker => marker.changeIndex), [0, 1, 2]);
  assert.equal(markers.items.other, undefined);
});
test('profile marker only selects the named field and leaves other profile fields unmarked', () => {
  const before = emptyView('S'), after = emptyView('E');
  for (const name of ['job_title', 'organization_unit'] as const) after.fields.push({ type: 'field', field_ref: name, item_ref: null,
    itemId: null, key: fieldKey(null, name), name, value: '新文字', section_ref: 'profile' });
  const records: ChangeReadRecord[] = [
    { type: 'change', change_index: 0, kind: 'update', entity_kind: 'profile', before_exists: true, after_exists: true, changed_fields: ['job_title'] },
    ...after.fields.map(record => ({ type: 'value' as const, change_index: 0, side: 'after' as const, record })),
  ];
  const markers = projectRunMarkers(records, before, after);
  assert.deepEqual(Object.keys(markers.fields), [fieldKey(null, 'job_title')]);
  assert.deepEqual(markers.items, {});
});
test('move and reorder labels attach to the exact current item without calling text a rewrite', () => {
  const before = emptyView('S'), after = emptyView('E');
  const first = item(after, 'first', 'new-first', '同名'), second = item(after, 'second', 'new-second', '同名');
  const records: ChangeReadRecord[] = [
    { type: 'change', change_index: 0, kind: 'move', entity_kind: 'task', before_exists: true, after_exists: true, changed_fields: ['container_ref'] },
    { type: 'value', change_index: 0, side: 'after', record: first.row }, { type: 'value', change_index: 0, side: 'after', record: first.field },
    { type: 'change', change_index: 1, kind: 'reorder', entity_kind: 'task', before_exists: true, after_exists: true, changed_fields: ['position'] },
    { type: 'value', change_index: 1, side: 'after', record: second.row },
  ];
  const markers = projectRunMarkers(records, before, after);
  assert.equal(markers.items.first[0].label, '本輪移入');
  assert.equal(markers.items.second[0].label, '本輪順序調整');
  assert.deepEqual(markers.fields, {});
});
test('deleted item never produces a current editor marker, even when another item has the same text', () => {
  const before = emptyView('S'), after = emptyView('E');
  const removed = item(before, 'deleted', 'old', '同名'); item(after, 'kept', 'new', '同名');
  const records: ChangeReadRecord[] = [
    { type: 'change', change_index: 0, kind: 'delete', entity_kind: 'task', before_exists: true, after_exists: false, changed_fields: ['name'] },
    { type: 'value', change_index: 0, side: 'before', record: removed.row },
    { type: 'value', change_index: 0, side: 'before', record: removed.field },
  ];
  assert.deepEqual(projectRunMarkers(records, before, after), { fields: {}, items: {} });
});

test('undoing a whole turn is offered only when it can be taken back as one range', () => {
  const settled = (overrides: object = {}) => ({ format_version: 1, view: 'run_change', access: 'history',
    dataset_id: 'dataset', document_id: 'doc', run_id: 'turn-A', capture_ref: 'capture',
    effects_state: 'settled', continuity: 'continuous', captured_operation_count: 2,
    base_revision_ref: 'before', result_revision_ref: 'after', records: [], start_index: 0,
    total_records: 0, total_changes: 3, has_more: false, next_cursor: null, oversized_unit: false,
    ...overrides }) as ChatRunChangePage;

  assert.deepEqual(undoOffer(settled(), 'after'),
    { available: true, runId: 'turn-A', expectedResultRef: 'after' });
  // The document moved on: undoing would discard whatever came after.
  assert.equal(undoOffer(settled(), 'later-head').available, false);
  assert.equal(undoOffer(settled(), null).available, false);
  // Nothing finished, nothing net, or interleaved with other edits.
  assert.equal(undoOffer(settled({ effects_state: 'unconfirmed' }), 'after').available, false);
  assert.equal(undoOffer(settled({ total_changes: 0 }), 'after').available, false);
  assert.equal(undoOffer(settled({ continuity: 'none', result_revision_ref: null }), 'after').available, false);
  assert.equal(undoOffer(settled({ continuity: 'discontinuous' }), 'after').available, false);
  // Every refusal explains itself rather than leaving a dead button.
  for (const page of [settled({ effects_state: 'unconfirmed' }), settled({ total_changes: 0 }),
                      settled({ continuity: 'discontinuous' })]) {
    const offer = undoOffer(page, 'after');
    assert.equal(offer.available, false);
    assert.ok(!offer.available && offer.reason.length > 0);
  }
});
