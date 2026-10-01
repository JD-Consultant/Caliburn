const fs = require('node:fs');
const path = require('node:path');
const Ajv2020 = require('ajv/dist/2020').default;
const addFormats = require('ajv-formats');
const root = 'S:/caliburn';
const read = p => JSON.parse(fs.readFileSync(path.join(root, p), 'utf8'));
const schema = read('docs/specs/contracts/jd-editor-v1.schema.json');
const ajv = new Ajv2020({strict:false, allErrors:true, coerceTypes:false, useDefaults:false, removeAdditional:false});
addFormats(ajv);
ajv.addSchema(schema);
const errors = [];
const checks = [];
for (const name of Object.keys(schema.$defs)) {
  try { if (!ajv.getSchema(`${schema.$id}#/$defs/${name}`)) errors.push(`unresolved:${name}`); }
  catch(e) { errors.push(`compile:${name}:${e.message}`); }
}
function check(name, definition, value, expected) {
  const validator = ajv.getSchema(`${schema.$id}#/$defs/${definition}`);
  if (!validator) { errors.push(`missing:${definition}`); return; }
  const actual = validator(value);
  checks.push({name,definition,expected,actual});
  if (actual !== expected) errors.push({name,validationErrors:validator.errors});
}
const canonical = read('docs/specs/evidence/jd-official-profile-probe/results/2026-09-09T16-26-50-933Z/F02-A-canonical-input.json');
check('official_full_r2_canonical','JdDocumentValue',canonical,true);
const prose=fs.readFileSync(path.join(root,'docs/specs/2026-09-10-jd-editor-contract-schema.md'),'utf8');
const examples=[...prose.matchAll(/```json\r?\n([\s\S]*?)\r?\n```/g)];
const definitions=['JdEditModelInput','JdWriteResult','JdWriteResult','JdManualSaveClientInput'];
if (examples.length !== definitions.length) errors.push('example count changed: inspect mapping');
examples.forEach((x,i)=>{if(definitions[i]) check(`document_example_${i+1}`,definitions[i],JSON.parse(x[1]),true);});
const range={anchor:{path:[0,0],offset:0},focus:{path:[0,0],offset:2}};
const value=[{type:'p',id:'p-01',children:[{text:'每月核對'}]}];
check('browser_selection_capture','JdSelectionCaptureClientInput',{base_revision_ref:'jd-revision:01',range},true);
check('manual_uuid_format','JdManualSaveClientInput',{request_key:'not-a-uuid',base_revision_ref:'jd-revision:01',value},false);
check('model_cannot_supply_capture','JdReadModelInput',{jd_selection:{base_revision_ref:'jd-revision:01',range}},false);
check('new_content_cannot_supply_id','JdEditModelInput',{commands:[{type:'insert_content',target_ref:'t',placement:'after',content:value}],source_refs:[]},false);
check('native_selection_request','JdPlateReadSelectionRequest',{profile:{format_version:1,engine_profile:'jd-plate-clean-v1'},value,range},true);
check('native_selection_result','JdPlateReadSelectionResult',{ok:true,target_id:'p-01',range,fragment:[{type:'p',id:'p-01',children:[{text:'每月'}]}]},true);
console.log(JSON.stringify({validator:`ajv ${require('ajv/package.json').version}`,defs:Object.keys(schema.$defs).length,checks,errors,scope:'schema only; no editor execution, database, provider, DOM, or semantic validation'},null,2));
if(errors.length) process.exitCode=1;
