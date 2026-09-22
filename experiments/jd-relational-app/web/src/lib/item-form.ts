import type { ContainerRecord, FieldRecord, ItemRecord, SectionRecord } from '../../../src/jd_relational/generated/jd-read.ts';
import type { AddTaskDetailChange, ManualCommand, SetFieldChange } from '../../../src/jd_relational/generated/jd-manual-http.ts';
import { fieldLabels, kindLabels, type FieldView, type ItemView, type JdView } from './view.ts';
import type { JsonValue } from './drafts.ts';
export interface ContainerAddress {
  sectionKey: SectionRecord['section_key']; ownerId: string | null; kind: ItemRecord['kind'];
}
export interface FormField { itemId: string | null; name: FieldRecord['name']; baseValue: string | null; text: string }
export interface FormDetail {
  key: string; itemId: string | null; taskId: string | null;
  kind: 'outcome' | 'requirement'; baseValue: string | null; text: string;
}
export interface ItemForm {
  format: 1; mode: 'create' | 'revise' | 'move' | 'delete' | 'capabilities';
  itemId: string | null; container: ContainerAddress; afterId: string | null;
  baseRevisionRef: string; baselineText: string;
  fields: FormField[]; details: FormDetail[]; originalDetailIds: string[];
  capabilityIds: string[]; originalCapabilityIds: string[];
  newCapability: { kind: 'knowledge' | 'skill'; name: string; description: string } | null;
}
export type CommandOptions = { preserveForm?: boolean };
export interface ItemDialogProps {
  view: JdView; form: unknown | null; disabled: boolean;
  onFormChange: (value: unknown | null) => void;
  onComposition: (active: boolean) => void;
  onCommand: (command: ManualCommand, options?: CommandOptions) => Promise<void>;
}
const idPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const sectionKeys = ['profile', 'purpose', 'duties_tasks', 'knowledge', 'skills', 'conditions'];
const modes = ['create', 'revise', 'move', 'delete', 'capabilities'];
function object(value: unknown, keys: string[]): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
const id = (value: unknown): value is string => typeof value === 'string' && idPattern.test(value);
const maybeId = (value: unknown) => value === null || id(value);
const maybeText = (value: unknown) => value === null || typeof value === 'string';
function ids(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(id) && new Set(value).size === value.length;
}
/** This validates a local UI draft, not JD content or writable authority. */
export function parseItemForm(value: unknown): ItemForm | null {
  if (!object(value, ['format', 'mode', 'itemId', 'container', 'afterId', 'baseRevisionRef', 'baselineText',
    'fields', 'details', 'originalDetailIds', 'capabilityIds', 'originalCapabilityIds', 'newCapability']) || value.format !== 1
    || typeof value.mode !== 'string' || !modes.includes(value.mode) || !maybeId(value.itemId)
    || !maybeId(value.afterId) || typeof value.baseRevisionRef !== 'string' || !value.baseRevisionRef
    || typeof value.baselineText !== 'string' || !object(value.container, ['sectionKey', 'ownerId', 'kind'])
    || typeof value.container.sectionKey !== 'string' || !sectionKeys.includes(value.container.sectionKey)
    || !maybeId(value.container.ownerId) || typeof value.container.kind !== 'string'
    || !Object.hasOwn(kindLabels, value.container.kind)
    || !ids(value.originalDetailIds) || !ids(value.capabilityIds) || !ids(value.originalCapabilityIds)
    || !Array.isArray(value.fields) || !Array.isArray(value.details)) return null;
  if (value.newCapability !== null && (!object(value.newCapability, ['kind', 'name', 'description'])
    || !['knowledge', 'skill'].includes(String(value.newCapability.kind))
    || typeof value.newCapability.name !== 'string' || typeof value.newCapability.description !== 'string')) return null;
  if (value.fields.some(field => !object(field, ['itemId', 'name', 'baseValue', 'text'])
    || !maybeId(field.itemId) || typeof field.name !== 'string' || !Object.hasOwn(fieldLabels, field.name)
    || !maybeText(field.baseValue) || typeof field.text !== 'string')) return null;
  if (value.details.some(detail => !object(detail, ['key', 'itemId', 'taskId', 'kind', 'baseValue', 'text'])
    || !id(detail.key) || !maybeId(detail.itemId) || !maybeId(detail.taskId)
    || !['outcome', 'requirement'].includes(String(detail.kind))
    || !maybeText(detail.baseValue) || typeof detail.text !== 'string')) return null;
  const form = value as unknown as ItemForm;
  if ((form.mode === 'create') !== (form.itemId === null)
    || new Set(form.fields.map(field => JSON.stringify([field.itemId, field.name]))).size !== form.fields.length
    || new Set(form.details.map(detail => detail.key)).size !== form.details.length
    || new Set(form.details.filter(detail => detail.itemId !== null).map(detail => detail.itemId)).size
      !== form.details.filter(detail => detail.itemId !== null).length) return null;
  if (form.mode === 'create') {
    const names = newFieldNames(form.container.kind);
    if (form.fields.length !== names.length || names.some(name => !form.fields.some(field => field.name === name))
      || form.fields.some(field => field.itemId !== null || field.baseValue !== null)
      || form.originalDetailIds.length || form.originalCapabilityIds.length
      || form.details.some(detail => detail.itemId !== null || detail.taskId !== null || detail.baseValue !== null)
      || (form.container.kind !== 'task' && (form.details.length || form.capabilityIds.length || form.newCapability !== null))) return null;
  } else {
    if (form.fields.some(field => field.itemId === null) || form.details.some(detail => detail.taskId === null)
      || form.details.some(detail => detail.itemId !== null && !form.originalDetailIds.includes(detail.itemId))) return null;
    if (form.mode === 'revise' && (form.container.kind !== 'task' || form.fields.length !== 2
      || !['name', 'description'].every(name => form.fields.some(field => field.name === name && field.itemId === form.itemId))
      || form.details.some(detail => detail.taskId !== form.itemId))) return null;
    if (form.mode === 'capabilities' && (form.container.kind !== 'task' || form.fields.length || form.details.length || form.originalDetailIds.length)) return null;
    if ((form.mode === 'move' || form.mode === 'delete') && (form.details.some(detail => detail.itemId !== null)
      || form.originalDetailIds.length || form.newCapability !== null
      || JSON.stringify(form.capabilityIds) !== JSON.stringify(form.originalCapabilityIds))) return null;
  }
  return form;
}
export function itemText(item: ItemView): string {
  return item.fields.find(field => field.name === 'name')?.value
    || item.fields.find(field => field.name === 'description' || field.name === 'scope_text' || field.name === 'text')?.value
    || `尚未命名的${kindLabels[item.kind]}`;
}
export function addressOf(view: JdView, container: ContainerRecord): ContainerAddress {
  const section = view.sections.find(section => section.section_ref === container.section_ref);
  const owner = container.owner_ref === null ? null : view.items.find(item => item.item_ref === container.owner_ref);
  if (!section || (container.owner_ref !== null && !owner)) throw new Error('invalid_form_target');
  return { sectionKey: section.section_key, ownerId: owner?.item_id ?? null, kind: container.child_kind };
}
function sameAddress(left: ContainerAddress, right: ContainerAddress): boolean {
  return left.sectionKey === right.sectionKey && left.ownerId === right.ownerId && left.kind === right.kind;
}
export function containerFor(view: JdView, address: ContainerAddress): ContainerRecord {
  const matches = view.containers.filter(container => sameAddress(addressOf(view, container), address));
  if (matches.length !== 1) throw new Error('invalid_form_target');
  return matches[0];
}
export function itemFor(view: JdView, itemId: string): ItemView {
  const item = view.items.find(item => item.item_id === itemId);
  if (!item) throw new Error('invalid_form_target');
  return item;
}
export function fieldFor(view: JdView, itemId: string | null, name: FieldRecord['name']): FieldView {
  const field = view.fields.find(field => field.itemId === itemId && field.name === name);
  if (!field) throw new Error('invalid_form_target');
  return field;
}
export function siblings(view: JdView, container: ContainerRecord): ItemView[] {
  return view.items.filter(item => item.container_ref === container.container_ref).sort((a, b) => a.position - b.position);
}
export function children(view: JdView, owner: ItemView): ItemView[] {
  const refs = new Set(view.containers.filter(container => container.owner_ref === owner.item_ref).map(container => container.container_ref));
  return view.items.filter(item => refs.has(item.container_ref)).sort((a, b) => a.position - b.position);
}
function formField(field: FieldView): FormField {
  return { itemId: field.itemId, name: field.name, baseValue: field.value, text: field.value ?? '' };
}
export function summary(view: JdView, item: ItemView | null): string {
  if (!item) return '新增項目';
  const related = [item, ...children(view, item)];
  if (item.kind === 'duty') related.push(...children(view, item).flatMap(task => children(view, task)));
  if (item.kind === 'task') {
    const parentRef = view.containers.find(container => container.container_ref === item.container_ref)?.owner_ref;
    const duty = view.items.find(row => row.item_ref === parentRef);
    if (duty) related.unshift(duty);
  }
  const taskRefs = new Set(related.filter(row => row.kind === 'task').map(row => row.item_ref));
  const usedRefs = new Set(view.relations.filter(relation => taskRefs.has(relation.task_ref)).map(relation => relation.capability_ref));
  related.push(...view.items.filter(row => usedRefs.has(row.item_ref)));
  return related.map(row => `${kindLabels[row.kind]}\n${row.fields.map(field => `${fieldLabels[field.name]}：${field.value ?? '尚未填寫'}`).join('\n')}`).join('\n\n');
}
export function formSummary(view: JdView, form: ItemForm): string {
  const item = form.itemId ? view.items.find(row => row.item_id === form.itemId) ?? null : null;
  if (item) return summary(view, item);
  const owner = form.container.ownerId ? view.items.find(row => row.item_id === form.container.ownerId) ?? null : null;
  return owner ? summary(view, owner) : `新增${kindLabels[form.container.kind]}；${form.container.kind === 'task' ? '尚未歸入職責' : '共用清單'}`;
}
function capabilityIds(view: JdView, task: ItemView): string[] {
  return view.relations.filter(relation => relation.task_ref === task.item_ref).map(relation => {
    const capability = view.items.find(item => item.item_ref === relation.capability_ref);
    if (!capability) throw new Error('invalid_form_target');
    return capability.item_id;
  });
}
export function structuralFields(view: JdView, item: ItemView, destination: ContainerRecord): FormField[] {
  if (item.kind === 'duty') return children(view, item).flatMap(task => [task, ...children(view, task)]).flatMap(row => row.fields.map(formField));
  if (item.kind !== 'task' || item.container_ref === destination.container_ref) return [];
  const source = view.containers.find(container => container.container_ref === item.container_ref)!;
  const duties = view.items.filter(row => row.item_ref === source.owner_ref || row.item_ref === destination.owner_ref);
  return [...item.fields, ...children(view, item).flatMap(row => row.fields),
    ...duties.flatMap(row => row.fields.filter(field => field.name === 'scope_text'))].map(formField);
}
function newFieldNames(kind: ItemRecord['kind']): FieldRecord['name'][] {
  return kind === 'duty' || kind === 'collaborator' ? ['name', 'scope_text']
    : ['task', 'knowledge', 'skill'].includes(kind) ? ['name', 'description'] : ['text'];
}
export function newItemForm(view: JdView, container: ContainerRecord): ItemForm {
  const names = newFieldNames(container.child_kind);
  const form: ItemForm = { format: 1, mode: 'create', itemId: null, container: addressOf(view, container),
    afterId: siblings(view, container).at(-1)?.item_id ?? null, baseRevisionRef: view.revisionRef, baselineText: '新增項目',
    fields: names.map(name => ({ itemId: null, name, baseValue: null, text: '' })), details: [],
    originalDetailIds: [], capabilityIds: [], originalCapabilityIds: [], newCapability: null };
  form.baselineText = formSummary(view, form);
  return form;
}
export function manageItemForm(view: JdView, item: ItemView, mode: Exclude<ItemForm['mode'], 'create'>): ItemForm {
  const container = view.containers.find(container => container.container_ref === item.container_ref)!;
  const rows = siblings(view, container); const index = rows.findIndex(row => row.item_id === item.item_id);
  const details: FormDetail[] = mode === 'revise' ? children(view, item).filter(row => row.kind === 'outcome' || row.kind === 'requirement')
    .map(row => ({ key: crypto.randomUUID(), itemId: row.item_id, taskId: item.item_id,
      kind: row.kind as 'outcome' | 'requirement', baseValue: row.fields[0].value, text: row.fields[0].value ?? '' })) : [];
  const selected = item.kind === 'task' ? capabilityIds(view, item) : [];
  return { format: 1, mode, itemId: item.item_id, container: addressOf(view, container), afterId: rows[index - 1]?.item_id ?? null,
    baseRevisionRef: view.revisionRef, baselineText: summary(view, item),
    fields: mode === 'revise' ? item.fields.map(formField) : mode === 'delete' ? structuralFields(view, item, container) : [],
    details, originalDetailIds: details.map(detail => detail.itemId!), capabilityIds: selected, originalCapabilityIds: selected, newCapability: null };
}
export const nullable = (text: string): string | null => text === '' ? null : text;
function fieldChanges(view: JdView, form: ItemForm): SetFieldChange[] {
  return form.fields.filter(field => nullable(field.text) !== field.baseValue).map(field => ({ kind: 'set_field',
    target_field_ref: fieldFor(view, field.itemId, field.name).field_ref, text: nullable(field.text), basis_refs: [] }));
}
function newDetails(view: JdView, form: ItemForm): AddTaskDetailChange[] {
  return form.details.filter(detail => detail.itemId === null).map(detail => {
    if (!detail.taskId) throw new Error('invalid_form_target');
    const task = itemFor(view, detail.taskId);
    const last = children(view, task).filter(row => row.kind === detail.kind &&
      (!form.originalDetailIds.includes(row.item_id) || form.details.some(detail => detail.itemId === row.item_id))).at(-1);
    return { kind: 'add_task_detail', task_ref: task.item_ref, detail_kind: detail.kind,
      after_ref: last?.item_ref ?? null, text: detail.text, basis_refs: [] };
  });
}
/** Translate one explicit form intent; current opaque refs come only from the read page. */
export function commandForForm(view: JdView, form: ItemForm): ManualCommand | null {
  if (form.baseRevisionRef !== view.revisionRef) throw new Error('form_revision_changed');
  if (!parseItemForm(form) || form.newCapability !== null) throw new Error('invalid_form_target');
  if (form.mode === 'create') {
    const container = containerFor(view, form.container);
    const after = form.afterId === null ? null : itemFor(view, form.afterId);
    if (after && after.container_ref !== container.container_ref) throw new Error('invalid_form_target');
    const value = (name: FieldRecord['name']) => nullable(form.fields.find(field => field.name === name)?.text ?? '');
    const common = { container_ref: container.container_ref, after_ref: after?.item_ref ?? null, basis_refs: [] };
    if (container.child_kind === 'task') return { tool: 'jd_create_task', arguments: { ...common,
      name: value('name'), description: value('description'),
      outcomes: form.details.filter(detail => detail.kind === 'outcome').map(detail => ({ text: detail.text, basis_refs: [] })),
      requirements: form.details.filter(detail => detail.kind === 'requirement').map(detail => ({ text: detail.text, basis_refs: [] })),
      capabilities: form.capabilityIds.map(itemId => ({ capability_ref: itemFor(view, itemId).item_ref, basis_refs: [] })) } };
    if (container.child_kind === 'duty' || container.child_kind === 'collaborator') return { tool: 'jd_insert_item',
      arguments: { item: { ...common, kind: container.child_kind, name: value('name'), scope_text: value('scope_text') } } };
    if (container.child_kind === 'knowledge' || container.child_kind === 'skill') return { tool: 'jd_insert_item',
      arguments: { item: { ...common, kind: container.child_kind, name: value('name'), description: value('description') } } };
    return { tool: 'jd_insert_item', arguments: { item: { ...common,
      kind: container.child_kind === 'outcome' || container.child_kind === 'requirement' ? container.child_kind : 'condition',
      text: value('text') ?? '' } } };
  }
  const item = itemFor(view, form.itemId!);
  if (form.mode === 'delete') return { tool: 'jd_delete_item', arguments: { target_ref: item.item_ref,
    content_changes: [...fieldChanges(view, form), ...newDetails(view, form)] } };
  if (form.mode === 'move') {
    const container = containerFor(view, form.container);
    const after = form.afterId === null ? null : itemFor(view, form.afterId);
    if (after && after.container_ref !== container.container_ref) throw new Error('invalid_form_target');
    return { tool: 'jd_move_item', arguments: { target_ref: item.item_ref,
      destination_container_ref: container.container_ref, after_ref: after?.item_ref ?? null,
      content_changes: [...fieldChanges(view, form), ...newDetails(view, form)] } };
  }
  const changes: Extract<ManualCommand, { tool: 'jd_revise_work' }>['arguments']['changes'] = [];
  if (form.mode === 'revise') {
    changes.push(...fieldChanges(view, form));
    for (const detail of form.details.filter(detail => detail.itemId !== null)) {
      if (detail.text !== detail.baseValue) changes.push({ kind: 'set_field',
        target_field_ref: fieldFor(view, detail.itemId, 'text').field_ref, text: detail.text, basis_refs: [] });
    }
    for (const itemId of form.originalDetailIds) if (!form.details.some(detail => detail.itemId === itemId))
      changes.push({ kind: 'remove_task_detail', detail_ref: itemFor(view, itemId).item_ref });
    changes.push(...newDetails(view, form));
  }
  for (const itemId of new Set([...form.originalCapabilityIds, ...form.capabilityIds])) {
    if (form.originalCapabilityIds.includes(itemId) === form.capabilityIds.includes(itemId)) continue;
    changes.push({ kind: 'set_task_capability', task_ref: item.item_ref, capability_ref: itemFor(view, itemId).item_ref,
      mode: form.capabilityIds.includes(itemId) ? 'link' : 'unlink', basis_refs: [] });
  }
  return changes.length ? { tool: 'jd_revise_work', arguments: { changes } } : null;
}

export function commandForNewCapability(view: JdView, form: ItemForm): ManualCommand {
  if (!parseItemForm(form) || !form.newCapability || form.baseRevisionRef !== view.revisionRef) throw new Error('invalid_form_target');
  const draft = form.newCapability;
  const group = containerFor(view, { sectionKey: draft.kind === 'knowledge' ? 'knowledge' : 'skills', ownerId: null, kind: draft.kind });
  const nested = newItemForm(view, group);
  nested.fields = nested.fields.map(field => ({ ...field, text: field.name === 'name' ? draft.name : draft.description }));
  return commandForForm(view, nested)!;
}

/** Called only inside the parent's successful original-receipt acknowledgment transaction. */
export function settleItemForm(value: JsonValue, command: ManualCommand): JsonValue {
  const form = parseItemForm(value);
  if (!form?.newCapability || command.tool !== 'jd_insert_item') return value;
  const item = command.arguments.item; const draft = form.newCapability;
  if ((item.kind !== 'knowledge' && item.kind !== 'skill') || item.kind !== draft.kind
    || item.name !== nullable(draft.name) || item.description !== nullable(draft.description) || item.basis_refs.length) return value;
  return { ...form, newCapability: null } as unknown as JsonValue;
}
