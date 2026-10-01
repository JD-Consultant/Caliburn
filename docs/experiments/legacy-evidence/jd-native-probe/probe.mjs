import assert from 'node:assert/strict';
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {createSlateEditor, createSlatePlugin, NodeIdPlugin} from 'platejs';
import {computeDiff} from '@platejs/diff';

// Throwaway native-capability probe. Paths are supplied by this deterministic
// fixture, never by an LLM. This is not a JD schema or application adapter.
const clone = value => JSON.parse(JSON.stringify(value));
const p = (id, text, props = {}) => ({id, type: 'p', ...props, children: [{text}]});
const fixture = [
  p('purpose', '將確認的需求轉成可使用的介面；尚待確認發布責任。'),
  {id: 'd1', type: 'jd_duty', title: '需求與交付', children: [
    {id: 't1', type: 'jd_task', sourceRefs: ['source:1'], children: [
      p('t1-description', '協助確認需求。'),
      p('t1-condition', '對特殊案件提供建議；核准由專案經理負責。'),
    ]},
    {id: 't2', type: 'jd_task', sourceRefs: ['source:2'], children: [
      p('t2-description', '協助確認需求。'),
      p('t2-condition', '僅有維護約定的案件按月檢查；其他案件不適用。'),
    ]},
  ]},
  {id: 'd2', type: 'jd_duty', title: '其他工作', children: [
    {id: 't3', type: 'jd_task', children: [p('t3-description', '處理上線後異常，保留未解事項。')]},
  ]},
  {id: 'knowledge', type: 'jd_knowledge', scope: {uses: ['整合', '診斷']}, children: [p('k1', '理解介面契約與非同步狀態。')]},
  {id: 'unassigned', type: 'jd_unassigned', children: [p('u1', '先記錄交接成果，任務歸屬尚未確認。')]},
];
const customTypes = ['jd_duty', 'jd_task', 'jd_knowledge', 'jd_unassigned'];
let nextId = 0;
const editor = value => createSlateEditor({
  value: clone(value),
  plugins: [
    NodeIdPlugin.configure({options: {idCreator: () => `probe-new-${++nextId}`}}),
    ...customTypes.map(key => createSlatePlugin({key, node: {isElement: true}})),
  ],
});
const results = [];
const output = {};
const record = (name, test) => {
  try { const detail = test(); results.push({name, passed: true, detail}); }
  catch (e) { results.push({name, passed: false, error: e.message}); }
};
const walk = (value, fn) => value.forEach(node => {fn(node); if(node.children) walk(node.children, fn);});
const changes = value => {const found=[]; walk(value, n=>{if(n.diffOperation) found.push({id:n.id,text:n.text,operation:n.diffOperation});}); return found;};
const compare = (name, before, after, options = {}) => {
  const diff = computeDiff(clone(before), clone(after), options);
  output[name] = {before,after,diff};
  return changes(diff);
};
mkdirSync('results', {recursive:true});

record('native initialization preserves complete nested fixture', () => {
  const e=editor(fixture); e.tf.normalize({force:true});
  assert.deepEqual(clone(e.children),fixture);
});
record('targeted traditional Chinese edit preserves repeated text elsewhere', () => {
  const e=editor(fixture);
  e.tf.insertText('協助整理需求。', {at:{anchor:{path:[1,1,0,0],offset:0},focus:{path:[1,1,0,0],offset:7}}});
  assert.equal(e.children[1].children[0].children[0].children[0].text,'協助確認需求。');
  assert.equal(e.children[1].children[1].children[0].children[0].text,'協助整理需求。');
  assert.deepEqual(e.children[1].children[1].children[1],fixture[1].children[1].children[1]);
  assert.deepEqual(e.children[1].children[1].sourceRefs,['source:2']);
  assert(changes(computeDiff(fixture,clone(e.children))).length>0);
});
record('move task across duties preserves identity and all children', () => {
  const e=editor(fixture); const original=clone(e.children[1].children[1]);
  e.tf.moveNodes({at:[1,1],to:[2,1]});
  assert.deepEqual(clone(e.children[2].children[1]),original);
  assert.deepEqual(clone(e.children[1].children[0]),fixture[1].children[0]);
  const delta=compare('move-task',fixture,clone(e.children));
  assert(delta.some(x=>x.operation.type==='delete'));
  assert(delta.some(x=>x.operation.type==='insert'));
  return {diffOperations:delta.map(x=>x.operation.type)};
});
record('split paragraph gives fresh identity and preserves source metadata', () => {
  const value=[p('split','繁中段落拆分測試。',{sourceRefs:['source:3']})];
  const e=editor(value); e.tf.splitNodes({at:{path:[0,0],offset:4}});
  assert.equal(e.children.length,2);
  assert.equal(e.children.map(n=>n.children.map(t=>t.text).join('')).join(''),'繁中段落拆分測試。');
  assert.notEqual(e.children[0].id,e.children[1].id);
  assert.deepEqual(e.children.map(n=>n.sourceRefs),[['source:3'],['source:3']]);
  output.split=clone(e.children);
  return {ids:e.children.map(n=>n.id)};
});
record('undo redo restore native text operation', () => {
  const e=editor(fixture); const before=clone(e.children);
  e.tf.withNewBatch(()=>e.tf.insertText('補充：',{at:{path:[0,0],offset:0}}));
  const after=clone(e.children); e.tf.undo(); assert.deepEqual(clone(e.children),before);
  e.tf.redo(); assert.deepEqual(clone(e.children),after);
});
record('JSON disk roundtrip creates fresh editor without content or metadata loss', () => {
  const e=editor(fixture); e.tf.setNodes({title:'已更名職責'},{at:[1]});
  const before=clone(e.children); writeFileSync('results/clean-document.json',JSON.stringify(before,null,2));
  const reopened=editor(JSON.parse(readFileSync('results/clean-document.json','utf8')));
  reopened.tf.normalize({force:true}); assert.deepEqual(clone(reopened.children),before);
  return {note:'JSON file I/O only; not PostgreSQL, crash recovery or durable undo history'};
});
record('marks additions and removals are reported', () => {
  for(const [name,before,after] of [
    ['mark-add',[p('m','工作')],[{...p('m','工作'),children:[{text:'工作',bold:true}]}]],
    ['mark-remove',[{...p('m','工作'),children:[{text:'工作',bold:true}]}],[p('m','工作')]],
  ]) assert(compare(name,before,after).some(x=>x.operation.type==='update'));
});
record('element properties include falsy values and object metadata', () => {
  const before=[p('x','工作',{score:1,verified:true,scope:{name:'一般'}})];
  const after=[p('x','工作',{score:0,verified:false,scope:{name:'特殊'}})];
  const delta=compare('element-properties',before,after);
  assert(delta.some(x=>x.operation.newProperties?.score===0));
  assert(delta.some(x=>x.operation.newProperties?.verified===false));
  assert(delta.some(x=>x.operation.newProperties?.scope?.name==='特殊'));
});
record('element property removal remains visible', () => {
  const delta=compare('element-remove-prop',[p('x','工作',{scope:'僅特殊案件'})],[p('x','工作')]);
  assert(delta.some(x=>x.operation.properties?.scope==='僅特殊案件'));
});
record('same ID with simultaneous attributes and text change remains visible', () => {
  const before=[p('x','協助上線',{scope:'特殊'})];
  const after=[p('x','負責核准上線',{scope:'全部'})];
  const delta=compare('same-id-both-change',before,after,{elementsAreRelated:(a,b)=>a.id===b.id});
  assert(delta.length>0);
  const diff=output['same-id-both-change'].diff;
  const readOnlyRepresentation=editor(diff); readOnlyRepresentation.tf.normalize({force:true});
  assert(changes(readOnlyRepresentation.children).some(x=>x.operation.type==='delete'));
  assert(changes(readOnlyRepresentation.children).some(x=>x.operation.type==='insert'));
  output['normalized-diff']=clone(readOnlyRepresentation.children);
  return {diffOperations:delta.map(x=>x.operation.type),ids:readOnlyRepresentation.children.map(n=>n.id)};
});
record('canonical snapshots stay unchanged by computeDiff', () => {
  const before=clone(fixture), after=clone(fixture); after[0].children[0].text+='補充。';
  const beforeString=JSON.stringify(before),afterString=JSON.stringify(after);
  computeDiff(before,after); assert.equal(JSON.stringify(before),beforeString); assert.equal(JSON.stringify(after),afterString);
});

// Counterexamples test genuine boundaries. A failed case is reported, not
// patched away or converted into a passing expectation.
record('counterexample: falsy text-leaf metadata preserved in diff output', () => {
  const before=[{...p('x','工作'),children:[{text:'工作',score:1}]}];
  const after=[{...p('x','工作'),children:[{text:'工作',score:0}]}];
  assert(compare('leaf-falsy',before,after).some(x=>x.operation.newProperties?.score===0));
});
record('counterexample: empty text mark-only change is reported', () => {
  const before=[{...p('x',''),children:[{text:'',bold:true}]}];
  const after=[{...p('x',''),children:[{text:'',italic:true}]}];
  assert(compare('empty-mark',before,after).length>0);
});
const summary={runtime:process.version,packages:{platejs:'53.3.11','@platejs/diff':'53.0.0'},total:results.length,passed:results.filter(r=>r.passed).length,failed:results.filter(r=>!r.passed).length,results};
writeFileSync('results/native-results.json',JSON.stringify(summary,null,2));
writeFileSync('results/native-diffs.json',JSON.stringify(output,null,2));
console.log(JSON.stringify(summary,null,2));
if(summary.failed) process.exitCode=1;
