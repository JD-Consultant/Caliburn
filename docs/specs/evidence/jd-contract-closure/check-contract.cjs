// Offline contract assertions only: no editor, tool execution, database or provider.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const Ajv = require('ajv/dist/2020').default;
const addFormats = require('ajv-formats');
const root = path.resolve(__dirname, '../../../..');
const schemaPath = path.resolve(root, process.argv[2] || 'docs/specs/contracts/jd-editor-v1.schema.json');
const bytes = fs.readFileSync(schemaPath);
const schema = JSON.parse(bytes);
const ajv = new Ajv({strict: false, allErrors: true, coerceTypes: false, useDefaults: false, removeAdditional: false});
addFormats(ajv);
ajv.addSchema(schema);
const errors = [], checks = [];
for (const key of Object.keys(schema.$defs)) {
  try { if (!ajv.getSchema(`${schema.$id}#/$defs/${key}`)) errors.push({unresolved: key}); }
  catch (error) { errors.push({definition: key, error: error.message}); }
}
function check(name, definition, value, expected) {
  const before = JSON.stringify(value);
  const validate = ajv.getSchema(`${schema.$id}#/$defs/${definition}`);
  const actual = validate(value);
  checks.push({name, definition, expected, actual});
  if (actual !== expected || before !== JSON.stringify(value)) {
    errors.push({name, expected, actual, mutated: before !== JSON.stringify(value), errors: validate.errors});
  }
}
const edit = commands => ({commands});
const set = (values, unset) => ({type:'set_properties', target_ref:'target:cell', ...(values ? {set:values} : {}), ...(unset ? {unset} : {})});
const propertyValues = {source_refs:[], colSizes:[120], marginLeft:0, size:40, colSpan:2, rowSpan:2, background:'red', borders:{}};
for (const [key, value] of Object.entries(propertyValues)) {
  check(`TF01_model_overlap_${key}`, 'JdSetPropertiesCommand', set({[key]:value}, [key]), false);
  const native = {...set({[key]:value}, [key]), target_id:'cell-01'};
  delete native.target_ref;
  check(`TF01_resolved_overlap_${key}`, 'JdResolvedEditCommand', native, false);
}
check('TF01_disjoint_update', 'JdSetPropertiesCommand', set({background:'red'}, ['borders']), true);
check('TF01_set_only', 'JdSetPropertiesCommand', set({background:'red'}), true);
check('TF01_unset_only', 'JdSetPropertiesCommand', set(null, ['background']), true);
check('TF01_empty_update_rejected', 'JdSetPropertiesCommand', {type:'set_properties',target_ref:'t'}, false);
const cell = {type:'td',colSpan:2,rowSpan:1,children:[{type:'p',children:[{text:'繁中內容'}]}]};
check('TF02_numeric_new_cell', 'JdNewElement', cell, true);
check('TF02_new_cell_attributes_rejected', 'JdNewElement', {...cell,attributes:{colspan:'3'}}, false);
check('TF02_set_attributes_rejected', 'JdSetPropertiesCommand', set({attributes:{colspan:'2'}}), false);
check('TF02_unset_attributes_rejected', 'JdSetPropertiesCommand', set(null,['attributes']), false);
check('TF02_zero_span_rejected', 'JdNewElement', {...cell,colSpan:0}, false);
check('TF02_saved_native_attributes_retained', 'JdSavedElement', {...cell,id:'cell-01',attributes:{colspan:'2'},children:[{type:'p',id:'p-01',children:[{text:'繁中內容'}]}]}, true);
const move = {type:'move_content',target_ref:'task:a',destination_ref:'task:b',placement:'after'};
check('TF03_move_without_repeated_sources', 'JdEditModelInput', edit([move]), true);
check('TF03_top_level_sources_rejected', 'JdEditModelInput', {...edit([move]),source_refs:[]}, false);
const insert = {type:'insert_content',target_ref:'target:p',placement:'after',content:[{type:'p',source_refs:['source:01'],children:[{text:'每月核對'}]}]};
check('TF03_new_content_attached_sources', 'JdEditModelInput', edit([insert]), true);
check('TF03_explicit_source_replacement', 'JdEditModelInput', edit([set({source_refs:['source:02']})]), true);
check('TF03_explicit_source_clear', 'JdEditModelInput', edit([set(null,['source_refs'])]), true);
const actions = ['continue','correct_arguments','reread_current','reconcile_operation','wait','stop'];
const closed = {
  committed:['continue'], no_change:['continue'],
  invalid_input:['correct_arguments','stop'], unsupported_content:['correct_arguments','stop'],
  target_missing:['reread_current','stop'], stale_base:['reread_current','stop'],
  engine_failed:['stop'], save_failed:['stop'], operation_conflict:['stop'], busy:['wait','stop']
};
const detail = {code:'fixture_failure',message:'固定失敗，未修改文件',command_index:null};
function result(status, next_action, bound=true, confirmed=true) {
  const success = ['committed','no_change'].includes(status);
  return {
    status, operation_ref:bound?'operation:01':null,
    base_revision_ref:'revision:01', result_revision_ref:success?(status==='no_change'?'revision:01':'revision:02'):null,
    change_ref:success?'change:01':null,
    document_effect:status==='committed'?'committed':status==='outcome_unknown'?'unknown':'unchanged',
    receipt_durability:confirmed?'confirmed':'unconfirmed',
    actual_changes:success?{origin:'ai',before_revision_ref:'revision:01',after_revision_ref:status==='no_change'?'revision:01':'revision:02',native_operations:status==='no_change'?null:[],affected_element_ids:[]}:null,
    error:success?null:detail, next_action
  };
}
for (const [status, permitted] of Object.entries(closed)) {
  for (const action of actions) {
    const value=result(status,action,status!=='busy',status!=='busy');
    check(`ER01_closed_${status}_${action}`, 'JdWriteResult', value, permitted.includes(action));
  }
}
for (const status of ['invalid_input','unsupported_content','target_missing','stale_base','engine_failed','save_failed','operation_conflict','outcome_unknown']) {
  for (const action of actions) {
    check(`ER01_unconfirmed_bound_${status}_${action}`, 'JdWriteResult', result(status,action,true,false), action==='reconcile_operation');
  }
}
for (const action of actions) {
  check(`ER01_prebinding_invalid_${action}`, 'JdWriteResult', result('invalid_input',action,false,false), ['correct_arguments','stop'].includes(action));
}
check('ER01_busy_must_not_bind_operation','JdWriteResult',result('busy','wait',true,false),false);
check('ER01_conflict_requires_original_operation','JdWriteResult',result('operation_conflict','stop',false,true),false);
check('ER01_confirmed_receipt_requires_operation','JdWriteResult',result('invalid_input','stop',false,true),false);
check('ER01_unknown_no_claimed_result','JdWriteResult',{...result('outcome_unknown','reconcile_operation',true,false),result_revision_ref:'revision:02'},false);
check('ER01_manual_uses_same_result_boundary','JdManualSaveResult',result('save_failed','correct_arguments'),false);
for (const status of ['invalid_input','unsupported_content','target_missing','stale_base','engine_failed','save_failed','busy']) {
  const action=closed[status][0]; const value=result(status,action,status!=='busy',status!=='busy');
  check(`ER01_failure_${status}_no_result_ref`,'JdWriteResult',{...value,result_revision_ref:'revision:02'},false);
  check(`ER01_failure_${status}_no_change_ref`,'JdWriteResult',{...value,change_ref:'change:02'},false);
}
check('ER01_conflict_can_locate_original_result','JdWriteResult',{...result('operation_conflict','stop'),result_revision_ref:'revision:02',change_ref:'change:01'},true);
const netZero=result('no_change','continue');
check('DB04_no_change_cannot_publish_transient_operations','JdWriteResult',{...netZero,actual_changes:{...netZero.actual_changes,native_operations:[{type:'insert_text',path:[0,0],offset:0,text:'x'}]}},false);
check('DB04_no_change_has_no_affected_ids','JdWriteResult',{...netZero,actual_changes:{...netZero.actual_changes,affected_element_ids:['p-01']}},false);
const readActions = ['correct_arguments','reread_current','wait','stop'];
const readMatrix = {invalid_input:['correct_arguments','stop'],unsupported_content:['stop'],target_missing:['reread_current','stop'],busy:['wait','stop'],read_failed:['stop']};
for (const [status, allowed] of Object.entries(readMatrix)) {
  for (const action of readActions) {
    const value={status,document_effect:'unchanged',receipt_durability:'unconfirmed',error:detail,next_action:action};
    check(`ER02_${status}_${action}`, 'JdReadFailure', value, allowed.includes(action));
  }
}
const readFailure={status:'read_failed',document_effect:'unchanged',receipt_durability:'unconfirmed',error:detail,next_action:'stop'};
check('ER02_jd_read_infra_failure','JdReadResult',readFailure,true);
check('ER02_change_read_infra_failure','JdChangeReadResult',readFailure,true);
const canonical=JSON.parse(fs.readFileSync(path.join(root,'docs/specs/evidence/jd-official-profile-probe/results/2026-09-09T16-26-50-933Z/F02-A-canonical-input.json'),'utf8'));
check('baseline_full_official_r2_still_valid','JdDocumentValue',canonical,true);
check('baseline_model_cannot_supply_id','JdEditModelInput',edit([{...insert,content:[{...insert.content[0],id:'forbidden'}]}]),false);
check('baseline_current_read_no_model_offsets','JdReadModelInput',{offset:12},false);
check('baseline_read_modes_exclusive','JdReadModelInput',{target_ref:'t',revision_ref:'r'},false);
check('baseline_source_scope_is_not_a_schema_claim','JdEditModelInput',edit([{...insert,content:[{...insert.content[0],source_refs:['syntactically-valid-but-unissued']}]}]),true);
const prose=fs.readFileSync(path.join(root,'docs/specs/2026-09-10-jd-editor-contract-schema.md'),'utf8');
const examples=[...prose.matchAll(/```json\r?\n([\s\S]*?)\r?\n```/g)];
const exampleDefs=['JdEditModelInput','JdWriteResult','JdWriteResult','JdManualSaveClientInput'];
if(examples.length!==exampleDefs.length) errors.push({exampleCount:examples.length,expected:exampleDefs.length});
examples.forEach((match,i)=>check(`current_companion_example_${i+1}`,exampleDefs[i],JSON.parse(match[1]),true));
const sourceExamples=fs.readFileSync(path.join(root,'docs/specs/evidence/2026-09-10-jd-model-input-contract-closure.md'),'utf8');
[...sourceExamples.matchAll(/```json\r?\n([\s\S]*?)\r?\n```/g)].forEach((match,i)=>check(`source_attachment_example_${i+1}`,'JdEditModelInput',JSON.parse(match[1]),true));
const output={schema:path.relative(root,schemaPath).replaceAll('\\','/'),sha256:crypto.createHash('sha256').update(bytes).digest('hex'),validator:`AJV ${require('ajv/package.json').version}`,defs:Object.keys(schema.$defs).length,checks,errors,scope:'schema only; no editor, source validation, database, provider, DOM, or natural-model claim'};
console.log(JSON.stringify(output,null,2));
if(errors.length) process.exitCode=1;
