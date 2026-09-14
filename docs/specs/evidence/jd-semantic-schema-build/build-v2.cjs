'use strict';
// One-time, reproducible design-schema amendment from frozen v1. Not a runtime migration.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../../../..');
const source = path.join(root, 'docs/specs/contracts/jd-editor-v1.schema.json');
const output = path.join(root, 'docs/specs/contracts/jd-editor-v2.schema.json');
const sourceBytes = fs.readFileSync(source);
const expected = 'ced26a3b625de891989a63d5f12e4ac884484083d7f677cf10ad8c54e318b973';
if (crypto.createHash('sha256').update(sourceBytes).digest('hex') !== expected) throw Error('Frozen v1 source changed');
const schema = JSON.parse(sourceBytes);
const d = schema.$defs;
const ref = name => ({ $ref: '#/$defs/' + name });
const clone = value => JSON.parse(JSON.stringify(value));
const typeIs = name => ({ type: 'object', required: ['type'], properties: { type: { const: name } } });
const typed = (base, type) => ({ allOf: [ref(base), typeIs(type)] });
schema.$id = schema.$id.replace('jd-editor-v1', 'jd-editor-v2');
if (schema.title) schema.title = schema.title.replace(/v1/g, 'v2').replace(/V1/g, 'V2');
schema.description = 'Active JD design contract v2: parallel Task outcome/requirement groups and same-revision knowledge/skill references. Frozen v1 remains historical; not a migration or production authority.';
d.JdEngineProfile.properties.format_version.const = 2;
d.JdEngineProfile.properties.engine_profile.const = 'jd-plate-clean-v2';
d.JdDocumentValue.description = d.JdDocumentValue.description.replace(/jd-plate-clean-v1/g, 'jd-plate-clean-v2');
d.JdElementType.enum.push('jd_outcomes', 'jd_requirements', 'jd_knowledge', 'jd_skill');
d.JdItemIds = { type: 'array', uniqueItems: true, items: { type: 'string', minLength: 1 }, description: 'Ordered same-revision semantic item IDs. The App verifies unique whole-document IDs, endpoint kind and existence; no current/history fallback.' };
d.JdItemRefs = { type: 'array', uniqueItems: true, items: ref('OpaqueRef'), description: 'Ordered App-issued target references from the exact read revision. They are capabilities, not saved item IDs. App checks document/base, access and endpoint kind.' };
for (const mode of ['Saved', 'New']) {
  const elementName = 'Jd' + mode + 'Element';
  const el = d[elementName];
  const body = 'Jd' + mode + 'BodyElement';
  for (const [suffix, type] of [['Outcomes','jd_outcomes'],['Requirements','jd_requirements'],['KnowledgeItem','jd_knowledge'],['SkillItem','jd_skill']]) d['Jd' + mode + suffix] = typed(elementName, type);
  d['Jd' + mode + 'TaskChild'] = { oneOf: [ref(body), ref('Jd' + mode + 'Outcomes'), ref('Jd' + mode + 'Requirements')] };
  d['Jd' + mode + 'KnowledgeSectionChild'] = { oneOf: [ref(body), ref('Jd' + mode + 'KnowledgeItem')] };
  d['Jd' + mode + 'SkillsSectionChild'] = { oneOf: [ref(body), ref('Jd' + mode + 'SkillItem')] };
  const taskRule = el.allOf.find(rule => rule.if?.properties?.type?.const === 'jd_task');
  taskRule.then.properties.children = {
    type: 'array', minItems: 3, items: ref('Jd' + mode + 'TaskChild'),
    allOf: [
      { contains: typeIs('jd_outcomes'), minContains: 1, maxContains: 1 },
      { contains: typeIs('jd_requirements'), minContains: 1, maxContains: 1 },
      { contains: ref(body), minContains: 1 }
    ]
  };
  el.allOf.push({ if: { type: 'object', required: ['type'], properties: { type: { enum: ['jd_outcomes','jd_requirements','jd_knowledge','jd_skill'] } } }, then: { properties: { children: { type: 'array', minItems: 1, items: ref(body) } } } });
  const sectionRule = el.allOf.find(rule => rule.if?.properties?.type?.const === 'jd_section');
  sectionRule.then.else = {
    if: { properties: { section_kind: { const: 'knowledge' } }, required: ['section_kind'] },
    then: { properties: { children: { type: 'array', items: ref('Jd' + mode + 'KnowledgeSectionChild') } } },
    else: {
      if: { properties: { section_kind: { const: 'skills' } }, required: ['section_kind'] },
      then: { properties: { children: { type: 'array', items: ref('Jd' + mode + 'SkillsSectionChild') } } },
      else: { properties: { children: { type: 'array', items: ref(body) } } }
    }
  };
}
for (const key of ['knowledge_ids','skill_ids']) d.JdSavedElement.properties[key] = ref('JdItemIds');
d.JdSavedElement.allOf.push({ if: { type: 'object', required: ['type'], properties: { type: { not: { const: 'jd_task' } } } }, then: { not: { anyOf: [{required:['knowledge_ids']},{required:['skill_ids']}] } } });
d.JdNewElement.description = 'New content has no Element IDs or semantic link fields. Create items first, confirm saving, reread the current base, then link saved Tasks with set_properties. Use empty paragraphs for unknown group content, never invented facts.';
// Preserve the original property family for the resolved boundary, before adding model refs.
d.JdResolvedEditableProperties = clone(d.JdEditableProperties);
d.JdResolvedUnsettableProperty = clone(d.JdUnsettableProperty);
d.JdResolvedPropertyUpdateConstraint = clone(d.JdPropertyUpdateConstraint);
function addRelations(propertiesName, unsetName, constraintName, names) {
  for (const name of names) {
    d[propertiesName].properties[name] = ref(name.endsWith('_ids') ? 'JdItemIds' : 'JdItemRefs');
    d[unsetName].enum.push(name);
    d[constraintName].allOf.push({ not: { type: 'object', required: ['set','unset'], properties: { set: { type: 'object', required: [name] }, unset: { type: 'array', contains: { const: name } } } } });
  }
}
addRelations('JdEditableProperties','JdUnsettableProperty','JdPropertyUpdateConstraint',['knowledge_refs','skill_refs']);
addRelations('JdResolvedEditableProperties','JdResolvedUnsettableProperty','JdResolvedPropertyUpdateConstraint',['knowledge_ids','skill_ids']);
d.JdEditableProperties.description += ' knowledge_refs/skill_refs apply only to a saved Task and replace the complete ordered link set. [] or unset clears; omission preserves. Copy issued refs after reading the relevant current-base items.';
d.JdResolvedEditableProperties.description = 'App-resolved native property updates. Semantic knowledge_ids/skill_ids apply only to Tasks and contain same-base item IDs. Both set and unset names are translated from model refs; Node receives no opaque semantic target refs. Existing source_refs keep their separate source-owner meaning.';
const resolvedSet = d.JdResolvedEditCommand.oneOf.find(branch => branch.properties?.type?.const === 'set_properties');
resolvedSet.properties.set = ref('JdResolvedEditableProperties');
resolvedSet.properties.unset.items = ref('JdResolvedUnsettableProperty');
resolvedSet.allOf = [ref('JdResolvedPropertyUpdateConstraint')];
d.JdSetPropertiesCommand.description += ' Task knowledge_refs/skill_refs replace complete ordered relations; [] or unset clears them. App resolves endpoint kind, access and scope, then maps both set and unset to saved IDs. Never enter raw or temporary IDs.';
const target = d.JdReadTarget;
for (const key of ['knowledge_refs','skill_refs','used_by_task_refs']) target.properties[key] = ref('JdItemRefs');
target.allOf = [
  { if: { properties: { element: typeIs('jd_task') }, required:['element'] }, then: { required:['knowledge_refs','skill_refs'], not:{required:['used_by_task_refs']} }, else: { not:{anyOf:[{required:['knowledge_refs']},{required:['skill_refs']}] } } },
  { if: { properties: { element: {type:'object',required:['type'],properties:{type:{enum:['jd_knowledge','jd_skill']}}} }, required:['element'] }, then: {required:['used_by_task_refs']}, else: {not:{required:['used_by_task_refs']}} }
];
target.description = 'Element and its issued reference from one immutable read base. Task link refs and knowledge/skill incoming Task refs are derived from the full revision, including targets whose body is on another page. Read those targets before changing meaning; issuing a ref does not mean its body was read. All derived history refs remain read-only. Incoming Tasks follow document order.';
d.JdReadModelInput.description += ' Task targets include knowledge_refs/skill_refs; knowledge/skill targets include used_by_task_refs computed by the App. Read complete affected items/Tasks before changing shared meaning, following issued target refs and pagination. IDs inside saved fragments are not edit refs.';
d.JdEditModelInput.description += ' New Tasks contain separate jd_outcomes and jd_requirements groups (one each, empty paragraph allowed). Knowledge/skill items are standalone typed blocks. First create items without links; after confirmed saving reread the new base, then set Task knowledge_refs/skill_refs. Never invent temporary IDs or reuse previous-base refs. For shared item edits read affected Tasks; for deleting a referenced item explicitly unlink/relink all affected Tasks in the same batch or keep the item.';
// New schema is the only active design SSOT. Old experiments retain their v1 source/hash.
fs.writeFileSync(output, JSON.stringify(schema, null, 2) + '\n');
console.log(JSON.stringify({output:path.relative(root,output),defs:Object.keys(d).length,sha256:crypto.createHash('sha256').update(fs.readFileSync(output)).digest('hex')}));
