// Offline v2 contract probe. No native editor, database, provider, or production imports.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const Ajv = require('ajv/dist/2020').default;
const addFormats = require('ajv-formats');
const f = require('./fixtures.cjs');
const root = path.resolve(__dirname, '../../../..');
const schemaPath = path.resolve(root, process.argv[2] || 'docs/specs/contracts/jd-editor-v2.schema.json');
const schemaBytes = fs.readFileSync(schemaPath);
const schema = JSON.parse(schemaBytes);
const ajv = new Ajv({strict: false, allErrors: true, coerceTypes: false, useDefaults: false, removeAdditional: false});
addFormats(ajv);
ajv.addSchema(schema);
const checks = [], errors = [];
for (const definition of Object.keys(schema.$defs)) {
  try {
    const compiled = Boolean(ajv.getSchema(`${schema.$id}#/$defs/${definition}`));
    checks.push({name: `compile_${definition}`, layer: 'schema-compilation', expected: true, actual: compiled});
    if (!compiled) errors.push({definition, unresolved: true});
  } catch (error) {
    checks.push({name: `compile_${definition}`, layer: 'schema-compilation', expected: true, actual: false});
    errors.push({definition, message: error.message});
  }
}
function shape(name, definition, value, expected = true) {
  const before = JSON.stringify(value);
  const validate = ajv.getSchema(`${schema.$id}#/$defs/${definition}`);
  if (!validate) {
    checks.push({name, layer: 'schema', definition, expected, actual: null});
    errors.push({name, definition, missingDefinition: true});
    return;
  }
  const actual = validate(value);
  const mutated = before !== JSON.stringify(value);
  checks.push({name, layer: 'schema', definition, expected, actual, mutated});
  if (actual !== expected || mutated) errors.push({name, definition, expected, actual, mutated, errors: validate.errors});
}
function observation(name, run, expected, input = null) {
  const before = JSON.stringify(input);
  let actual;
  try { actual = run(); }
  catch (error) { actual = {unexpectedError: error.message}; }
  const mutated = before !== JSON.stringify(input);
  checks.push({name, layer: 'finite-contract-model', expected, actual, mutated});
  if (JSON.stringify(actual) !== JSON.stringify(expected) || mutated) errors.push({name, expected, actual, mutated});
}
const edit = commands => ({commands});
const set = (props, unset) => ({type: 'set_properties', target_ref: 'ref:task-1', ...(props ? {set: props} : {}), ...(unset ? {unset} : {})});
const resolvedSet = (props, unset) => ({type: 'set_properties', target_id: 'task-1', ...(props ? {set: props} : {}), ...(unset ? {unset} : {})});
const base = f.baseline();
const mutate = fn => {const value = f.clone(base); fn(value); return value;};

shape('profile_v2', 'JdEngineProfile', {format_version: 2, engine_profile: 'jd-plate-clean-v2'});
shape('profile_v1_is_not_v2', 'JdEngineProfile', {format_version: 1, engine_profile: 'jd-plate-clean-v1'}, false);
shape('three_tasks_two_k_two_s_parallel_groups', 'JdDocumentValue', base);
shape('empty_group_bodies_and_no_links_are_valid_draft', 'JdSavedElement', f.find(base, 'task-0'));
shape('explicit_empty_saved_links', 'JdSavedElement', {...f.find(base, 'task-0'), knowledge_ids: [], skill_ids: []});
shape('complete_empty_k_item_is_valid_draft', 'JdSavedElement', f.group('jd_knowledge', 'empty-k'));
shape('task_requires_outcomes', 'JdDocumentValue', mutate(v => f.find(v, 'task-1').children.splice(1, 1)), false);
shape('task_requires_requirements', 'JdDocumentValue', mutate(v => f.find(v, 'task-1').children.splice(2, 1)), false);
shape('task_requires_body_outside_groups', 'JdDocumentValue', mutate(v => f.find(v, 'task-1').children.splice(0, 1)), false);
for (const kind of ['jd_outcomes', 'jd_requirements']) {
  shape(`task_rejects_second_${kind}`, 'JdDocumentValue', mutate(v => f.find(v, 'task-1').children.push(f.group(kind, `extra-${kind}`))), false);
  shape(`${kind}_is_not_root`, 'JdDocumentValue', [f.group(kind, 'root-group')], false);
  shape(`${kind}_cannot_contain_k`, 'JdSavedElement', {type: kind, id: 'group-k', children: [f.item('jd_knowledge', 'k-extra', '標題', '內容')]}, false);
  shape(`${kind}_cannot_have_empty_children`, 'JdSavedElement', {type: kind, id: 'empty-group', children: []}, false);
}
shape('requirements_cannot_nest_under_outcomes', 'JdDocumentValue', mutate(v => f.find(v, 'task-1-outcomes').children.push(f.group('jd_requirements', 'nested-requirements'))), false);
shape('k_cannot_be_direct_task_child', 'JdDocumentValue', mutate(v => f.find(v, 'task-1').children.push(f.item('jd_knowledge', 'misplaced-k', '標題', '內容'))), false);
shape('k_not_allowed_in_skills_section', 'JdDocumentValue', mutate(v => f.find(v, 'skills-section').children.push(f.item('jd_knowledge', 'misplaced-k', '標題', '內容'))), false);
shape('s_not_allowed_in_knowledge_section', 'JdDocumentValue', mutate(v => f.find(v, 'knowledge-section').children.push(f.item('jd_skill', 'misplaced-s', '標題', '內容'))), false);
shape('k_not_allowed_in_work_section', 'JdDocumentValue', mutate(v => f.find(v, 'work-section').children.push(f.item('jd_knowledge', 'misplaced-k', '標題', '內容'))), false);
shape('k_cannot_contain_task', 'JdSavedElement', {type: 'jd_knowledge', id: 'bad-k', children: [f.task('nested-task', '內容')]}, false);
shape('s_cannot_contain_k', 'JdSavedElement', {type: 'jd_skill', id: 'bad-s', children: [f.item('jd_knowledge', 'nested-k', '標題', '內容')]}, false);
shape('k_not_root', 'JdDocumentValue', [f.item('jd_knowledge', 'root-k', '標題', '內容')], false);
for (const property of ['knowledge_ids', 'skill_ids']) {
  shape(`saved_task_${property}_duplicates_rejected`, 'JdSavedElement', {...f.find(base, 'task-0'), [property]: ['same', 'same']}, false);
  shape(`saved_non_task_${property}_rejected`, 'JdSavedElement', {...f.p('p-unrelated', '文字'), [property]: []}, false);
  shape(`saved_empty_${property}_member_rejected`, 'JdSavedElement', {...f.find(base, 'task-0'), [property]: ['']}, false);
}
shape('saved_model_ref_property_rejected', 'JdSavedElement', {...f.find(base, 'task-0'), knowledge_refs: []}, false);
shape('saved_reverse_link_property_rejected', 'JdSavedElement', {...f.find(base, 'k-1'), used_by_task_refs: []}, false);
const newTask = f.withoutIds(f.find(base, 'task-1'));
shape('new_task_groups_without_ids_or_links', 'JdNewElement', newTask);
const newMissingGroup = f.clone(newTask); newMissingGroup.children.splice(1, 1);
shape('new_task_missing_group_rejected', 'JdNewElement', newMissingGroup, false);
const newRepeatedGroup = f.clone(newTask); newRepeatedGroup.children.push(f.clone(newRepeatedGroup.children[1]));
shape('new_task_repeated_group_rejected', 'JdNewElement', newRepeatedGroup, false);
shape('new_complete_knowledge', 'JdNewElement', f.withoutIds(f.find(base, 'k-1')));
shape('new_complete_skill', 'JdNewElement', f.withoutIds(f.find(base, 's-1')));
shape('new_item_requires_body', 'JdNewElement', {type: 'jd_knowledge', children: []}, false);
shape('new_knowledge_wrong_section_rejected', 'JdNewElement', {type: 'jd_section', section_kind: 'skills', children: [f.withoutIds(f.find(base, 'k-1'))]}, false);
for (const property of ['knowledge_ids', 'skill_ids', 'knowledge_refs', 'skill_refs']) {
  shape(`new_task_no_${property}_even_empty`, 'JdNewElement', {...newTask, [property]: []}, false);
}
shape('new_top_level_id_rejected', 'JdNewElement', {...newTask, id: 'guess-id'}, false);
const newNestedId = f.clone(newTask); newNestedId.children[1].children[0].id = 'guess-nested-id';
shape('new_nested_id_rejected', 'JdNewElement', newNestedId, false);
shape('new_temporary_id_rejected', 'JdNewElement', {...newTask, temporary_id: 'temp-1'}, false);
shape('first_create_items_without_link_command', 'JdEditModelInput', edit([{type: 'insert_content', target_ref: 'ref:knowledge-section', placement: 'append_child', content: [f.withoutIds(f.find(base, 'k-1'))]}]));
shape('first_create_task_and_item_without_temporary_links', 'JdEditModelInput', edit([
  {type: 'insert_content', target_ref: 'ref:work-section', placement: 'append_child', content: [newTask]},
  {type: 'insert_content', target_ref: 'ref:knowledge-section', placement: 'append_child', content: [f.withoutIds(f.find(base, 'k-1'))]},
]));
for (const [modelProperty, savedProperty, ref, id] of [
  ['knowledge_refs', 'knowledge_ids', 'ref:a-r1:k1', 'k-1'],
  ['skill_refs', 'skill_ids', 'ref:a-r1:s1', 's-1'],
]) {
  shape(`model_set_${modelProperty}`, 'JdEditModelInput', edit([set({[modelProperty]: [ref]})]));
  shape(`model_clear_${modelProperty}_empty`, 'JdSetPropertiesCommand', set({[modelProperty]: []}));
  shape(`model_clear_${modelProperty}_unset`, 'JdSetPropertiesCommand', set(null, [modelProperty]));
  shape(`model_overlap_${modelProperty}`, 'JdSetPropertiesCommand', set({[modelProperty]: [ref]}, [modelProperty]), false);
  shape(`model_duplicate_${modelProperty}`, 'JdSetPropertiesCommand', set({[modelProperty]: [ref, ref]}), false);
  shape(`model_cannot_set_${savedProperty}`, 'JdSetPropertiesCommand', set({[savedProperty]: [id]}), false);
  shape(`model_cannot_unset_${savedProperty}`, 'JdSetPropertiesCommand', set(null, [savedProperty]), false);
  shape(`resolved_set_${savedProperty}`, 'JdResolvedEditCommand', resolvedSet({[savedProperty]: [id]}));
  shape(`resolved_clear_${savedProperty}_unset`, 'JdResolvedEditCommand', resolvedSet(null, [savedProperty]));
  shape(`resolved_overlap_${savedProperty}`, 'JdResolvedEditCommand', resolvedSet({[savedProperty]: [id]}, [savedProperty]), false);
  shape(`resolved_cannot_set_${modelProperty}`, 'JdResolvedEditCommand', resolvedSet({[modelProperty]: [ref]}), false);
  shape(`resolved_cannot_unset_${modelProperty}`, 'JdResolvedEditCommand', resolvedSet(null, [modelProperty]), false);
}
shape('model_disjoint_relation_update', 'JdSetPropertiesCommand', set({knowledge_refs: ['ref:a-r1:k1']}, ['skill_refs']));
shape('resolved_disjoint_relation_update', 'JdResolvedEditCommand', resolvedSet({knowledge_ids: ['k-1']}, ['skill_ids']));
shape('model_preserves_source_attachment_property', 'JdSetPropertiesCommand', set({source_refs: ['source:issued-01'], knowledge_refs: ['ref:a-r1:k1']}));
for (const [key, value] of Object.entries({source_refs: [], colSizes: [120], marginLeft: 0, size: 40, colSpan: 2, rowSpan: 2, background: 'red', borders: {}})) {
  shape(`prior_model_overlap_${key}_still_rejected`, 'JdSetPropertiesCommand', set({[key]: value}, [key]), false);
  shape(`prior_resolved_overlap_${key}_still_rejected`, 'JdResolvedEditCommand', resolvedSet({[key]: value}, [key]), false);
}
const readTask = {target_ref: 'ref:task-1', element: f.find(base, 'task-1'), access: 'current_base', knowledge_refs: ['ref:a-r1:k1', 'ref:a-r1:k2'], skill_refs: ['ref:a-r1:s1']};
const readK = {target_ref: 'ref:a-r1:k1', element: f.find(base, 'k-1'), access: 'current_base', used_by_task_refs: ['ref:task-1', 'ref:task-2']};
const readS = {target_ref: 'ref:a-r1:s1', element: f.find(base, 's-1'), access: 'current_base', used_by_task_refs: ['ref:task-1', 'ref:task-2']};
shape('read_task_relation_refs', 'JdReadTarget', readTask);
shape('read_knowledge_reverse_refs', 'JdReadTarget', readK);
shape('read_skill_reverse_refs', 'JdReadTarget', readS);
shape('read_unused_item_empty_reverse_refs', 'JdReadTarget', {...readK, used_by_task_refs: []});
shape('read_history_task_still_has_relations', 'JdReadTarget', {...readTask, access: 'read_only'});
for (const property of ['knowledge_refs', 'skill_refs']) {
  const missing = f.clone(readTask); delete missing[property];
  shape(`read_task_requires_${property}`, 'JdReadTarget', missing, false);
  shape(`read_task_unique_${property}`, 'JdReadTarget', {...readTask, [property]: ['duplicate', 'duplicate']}, false);
}
for (const value of [readK, readS]) {
  const missing = f.clone(value); delete missing.used_by_task_refs;
  shape(`read_${value.element.type}_requires_reverse`, 'JdReadTarget', missing, false);
}
shape('read_task_cannot_have_reverse_refs', 'JdReadTarget', {...readTask, used_by_task_refs: []}, false);
shape('read_item_cannot_have_task_refs', 'JdReadTarget', {...readK, knowledge_refs: []}, false);
shape('read_plain_body_cannot_have_relation_refs', 'JdReadTarget', {target_ref: 'ref:p', element: f.p('p-read', '文字'), access: 'current_base', knowledge_refs: []}, false);
const manual = value => ({request_key: 'a177b9f5-c9ac-40db-a92e-3b6b7c97e744', base_revision_ref: 'revision:a-r1', value});
shape('manual_complete_value_v2', 'JdManualSaveClientInput', manual(base));
shape('manual_uses_same_grammar', 'JdManualSaveClientInput', manual(mutate(v => f.find(v, 'task-1').children.splice(2, 1))), false);
shape('node_complete_value_v2', 'JdPlateValidateValueRequest', {profile: {format_version: 2, engine_profile: 'jd-plate-clean-v2'}, value: base});

// A finite, read-only contract model. It is deliberately not an editor, a generic
// graph engine, a production issuer, or a replacement for the shared validator.
function index(snapshot) {
  const nodes = new Map(), duplicates = [];
  const visit = list => {for (const node of list) {
    if (node.id) {if (nodes.has(node.id)) duplicates.push(node.id); else nodes.set(node.id, node);}
    if (Array.isArray(node.children)) visit(node.children);
  }};
  visit(snapshot.value);
  return {nodes, duplicates};
}
function relationProblems(snapshot) {
  const {nodes, duplicates} = index(snapshot);
  const problems = duplicates.map(id => `duplicate-id:${id}`);
  for (const node of nodes.values()) {
    if (node.type !== 'jd_task') continue;
    for (const [property, kind] of [['knowledge_ids', 'jd_knowledge'], ['skill_ids', 'jd_skill']]) {
      const seen = new Set();
      for (const id of node[property] || []) {
        if (seen.has(id)) problems.push(`duplicate-link:${node.id}:${property}:${id}`);
        seen.add(id);
        const target = nodes.get(id);
        if (!target) problems.push(`missing:${node.id}:${property}:${id}`);
        else if (target.type !== kind) problems.push(`wrong-kind:${node.id}:${property}:${id}`);
      }
    }
  }
  return problems;
}
function fixedItem(store, documentId, revisionId, itemId, kind) {
  const snapshot = store.find(v => v.document_id === documentId && v.revision_id === revisionId);
  if (!snapshot) return null;
  const {nodes, duplicates} = index(snapshot);
  if (duplicates.length) return null;
  const item = nodes.get(itemId);
  return item && item.type === kind ? item : null;
}
function fixedIssued(refs, snapshot, kind) {
  const ids = [];
  for (const ref of refs) {
    const issued = f.issuedRefs[ref];
    if (!issued) return {error: 'unissued'};
    if (issued.access !== 'current_base') return {error: 'read-only'};
    if (issued.document_id !== snapshot.document_id) return {error: 'wrong-document'};
    if (issued.revision_id !== snapshot.revision_id) return {error: 'wrong-revision'};
    if (issued.kind !== kind || !fixedItem([snapshot], snapshot.document_id, snapshot.revision_id, issued.item_id, kind)) return {error: 'wrong-or-missing-kind'};
    if (ids.includes(issued.item_id)) return {error: 'duplicate-target'};
    ids.push(issued.item_id);
  }
  return {ids};
}
function users(snapshot, itemId) {
  return [...index(snapshot).nodes.values()]
    .filter(n => n.type === 'jd_task' && [...(n.knowledge_ids || []), ...(n.skill_ids || [])].includes(itemId))
    .map(n => n.id);
}
const {r1, r2, b1} = f.snapshots();
const store = [r1, r2, b1];
const snapshot = value => ({document_id: 'document-a', revision_id: 'a-r1', value});
const firstSaved = f.clone(r1);
for (const node of firstSaved.value[0].children) {
  delete node.knowledge_ids;
  delete node.skill_ids;
}
shape('first_saved_complete_items_can_remain_unlinked', 'JdDocumentValue', firstSaved.value);
observation('first_saved_candidate_has_items_and_zero_links', () => [relationProblems(firstSaved), users(firstSaved, 'k-1'), f.find(firstSaved.value, 'knowledge-section').children.length], [[], [], 2], firstSaved);
const secondCandidate = f.clone(firstSaved);
secondCandidate.revision_id = 'a-r2';
f.find(secondCandidate.value, 'task-1').knowledge_ids = fixedIssued(['ref:a-r1:k1', 'ref:a-r1:k2'], firstSaved, 'jd_knowledge').ids;
f.find(secondCandidate.value, 'task-1').skill_ids = fixedIssued(['ref:a-r1:s1'], firstSaved, 'jd_skill').ids;
shape('second_candidate_uses_resolved_item_ids', 'JdDocumentValue', secondCandidate.value);
observation('second_link_candidate_valid_without_recreating_items', () => [relationProblems(secondCandidate), users(secondCandidate, 'k-1'), JSON.stringify(secondCandidate.value.slice(1)) === JSON.stringify(firstSaved.value.slice(1))], [[], ['task-1'], true], [firstSaved, secondCandidate]);
observation('valid_many_to_many_and_zero_links', () => relationProblems(r1), [], r1);
observation('reverse_users_derived_in_task_order', () => users(r1, 'k-1'), ['task-1', 'task-2'], r1);
const missing = snapshot(mutate(v => f.find(v, 'task-1').knowledge_ids = ['missing-k']));
shape('missing_endpoint_is_shape_valid_app_must_check', 'JdDocumentValue', missing.value);
observation('missing_endpoint_rejected', () => relationProblems(missing), ['missing:task-1:knowledge_ids:missing-k'], missing);
const wrongKind = snapshot(mutate(v => f.find(v, 'task-1').knowledge_ids = ['s-1']));
shape('wrong_kind_is_shape_valid_app_must_check', 'JdDocumentValue', wrongKind.value);
observation('wrong_kind_endpoint_rejected', () => relationProblems(wrongKind), ['wrong-kind:task-1:knowledge_ids:s-1'], wrongKind);
const plainEndpoint = snapshot(mutate(v => f.find(v, 'task-1').skill_ids = ['task-1-body']));
observation('plain_paragraph_is_not_skill_item', () => relationProblems(plainEndpoint), ['wrong-kind:task-1:skill_ids:task-1-body'], plainEndpoint);
const duplicateId = snapshot(mutate(v => f.find(v, 'skills-section').children.push(f.item('jd_skill', 'k-1', '同 ID', '不允許'))));
shape('duplicate_id_is_shape_valid_app_must_check', 'JdDocumentValue', duplicateId.value);
observation('global_duplicate_element_ids_rejected', () => relationProblems(duplicateId).filter(x => x.startsWith('duplicate-id:')), ['duplicate-id:k-1', 'duplicate-id:k-1-title', 'duplicate-id:k-1-body'], duplicateId);
const duplicateLink = snapshot(mutate(v => f.find(v, 'task-1').knowledge_ids = ['k-1', 'k-1']));
observation('full_value_boundary_rechecks_duplicates', () => relationProblems(duplicateLink), ['duplicate-link:task-1:knowledge_ids:k-1'], duplicateLink);
const title = value => value ? value.children[0].children[0].text : null;
observation('same_id_r1_resolves_r1_definition', () => title(fixedItem(store, 'document-a', 'a-r1', 'k-1', 'jd_knowledge')), '發布程序', store);
observation('same_id_r2_resolves_r2_definition', () => title(fixedItem(store, 'document-a', 'a-r2', 'k-1', 'jd_knowledge')), '修訂後發布程序', store);
observation('same_id_other_document_is_distinct', () => title(fixedItem(store, 'document-b', 'b-r1', 'k-1', 'jd_knowledge')), '另一份文件同 ID 的不同項目', store);
observation('missing_revision_no_fallback_to_current', () => fixedItem(store, 'document-a', 'absent-r', 'k-1', 'jd_knowledge'), null, store);
observation('foreign_revision_no_cross_document_fallback', () => fixedItem(store, 'document-a', 'b-r1', 'k-1', 'jd_knowledge'), null, store);
const r1WithoutK2 = f.clone(r1); f.find(r1WithoutK2.value, 'knowledge-section').children.pop();
observation('missing_in_this_revision_no_later_lookup', () => fixedItem([r1WithoutK2, r2], 'document-a', 'a-r1', 'k-2', 'jd_knowledge'), null, [r1WithoutK2, r2]);
observation('issued_refs_map_to_saved_ids_preserving_order', () => fixedIssued(['ref:a-r1:k2', 'ref:a-r1:k1'], r1, 'jd_knowledge'), {ids: ['k-2', 'k-1']}, r1);
for (const [name, refs, current, kind, expected] of [
  ['raw_saved_id_is_not_issued', ['k-1'], r1, 'jd_knowledge', 'unissued'],
  ['guessed_same_batch_id_is_not_issued', ['temporary:new-k'], r1, 'jd_knowledge', 'unissued'],
  ['source_ref_is_not_relation_ref', ['source:issued-01'], r1, 'jd_knowledge', 'unissued'],
  ['foreign_document_ref_rejected', ['ref:b-r1:k1'], r1, 'jd_knowledge', 'wrong-document'],
  ['old_base_ref_rejected_at_new_base', ['ref:a-r1:k1'], r2, 'jd_knowledge', 'wrong-revision'],
  ['history_ref_is_read_only', ['ref:history:a-r1:k1'], r1, 'jd_knowledge', 'read-only'],
  ['history_read_of_head_still_read_only', ['ref:history:head:k1'], r2, 'jd_knowledge', 'read-only'],
  ['skill_handle_not_knowledge_handle', ['ref:a-r1:s1'], r1, 'jd_knowledge', 'wrong-or-missing-kind'],
  ['issued_record_cannot_override_actual_kind', ['ref:a-r1:wrong-kind'], r1, 'jd_knowledge', 'wrong-or-missing-kind'],
  ['issued_record_must_resolve_existing_item', ['ref:a-r1:missing'], r1, 'jd_knowledge', 'wrong-or-missing-kind'],
  ['distinct_handle_aliases_cannot_duplicate_target', ['ref:a-r1:k1', 'ref:a-r1:k1-alias'], r1, 'jd_knowledge', 'duplicate-target'],
]) observation(name, () => fixedIssued(refs, current, kind), {error: expected}, current);
observation('empty_link_update_is_valid', () => fixedIssued([], r1, 'jd_knowledge'), {ids: []}, r1);
observation('rename_exposes_all_affected_tasks', () => users(r2, 'k-1'), ['task-1', 'task-2'], r2);
observation('rename_does_not_change_task_text_sources_or_links', () => [0, 1, 2].every(i => JSON.stringify(r1.value[0].children[i]) === JSON.stringify(r2.value[0].children[i])), true, store);
observation('json_round_trip_preserves_full_value_and_links', () => f.clone(r1), r1, r1);

// Preconstructed before/after candidates exercise the required contract outcome.
// No paste, move, split, unwrap, or delete command is executed by this probe.
const deleteK = snapshot(mutate(v => f.find(v, 'knowledge-section').children.shift()));
observation('delete_referenced_k_reports_all_remaining_users', () => relationProblems(deleteK), ['missing:task-1:knowledge_ids:k-1', 'missing:task-2:knowledge_ids:k-1'], deleteK);
const deleteParent = snapshot(base.filter(n => n.id !== 'knowledge-section'));
observation('delete_ancestor_checks_descendant_endpoints', () => relationProblems(deleteParent), ['missing:task-1:knowledge_ids:k-1', 'missing:task-1:knowledge_ids:k-2', 'missing:task-2:knowledge_ids:k-1'], deleteParent);
const unlinkDelete = f.clone(deleteK);
for (const id of ['task-1', 'task-2']) f.find(unlinkDelete.value, id).knowledge_ids = f.find(unlinkDelete.value, id).knowledge_ids.filter(x => x !== 'k-1');
shape('explicit_unlink_delete_final_candidate_shape', 'JdDocumentValue', unlinkDelete.value);
observation('explicit_unlink_delete_final_candidate_valid', () => relationProblems(unlinkDelete), [], unlinkDelete);
observation('explicit_unlink_delete_keeps_task_body_and_sources', () => JSON.stringify(f.find(unlinkDelete.value, 'task-1-body')) === JSON.stringify(f.find(r1.value, 'task-1-body')), true, unlinkDelete);
const deleteTask = snapshot(mutate(v => f.find(v, 'work-section').children.splice(1, 1)));
observation('delete_task_does_not_require_deleting_shared_items', () => [relationProblems(deleteTask), users(deleteTask, 'k-1'), title(f.find(deleteTask.value, 'k-1'))], [[], ['task-2'], '發布程序'], deleteTask);
const moved = snapshot(mutate(v => f.find(v, 'work-section').children.reverse()));
observation('move_preserves_links_and_changes_derived_task_order', () => [relationProblems(moved), users(moved, 'k-1')], [[], ['task-2', 'task-1']], moved);
const oneCopy = snapshot(mutate(v => f.find(v, 'work-section').children.push(f.task('copy-task', '複製後的工作草稿。', ['k-1', 'k-2'], ['s-1']))));
shape('task_only_copy_candidate_shape', 'JdDocumentValue', oneCopy.value);
observation('task_only_copy_uses_existing_shared_definitions', () => [relationProblems(oneCopy), users(oneCopy, 'k-1'), f.find(oneCopy.value, 'knowledge-section').children.length], [[], ['task-1', 'task-2', 'copy-task'], 2], oneCopy);
const groupCopy = snapshot(mutate(v => {
  f.find(v, 'work-section').children.push(f.task('copy-task', '同組複製後的工作。', ['copy-k-1', 'k-2'], ['s-1']));
  f.find(v, 'knowledge-section').children.push(f.item('jd_knowledge', 'copy-k-1', '發布程序複本', '同組複製的完整定義。'));
}));
shape('whole_group_copy_candidate_shape', 'JdDocumentValue', groupCopy.value);
observation('group_copy_maps_internal_and_keeps_external_links', () => [relationProblems(groupCopy), users(groupCopy, 'copy-k-1'), users(groupCopy, 'k-1'), f.find(groupCopy.value, 'copy-task').knowledge_ids], [[], ['copy-task'], ['task-1', 'task-2'], ['copy-k-1', 'k-2']], groupCopy);
const foreignCopy = snapshot(mutate(v => f.find(v, 'task-1').knowledge_ids = ['foreign-only-k']));
observation('unmapped_cross_document_candidate_rejected', () => relationProblems(foreignCopy), ['missing:task-1:knowledge_ids:foreign-only-k'], foreignCopy);
const missingWholeValue = manual(missing.value);
shape('manual_orphan_link_is_shape_valid_not_semantically_valid', 'JdManualSaveClientInput', missingWholeValue);
observation('manual_full_value_uses_same_relation_boundary', () => relationProblems({...r1, value: missingWholeValue.value}), ['missing:task-1:knowledge_ids:missing-k'], missingWholeValue);
const unwrapped = snapshot(mutate(v => {
  const work = f.find(v, 'work-section');
  const removed = work.children.splice(1, 1)[0];
  const paragraphs = removed.children.flatMap(n => ['jd_outcomes', 'jd_requirements'].includes(n.type) ? n.children : [n]);
  work.children.splice(1, 0, ...paragraphs);
}));
const onlyTaskUnwrapped = mutate(v => {
  const work = f.find(v, 'work-section');
  const removed = work.children.splice(1, 1)[0];
  work.children.splice(1, 0, ...removed.children);
});
shape('unwrap_task_alone_leaves_illegal_groups', 'JdDocumentValue', onlyTaskUnwrapped, false);
const onlyGroupUnwrapped = mutate(v => {
  const task = f.find(v, 'task-1');
  const removed = task.children.splice(1, 1)[0];
  task.children.splice(1, 0, ...removed.children);
});
shape('unwrap_one_group_alone_leaves_incomplete_task', 'JdDocumentValue', onlyGroupUnwrapped, false);
shape('explicit_unwrap_candidate_body_remains_valid', 'JdDocumentValue', unwrapped.value);
observation('unwrap_does_not_transfer_outgoing_links_to_body', () => [relationProblems(unwrapped), users(unwrapped, 'k-1'), f.find(unwrapped.value, 'task-1-body')], [[], ['task-2'], f.find(base, 'task-1-body')], unwrapped);

const layers = {};
for (const check of checks) layers[check.layer] = (layers[check.layer] || 0) + 1;
const output = {
  schema: path.relative(root, schemaPath).replaceAll('\\', '/'),
  schema_sha256: crypto.createHash('sha256').update(schemaBytes).digest('hex'),
  fixture_sha256: crypto.createHash('sha256').update(fs.readFileSync(path.join(__dirname, 'fixtures.cjs'))).digest('hex'),
  runner_sha256: crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),
  node: process.version, validator: `AJV ${require('ajv/package.json').version}`,
  definitions: Object.keys(schema.$defs).length, count: checks.length, layers, checks, errors,
  representative_fixture: base,
  scope: 'JSON Schema plus a finite read-only contract model and fixed before/after candidates. No editor transforms, ref issuer, native normalization, real source ownership, database, ToolNode, provider, DOM, or natural-model proof.',
};
console.log(JSON.stringify(output, null, 2));
if (errors.length) process.exitCode = 1;
