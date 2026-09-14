'use strict';
// Cross-check recorded native values and captured SDK parameters against the one active schema.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../../../..');
const read = p => JSON.parse(fs.readFileSync(path.join(root, p), 'utf8'));
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(path.join(root, p))).digest('hex');
const schemaPath = 'docs/specs/contracts/jd-editor-v2.schema.json';
const schema = read(schemaPath);
const Ajv = require(path.join(root, 'node_modules/ajv/dist/2020.js'));
const ajv = new Ajv({ strict: false, allErrors: true, coerceTypes: false, useDefaults: false, removeAdditional: false, validateFormats: false });
ajv.addSchema(schema);
const validate = ajv.compile({ $ref: schema.$id + '#/$defs/JdDocumentValue' });
const base = 'docs/specs/evidence/jd-semantic-native-probe/';
const run = base + 'results/2026-09-09T22-38-20-172Z/';
const [a,b,c,d] = ['A','B','C','D'].map(k => read(run + 'F03-' + k + '.json'));
const cases = [
  ['full_r2_v2_fixture',read(base+'fixture.json'),true],
  ['task8_only_expected_oracle',read(base+'task8-move-full-expected.json'),true],
  ['native_canonical',a.canonical,true],
  ['native_empty_task_groups',a.emptyDraft,true],
  ['native_unlinked_creation',b.unlinked,true],
  ['native_linked_and_renamed',b.after,true],
  ['native_fixed_copy_mapping_and_move',c.after,true],
  ['native_explicit_group_and_task_unwrap',d.explicitThreeUnwrap.after,true],
  ['native_clear_group_body',d.clearGroupBody.after,true],
  ['native_unlink_then_delete',d.explicitUnlinkThenDelete.after,true],
  ['native_single_task_unwrap_rejected',d.singleTaskUnwrap.after,false],
  ['native_single_group_delete_rejected',d.singleGroupDelete.after,false],
  ['orphan_is_shape_valid_not_relation_valid',d.deleteReferencedKnowledge.after,true]
];
const checks = cases.map(([name,value,expected]) => {
  const before=JSON.stringify(value), actual=validate(value);
  assert.equal(JSON.stringify(value),before,'validator changed input');
  return { name, expected, actual, passed:actual===expected, errors:actual===expected?[]:structuredClone(validate.errors) };
});
function extract(name) {
  const parameter=structuredClone(schema.$defs[name]), definitions={}, pending=[parameter];
  while(pending.length) {
    const n=pending.pop();
    if(Array.isArray(n)) { pending.push(...n); continue; }
    if(!n||typeof n!=='object')continue;
    if(n.$ref?.startsWith('#/$defs/')) {
      const key=n.$ref.slice('#/$defs/'.length);
      if(!definitions[key]) {definitions[key]=structuredClone(schema.$defs[key]);pending.push(definitions[key]);}
    }
    for(const [k,v] of Object.entries(n))if(k!=='$ref')pending.push(v);
  }
  if(Object.keys(definitions).length)parameter.$defs=definitions;
  return parameter;
}
const wire=read('docs/specs/evidence/jd-semantic-contract-probe/provider-wire-v2-captured.json');
for(const [name,def] of Object.entries({jd_read:'JdReadModelInput',jd_edit:'JdEditModelInput',jd_change_read:'JdChangeReadModelInput'})) {
  const tool=wire.tools.find(t=>t.name===name);
  assert.deepEqual(tool.parameters,extract(def));
  assert.equal(tool.description,schema.$defs[def].description);
  assert.equal(tool.strict,false);
  checks.push({name:'recorded_wire_matches_active_'+name,passed:true});
}
const summary=read(run+'summary.json');
assert(summary.results.every(x=>x.passed&&x.checks.every(c=>c.passed)));
const result={schema_sha256:sha(schemaPath),frozen_v1_sha256:sha('docs/specs/contracts/jd-editor-v1.schema.json'),native_run:run,count:checks.length,failed:checks.filter(x=>!x.passed).length,checks,scope:'Read-only cross-check of recorded native values and captured SDK parameters. Orphan relation deliberately passes shape; App relation validation is separate. No new native process, database, provider or model execution; no UUID-format claim.'};
console.log(JSON.stringify(result,null,2));
process.exitCode=result.failed?1:0;
