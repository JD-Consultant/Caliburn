import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { ContainerRecord, ItemRecord, SectionRecord } from '../../src/jd_relational/generated/jd-read.ts';
import { type JdView, type ItemView, type FieldView, fieldKey } from '../src/lib/view.ts';
import { addressOf, commandForForm, commandForNewCapability, manageItemForm, newItemForm, parseItemForm, settleItemForm, structuralFields } from '../src/lib/item-form.ts';
import type { JsonValue } from '../src/lib/drafts.ts';
import { validateManualRequest } from '../src/lib/api.ts';

const uuid = (number: number) => `00000000-0000-4000-8000-${String(number).padStart(12, '0')}`;
function fixture(revision = 'original'): JdView {
  const ref = (name: string) => `${revision}:opaque:${name}`;
  const sections: SectionRecord[] = ['profile', 'purpose', 'duties_tasks', 'knowledge', 'skills', 'conditions']
    .map(section => ({ type: 'section', section_ref: ref(section), section_key: section as SectionRecord['section_key'], title: section }));
  const containers: ContainerRecord[] = [];
  const items: ItemView[] = []; const fields: FieldView[] = [];
  function container(key: string, section: string, kind: ItemRecord['kind'], owner: number | null = null) {
    containers.push({ type: 'container', container_ref: ref(key), section_ref: ref(section), child_kind: kind, owner_ref: owner === null ? null : ref(`item-${owner}`) });
  }
  function item(number: number, key: string, section: string, kind: ItemRecord['kind'], position: number, texts: Record<string, string | null>) {
    const row: ItemView = { type: 'item', item_ref: ref(`item-${number}`), item_id: uuid(number), section_ref: ref(section), container_ref: ref(key), kind, position, fields: [] };
    for (const [name, value] of Object.entries(texts)) {
      const field = { type: 'field' as const, item_ref: row.item_ref, section_ref: row.section_ref, field_ref: ref(`field-${number}-${name}`),
        itemId: row.item_id, name: name as FieldView['name'], value, key: fieldKey(row.item_id, name as FieldView['name']) };
      fields.push(field); row.fields.push(field);
    }
    items.push(row);
  }
  container('duties', 'duties_tasks', 'duty');
  item(1, 'duties', 'duties_tasks', 'duty', 0, { name: '維護', scope_text: '每月檢查；先隔離電源' });
  item(2, 'duties', 'duties_tasks', 'duty', 1, { name: '維護', scope_text: '僅軟體更新' });
  container('tasks-a', 'duties_tasks', 'task', 1); container('tasks-b', 'duties_tasks', 'task', 2);
  container('unassigned', 'duties_tasks', 'task');
  item(3, 'tasks-a', 'duties_tasks', 'task', 0, { name: '檢查', description: '保留🙂\n原條件' });
  item(4, 'tasks-a', 'duties_tasks', 'task', 1, { name: '檢查', description: '另一項工作，不可抹掉' });
  container('outcomes-a', 'duties_tasks', 'outcome', 3); container('requirements-a', 'duties_tasks', 'requirement', 3);
  container('outcomes-b', 'duties_tasks', 'outcome', 4); container('requirements-b', 'duties_tasks', 'requirement', 4);
  item(5, 'outcomes-a', 'duties_tasks', 'outcome', 0, { text: '檢查紀錄' });
  item(6, 'requirements-a', 'duties_tasks', 'requirement', 0, { text: '安全隔離\n功能確認' });
  container('knowledge', 'knowledge', 'knowledge'); container('skills', 'skills', 'skill');
  item(7, 'knowledge', 'knowledge', 'knowledge', 0, { name: '同名', description: '安全原理' });
  item(8, 'knowledge', 'knowledge', 'knowledge', 1, { name: '同名', description: '不同領域規則' });
  item(9, 'skills', 'skills', 'skill', 0, { name: null, description: '已知操作步驟，名稱未知' });
  container('conditions', 'conditions', 'work_environment');
  item(10, 'conditions', 'conditions', 'work_environment', 0, { text: '室內環境' });
  item(11, 'conditions', 'conditions', 'work_environment', 1, { text: '少量現場工作' });
  return { revisionRef: ref('revision'), sections, containers, items, fields, sources: [], relations: [{ type: 'task_capability',
    section_ref: ref('duties_tasks'), task_ref: ref('item-3'), capability_ref: ref('item-7'), capability_kind: 'knowledge', position: 0 }] };
}
const item = (view: JdView, number: number) => view.items.find(row => row.item_id === uuid(number))!;
const container = (view: JdView, suffix: string) => view.containers.find(row => row.container_ref.endsWith(`:${suffix}`))!;

test('new task keeps unknown name and all known details/capability identities in one command', () => {
  const view = fixture(); const form = newItemForm(view, container(view, 'unassigned'));
  form.fields.find(field => field.name === 'description')!.text = '目前已知🙂\n尚待命名';
  form.details = [
    { key: uuid(101), itemId: null, taskId: null, kind: 'outcome', baseValue: null, text: '一份報告' },
    { key: uuid(102), itemId: null, taskId: null, kind: 'outcome', baseValue: null, text: '保持可用狀態' },
    { key: uuid(103), itemId: null, taskId: null, kind: 'requirement', baseValue: null, text: '每月\n安全隔離後檢查' },
  ];
  form.capabilityIds = [uuid(7), uuid(8), uuid(9)];
  const before = structuredClone({ view, form }); const command = commandForForm(view, form);
  assert.equal(command?.tool, 'jd_create_task');
  if (command?.tool !== 'jd_create_task') assert.fail();
  assert.equal(command.arguments.name, null); assert.equal(command.arguments.description, '目前已知🙂\n尚待命名');
  assert.deepEqual(command.arguments.outcomes.map(row => row.text), ['一份報告', '保持可用狀態']);
  assert.deepEqual(command.arguments.requirements.map(row => row.text), ['每月\n安全隔離後檢查']);
  assert.deepEqual(command.arguments.capabilities.map(row => row.capability_ref), [7, 8, 9].map(number => item(view, number).item_ref));
  assert.deepEqual({ view, form }, before);
});

test('blank entered detail is not silently dropped or treated as saved content', () => {
  const view = fixture(); const form = newItemForm(view, container(view, 'unassigned'));
  form.fields[0].text = '已知任務';
  form.details = [{ key: uuid(101), itemId: null, taskId: null, kind: 'requirement', baseValue: null, text: '' }];
  const command = commandForForm(view, form);
  assert.equal(command?.tool, 'jd_create_task');
  if (command?.tool === 'jd_create_task') assert.deepEqual(command.arguments.requirements, [{ text: '', basis_refs: [] }]);
});

test('full task correction changes only explicit fields, details and capability choices', () => {
  const view = fixture(); const form = manageItemForm(view, item(view, 3), 'revise');
  form.fields.find(field => field.name === 'description')!.text = '新的描述\n保留條件';
  form.details = form.details.filter(row => row.itemId !== uuid(5));
  form.details.push({ key: uuid(101), itemId: null, taskId: uuid(3), kind: 'requirement', baseValue: null, text: '先核對授權' });
  form.capabilityIds = [uuid(8), uuid(9)];
  const command = commandForForm(view, form);
  if (command?.tool !== 'jd_revise_work') assert.fail();
  assert.deepEqual(command.arguments.changes.map(change => change.kind), ['set_field', 'remove_task_detail', 'add_task_detail', 'set_task_capability', 'set_task_capability', 'set_task_capability']);
  assert.ok(!JSON.stringify(command).includes(item(view, 4).item_ref));
  assert.ok(!JSON.stringify(command).includes('field-6-text'));
  const addition = command.arguments.changes.find(change => change.kind === 'add_task_detail');
  assert.equal(addition?.after_ref, item(view, 6).item_ref);
});

test('multi-select K/S is one correction and an unchanged selection has no save command', () => {
  const view = fixture(); const form = manageItemForm(view, item(view, 3), 'capabilities');
  assert.equal(commandForForm(view, form), null);
  form.capabilityIds = [uuid(8), uuid(9)];
  const command = commandForForm(view, form);
  if (command?.tool !== 'jd_revise_work') assert.fail();
  assert.equal(command.arguments.changes.length, 3);
  assert.deepEqual(command.arguments.changes.map(change => change.kind === 'set_task_capability' ? change.mode : null), ['unlink', 'link', 'link']);
});

test('stale draft rejects until explicit comparison, then uses current refs for stable IDs', () => {
  const old = fixture(); const next = fixture('next'); const form = manageItemForm(old, item(old, 3), 'revise');
  form.fields[0].text = '人工新名稱';
  assert.throws(() => commandForForm(next, form), /form_revision_changed/);
  form.baseRevisionRef = next.revisionRef;
  const command = commandForForm(next, form);
  assert.ok(JSON.stringify(command).includes('next:opaque:field-3-name'));
  assert.ok(!JSON.stringify(command).includes('original:opaque'));
});

test('revision must not require an unrelated old ordering anchor', () => {
  const old = fixture(); const next = fixture('next'); const form = manageItemForm(old, item(old, 4), 'revise');
  form.fields[0].text = '只修此任務'; form.baseRevisionRef = next.revisionRef;
  next.items = next.items.filter(row => ![uuid(3), uuid(5), uuid(6)].includes(row.item_id));
  next.containers = next.containers.filter(row => row.owner_ref !== 'next:opaque:item-3');
  next.fields = next.fields.filter(row => ![uuid(3), uuid(5), uuid(6)].includes(row.itemId!));
  next.relations = [];
  const command = commandForForm(next, form);
  assert.equal(command?.tool, 'jd_revise_work');
});

test('missing selected capability rejects the complete command; no same-name substitution', () => {
  const view = fixture(); const form = manageItemForm(view, item(view, 3), 'capabilities');
  form.capabilityIds = [uuid(999)];
  assert.throws(() => commandForForm(view, form), /invalid_form_target/);
});

test('task regrouping sends necessary task requirement and relevant duty summary together', () => {
  const view = fixture(); const task = item(view, 3); const destination = container(view, 'tasks-b');
  const form = manageItemForm(view, task, 'move'); form.container = addressOf(view, destination); form.afterId = null;
  form.fields = structuralFields(view, task, destination);
  form.fields.find(field => field.itemId === uuid(2) && field.name === 'scope_text')!.text = '軟體更新及指定檢查';
  form.details = [{ key: uuid(101), itemId: null, taskId: uuid(3), kind: 'requirement', baseValue: null, text: '每月檢查，先隔離電源' }];
  const command = commandForForm(view, form);
  if (command?.tool !== 'jd_move_item') assert.fail();
  assert.equal(command.arguments.target_ref, task.item_ref); assert.equal(command.arguments.destination_container_ref, destination.container_ref);
  assert.deepEqual(command.arguments.content_changes.map(change => change.kind), ['set_field', 'add_task_detail']);
  assert.ok(!JSON.stringify(command).includes(item(view, 4).item_ref));
});

test('duty deletion includes only explicit adjustments to surviving tasks', () => {
  const view = fixture(); const form = manageItemForm(view, item(view, 1), 'delete');
  form.fields.find(field => field.itemId === uuid(3) && field.name === 'description')!.text = '每月檢查；原必要內容仍適用';
  const command = commandForForm(view, form);
  if (command?.tool !== 'jd_delete_item') assert.fail();
  assert.equal(command.arguments.target_ref, item(view, 1).item_ref);
  assert.equal(command.arguments.content_changes.length, 1);
  assert.ok(!JSON.stringify(command).includes('field-4-'));
});

test('condition insert and reorder preserve the container kind and entry text', () => {
  const view = fixture(); const group = container(view, 'conditions'); const fresh = newItemForm(view, group);
  fresh.fields[0].text = '現場作業\n依必要安排';
  const inserted = commandForForm(view, fresh);
  if (inserted?.tool !== 'jd_insert_item') assert.fail();
  assert.equal(inserted.arguments.item.kind, 'condition'); assert.equal(inserted.arguments.item.container_ref, group.container_ref);
  const moved = manageItemForm(view, item(view, 11), 'move'); moved.afterId = null;
  const reordered = commandForForm(view, moved);
  if (reordered?.tool !== 'jd_move_item') assert.fail();
  assert.equal(reordered.arguments.destination_container_ref, group.container_ref);
  assert.deepEqual(reordered.arguments.content_changes, []);
});

test('persisted draft codec rejects unknown shape, invalid identity and duplicate entries', () => {
  const view = fixture(); const original = manageItemForm(view, item(view, 3), 'revise');
  assert.deepEqual(parseItemForm(structuredClone(original)), original);
  for (const mutation of [
    (form: Record<string, unknown>) => { form.extra = true; },
    (form: Record<string, unknown>) => { form.format = 2; },
    (form: Record<string, unknown>) => { form.itemId = 'same-name'; },
    (form: Record<string, unknown>) => { form.fields = [...original.fields, original.fields[0]]; },
    (form: Record<string, unknown>) => { form.capabilityIds = [uuid(7), uuid(7)]; },
    (form: Record<string, unknown>) => { form.details = [...original.details, original.details[0]]; },
  ]) {
    const value = structuredClone(original) as unknown as Record<string, unknown>; mutation(value);
    assert.equal(parseItemForm(value), null);
  }
});

test('persisted create form cannot silently discard an unexpected known field', () => {
  const view = fixture(); const form = newItemForm(view, container(view, 'unassigned'));
  form.fields[0].name = 'job_title'; form.fields[0].text = '不能被忽略的內容';
  assert.equal(parseItemForm(form), null);
});

test('nested shared definition is a separate command while the complete parent task stays intact', () => {
  const view = fixture(); const form = newItemForm(view, container(view, 'unassigned'));
  form.fields[1].text = '未提交的父任務';
  form.newCapability = { kind: 'knowledge', name: '', description: '概念已知\n名稱未定' };
  const before = structuredClone(form); const command = commandForNewCapability(view, form);
  if (command.tool !== 'jd_insert_item' || command.arguments.item.kind !== 'knowledge') assert.fail();
  assert.equal(command.arguments.item.name, null); assert.equal(command.arguments.item.description, '概念已知\n名稱未定');
  assert.equal(command.arguments.item.container_ref, container(view, 'knowledge').container_ref);
  assert.deepEqual(form, before);
  assert.throws(() => commandForForm(view, form), /invalid_form_target/);
});

test('confirmed original nested command clears only that candidate and never guesses a selected ID', () => {
  const view = fixture(); const form = newItemForm(view, container(view, 'unassigned'));
  form.fields[1].text = '父任務尚未提交'; form.capabilityIds = [uuid(7)];
  form.newCapability = { kind: 'skill', name: '操作', description: '受限範圍的操作' };
  const original = structuredClone(form); const command = commandForNewCapability(view, form);
  const result = settleItemForm(form as unknown as JsonValue, command);
  assert.deepEqual(result, { ...original, newCapability: null });
  assert.deepEqual(form, original);
  assert.deepEqual(settleItemForm(result, command), result);
});

test('late changed nested content or a different command is never retired by an old receipt', () => {
  const view = fixture(); const form = newItemForm(view, container(view, 'unassigned'));
  form.newCapability = { kind: 'skill', name: '操作', description: '第一份內容' };
  const command = commandForNewCapability(view, form);
  form.newCapability.description = '較晚改動';
  assert.deepEqual(settleItemForm(form as unknown as JsonValue, command), form);
  assert.deepEqual(settleItemForm(form as unknown as JsonValue, { tool: 'jd_set_text', arguments: {
    target_field_ref: item(view, 3).fields[0].field_ref, text: '操作', basis_refs: [] } }), form);
  assert.deepEqual(settleItemForm({ unknown: '保留無法辨认表單' }, command), { unknown: '保留無法辨认表單' });
});

test('every insert form and each management command validates against the original shared command schema', () => {
  const view = fixture();
  view.containers.push({ type: 'container', section_ref: 'original:opaque:profile', container_ref: 'original:opaque:collaborators', owner_ref: null, child_kind: 'collaborator' });
  const fresh = ['duties', 'collaborators', 'knowledge', 'skills', 'outcomes-a', 'requirements-a', 'conditions', 'unassigned'].map(key => {
    const form = newItemForm(view, container(view, key));
    form.fields.at(-1)!.text = '已知完整內容\n未知不補造';
    return commandForForm(view, form)!;
  });
  const revise = manageItemForm(view, item(view, 3), 'revise'); revise.fields[1].text = '明示修正';
  const move = manageItemForm(view, item(view, 3), 'move'); move.container = addressOf(view, container(view, 'unassigned')); move.afterId = null;
  const remove = manageItemForm(view, item(view, 5), 'delete');
  const choose = manageItemForm(view, item(view, 3), 'capabilities'); choose.capabilityIds = [uuid(8)];
  for (const command of [...fresh, ...[revise, move, remove, choose].map(form => commandForForm(view, form)!)]) {
    assert.doesNotThrow(() => validateManualRequest({ operation_id: uuid(200), base_revision_ref: view.revisionRef, command }));
  }
});
