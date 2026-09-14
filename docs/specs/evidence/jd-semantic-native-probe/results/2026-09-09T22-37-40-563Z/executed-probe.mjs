import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {inspect} from 'node:util';
import {editor,profile,dependencyVersions,clone,flush,node,path,walk,elements,allText,textOf,leafSignature,capture,finiteIssues} from './engine.mjs';

assert.equal(process.version,'v22.12.0');
const expected={'platejs':'53.3.11','@platejs/core':'53.3.11','@platejs/slate':'53.3.10','slate':'0.126.2','@platejs/basic-nodes':'53.0.0','@platejs/list-classic':'53.0.0','@platejs/table':'53.0.9','@platejs/diff':'53.0.0','react':'19.2.4','react-dom':'19.2.4'};
for(const [name,version] of Object.entries(expected))assert.equal(dependencyVersions[name].version,version);
const stamp=new Date().toISOString().replaceAll(/[:.]/g,'-');
const directory=new URL(`./results/${stamp}/`,import.meta.url);mkdirSync(directory,{recursive:true});
const fixture=JSON.parse(readFileSync(new URL('./fixture.json',import.meta.url),'utf8'));
const original=JSON.parse(readFileSync(new URL('../jd-official-profile-probe/results/2026-09-09T16-26-50-933Z/F02-A-canonical-input.json',import.meta.url),'utf8'));
const results=[];
const json=(name,v)=>writeFileSync(new URL(name,directory),JSON.stringify(v,null,2));
const full=(name,v)=>{json(`${name}.json`,v);writeFileSync(new URL(`${name}.inspect.txt`,directory),inspect(v,{depth:null,maxArrayLength:null,maxStringLength:null,compact:false}));};
const hashes={};for(const name of ['README.md','engine.mjs','prepare-fixture.mjs','fresh-editor.mjs','probe.mjs','fixture.json','fixture-mapping.json'])hashes[name]=createHash('sha256').update(readFileSync(new URL(name,import.meta.url))).digest('hex');
json('run-metadata.json',{started:new Date().toISOString(),node:process.version,executable:process.execPath,profile,dependencyVersions,inputHashes:hashes});
// Preserve executed sources before observing any result.
for(const name of ['README.md','engine.mjs','prepare-fixture.mjs','fresh-editor.mjs','probe.mjs'])writeFileSync(new URL(`executed-${name}`,directory),readFileSync(new URL(name,import.meta.url)));
const p=text=>({type:'p',children:[{text}]});
const task=text=>({type:'jd_task',children:[p(text),{type:'jd_outcomes',children:[p('')]},{type:'jd_requirements',children:[p('')]}]});
const afterPath=(e,id)=>{const at=path(e,id);return [...at.slice(0,-1),at.at(-1)+1];};
const batch=(e,fn)=>e.tf.withNewBatch(()=>e.tf.withoutNormalizing(fn));
async function settle(e){e.tf.normalize({force:true});await flush();}
async function baseline(){const e=editor(fixture);await settle(e);return e;}
function assertFinite(v){assert.deepEqual(finiteIssues(v),[]);}
function fresh(name,value){
  json(`${name}-input.json`,value);
  const output=fileURLToPath(new URL(`${name}-fresh.json`,directory));
  const proc=spawnSync(process.execPath,[fileURLToPath(new URL('./fresh-editor.mjs',import.meta.url)),fileURLToPath(new URL(`${name}-input.json`,directory)),output],{encoding:'utf8',timeout:30000});
  full(`${name}-process`,{pid:proc.pid,status:proc.status,signal:proc.signal,error:proc.error&&{code:proc.error.code,message:proc.error.message},stdout:proc.stdout,stderr:proc.stderr});
  if(proc.error)throw proc.error;
  assert.equal(proc.status,0,proc.stderr);
  const saved=JSON.parse(readFileSync(output,'utf8'));assert(saved.ok);assert.notEqual(saved.pid,process.pid);return saved;
}
async function group(id,description,fn){
  const trace={id,description},checks=[];
  const check=(name,test)=>{try{test();checks.push({name,passed:true});}catch(error){checks.push({name,passed:false,message:error.message});}};
  try{await fn(trace,check);}catch(error){trace.exception={message:error.message,stack:error.stack};checks.push({name:'execution',passed:false,message:error.message});}
  const result={id,description,passed:checks.length>0&&checks.every(c=>c.passed),checks};results.push(result);full(id,trace);json(`${id}-checks.json`,result);
  console.log(JSON.stringify({id,passed:result.passed,checks:checks.length,failed:checks.filter(c=>!c.passed)}));
}

await group('F03-A','完整 r2 v2 分組／K-S 項目、空草稿與新程序重開',async(t,check)=>{
  t.input=fixture;const e=editor(fixture);const batches=capture(e);await settle(e);t.canonical=clone(e.children);t.batches=batches;
  check('全部 r2 文字及含格式 leaf 序列保留',()=>{assert.equal(allText(t.canonical),allText(original));assert.deepEqual(leafSignature(t.canonical),leafSignature(original));});
  check('四種普通 block、兩組數量／位置及兩組端點符合候選',()=>{
    assertFinite(t.canonical);assert.equal(elements(t.canonical).filter(n=>n.type==='jd_task').length,8);
    assert.equal(elements(t.canonical).filter(n=>n.type==='jd_knowledge').length,5);assert.equal(elements(t.canonical).filter(n=>n.type==='jd_skill').length,5);
    for(const type of ['jd_outcomes','jd_requirements','jd_knowledge','jd_skill'])assert(e.plugins[type]);
    for(const prior of elements(original).filter(n=>n.source_refs))assert.deepEqual(node(e,prior.id).source_refs,prior.source_refs);
  });
  t.reopened=fresh('F03-A',t.canonical);
  check('普通 JSON／不同 PID 的新 editor normalize 後全值相等',()=>{assert.deepEqual(t.reopened.value,t.canonical);assertFinite(t.reopened.value);});
  const blank=editor([{type:'jd_section',section_kind:'work',children:[task('')]}]);await settle(blank);t.emptyDraft=clone(blank.children);
  check('無 Duty／無 links／空敘述及空兩組可由原生補 ID 並保留',()=>{assertFinite(t.emptyDraft);assert.equal(allText(t.emptyDraft),'');assert.equal(elements(t.emptyDraft).filter(n=>n.type==='jd_task').length,1);});
});

await group('F03-B','先建立無 links 內容，讀原生 ID 再設引用／續改',async(t,check)=>{
  const e=await baseline();t.before=clone(e.children);const batches=capture(e);
  const newK={type:'jd_knowledge',children:[p('【F03 合成】交接狀態知識'),p('僅作原生首建測試，不是 r2 新事實。')]};
  const newS={type:'jd_skill',children:[p('【F03 合成】交接整理技能'),p('僅作原生首建測試，不是 r2 新事實。')]};
  const newTask=task('【F03 合成】整理交接資訊');t.insertInputs=clone([newK,newS,newTask]);
  batch(e,()=>{
    e.tf.insertNodes(newK,{at:[...path(e,'section-knowledge'),node(e,'section-knowledge').children.length]});
    e.tf.insertNodes(newS,{at:[...path(e,'section-skills'),node(e,'section-skills').children.length]});
    e.tf.insertNodes(newTask,{at:[...path(e,'section-work'),node(e,'section-work').children.length]});
  });await settle(e);t.unlinked=clone(e.children);
  const k=node(e,'section-knowledge').children.at(-1),s=node(e,'section-skills').children.at(-1),newT=node(e,'section-work').children.at(-1);
  t.assigned={knowledge:k.id,skill:s.id,task:newT.id};
  check('輸入無 IDs／links；原生建立完整未連線草稿',()=>{
    assert(elements(t.insertInputs).every(n=>!('id'in n)&&!('knowledge_ids'in n)&&!('skill_ids'in n)));
    assertFinite(t.unlinked);assert(!('knowledge_ids'in newT));assert(!('skill_ids'in newT));assert(k.id&&s.id&&newT.id);
  });
  t.unlinkedReopened=fresh('F03-B-unlinked',t.unlinked);
  check('未連線首建中間稿可 JSON 新程序重開',()=>assert.deepEqual(t.unlinkedReopened.value,t.unlinked));
  e.tf.setNodes({knowledge_ids:[k.id],skill_ids:[s.id]},{at:path(e,newT.id)});
  const sharedK=node(e,'f03-jd_knowledge-2');const oldK=clone(sharedK);const suffix='【F03 合成續編】';
  e.tf.insertText(suffix,{at:e.api.end(path(e,sharedK.children[0].id))});
  const req=node(e,'f03-task-4-requirements');const oldReq=clone(req);
  e.tf.insertText('【F03 合成要求補充】',{at:e.api.end(path(e,req.id))});await settle(e);
  t.after=clone(e.children);t.batches=batches;
  check('setNodes 只建立指定 Task 兩組 links，共享 K 改名保留身分',()=>{
    assertFinite(t.after);assert.deepEqual(node(e,newT.id).knowledge_ids,[k.id]);assert.deepEqual(node(e,newT.id).skill_ids,[s.id]);
    assert.equal(textOf(node(e,sharedK.id)),textOf(oldK.children[0])+suffix+oldK.children.slice(1).map(textOf).join(''));assert.equal(node(e,sharedK.id).id,oldK.id);
    assert.deepEqual(node(e,'task-7').knowledge_ids,['f03-jd_knowledge-2']);assert(node(e,'task-4').knowledge_ids.includes('f03-jd_knowledge-2'));
    assert.equal(textOf(node(e,req.id)),textOf(oldReq)+'【F03 合成要求補充】');
    assert.deepEqual(node(e,'task-8'),elements(t.before).find(n=>n.id==='task-8'));
  });
  check('原生 set_node operations 真的包含兩组 ID 陣列且普通 JSON 保留',()=>{
    const ops=batches.flatMap(b=>b.operations);assert(ops.some(o=>o.type==='set_node'&&o.newProperties.knowledge_ids?.[0]===k.id&&o.newProperties.skill_ids?.[0]===s.id));
    assert.deepEqual(JSON.parse(JSON.stringify(ops)),ops);
  });
  t.reopened=fresh('F03-B-final',t.after);check('連線與完整續編結果新程序重開全等',()=>{assert.deepEqual(t.reopened.value,t.after);assertFinite(t.reopened.value);});
});

await group('F03-C','固定 Task 複製／包含 K-S 複製與明列映射／移動',async(t,check)=>{
  const e=await baseline();t.before=clone(e.children);const batches=capture(e);
  const copiedInput=n=>{const result=clone(n);for(const el of elements([result]))delete el.id;return result;};
  const sourceTask=clone(node(e,'task-7')),at=afterPath(e,'task-7');e.tf.insertNodes(copiedInput(sourceTask),{at});await settle(e);
  const taskOnly=e.api.node(at)[0];t.taskOnlyCopy=clone(taskOnly);
  check('只複製 Task：全部複本 ID 新配，共享定義及 links 保留',()=>{
    const oldIds=new Set(elements(t.before).map(n=>n.id));assert(elements([taskOnly]).every(n=>!oldIds.has(n.id)));
    assert.equal(textOf(taskOnly),textOf(sourceTask));assert.deepEqual(taskOnly.knowledge_ids,sourceTask.knowledge_ids);assert.deepEqual(taskOnly.skill_ids,sourceTask.skill_ids);
    assert.deepEqual(node(e,'f03-jd_knowledge-2'),elements(t.before).find(n=>n.id==='f03-jd_knowledge-2'));
  });
  const oldK=clone(node(e,'f03-jd_knowledge-2')),oldS=clone(node(e,'f03-jd_skill-3')),oldT=clone(node(e,'task-4'));
  const kp=afterPath(e,oldK.id);e.tf.insertNodes(copiedInput(oldK),{at:kp});await settle(e);const newK=e.api.node(kp)[0];
  const sp=afterPath(e,oldS.id);e.tf.insertNodes(copiedInput(oldS),{at:sp});await settle(e);const newS=e.api.node(sp)[0];
  const tp=afterPath(e,oldT.id);e.tf.insertNodes(copiedInput(oldT),{at:tp});await settle(e);const newT=e.api.node(tp)[0];
  t.nativeBeforeMapping=clone(e.children);t.fixtureMapping={knowledge:{from:oldK.id,to:newK.id},skill:{from:oldS.id,to:newS.id},task:{from:oldT.id,to:newT.id}};
  check('原生只配節點 IDs，不自動重寫自訂 links',()=>{assert.deepEqual(newT.knowledge_ids,oldT.knowledge_ids);assert.deepEqual(newT.skill_ids,oldT.skill_ids);assert.notEqual(newK.id,oldK.id);assert.notEqual(newS.id,oldS.id);});
  // Exact fixture membership and order; not a generic discovery/remapping algorithm.
  e.tf.setNodes({knowledge_ids:[newK.id,'f03-jd_knowledge-4'],skill_ids:[newS.id,'f03-jd_skill-4']},{at:path(e,newT.id)});await settle(e);
  const beforeMove=clone(node(e,'task-8'));e.tf.moveNodes({at:path(e,'task-8'),to:[...path(e,'duty-1'),node(e,'duty-1').children.length]});await settle(e);
  t.after=clone(e.children);t.batches=batches;
  check('明列映射只改複本內部 links；外部共用及原引用者不變；Task8移動保全',()=>{
    assertFinite(t.after);assert.deepEqual(node(e,newT.id).knowledge_ids,[newK.id,'f03-jd_knowledge-4']);assert.deepEqual(node(e,newT.id).skill_ids,[newS.id,'f03-jd_skill-4']);
    assert.deepEqual(node(e,'task-4'),oldT);assert.deepEqual(node(e,'task-7'),sourceTask);assert.deepEqual(node(e,'task-8'),beforeMove);
    assert.equal(textOf(newK),textOf(oldK));assert.equal(textOf(newS),textOf(oldS));
  });
  t.reopened=fresh('F03-C',t.after);check('複本映射／移動完整 JSON 新程序全等',()=>{assert.deepEqual(t.reopened.value,t.after);assertFinite(t.reopened.value);});
});

await group('F03-D','原生 unwrap／delete 與最終候選邊界',async(t,check)=>{
  async function variant(name,fn){const e=await baseline();const before=clone(e.children),batches=capture(e);fn(e);await settle(e);const result={before,after:clone(e.children),issues:finiteIssues(e.children),batches};t[name]=result;return {e,...result};}
  const alone=await variant('singleTaskUnwrap',e=>e.tf.unwrapNodes({at:path(e,'task-4')}));
  check('單 unwrap 原生執行但產生非法 group parent，不假稱原生拒絕',()=>{assert.equal(allText(alone.after),allText(alone.before));assert(alone.issues.some(x=>x.code==='group_parent'));assert(!elements(alone.after).some(n=>n.id==='task-4'));});
  const flat=await variant('explicitThreeUnwrap',e=>batch(e,()=>{
    e.tf.unwrapNodes({at:path(e,'f03-task-4-outcomes')});e.tf.unwrapNodes({at:path(e,'f03-task-4-requirements')});e.tf.unwrapNodes({at:path(e,'task-4')});
  }));
  check('明示同批先兩組後Task：全文／文字格式保留、最終有效',()=>{
    assertFinite(flat.after);assert.equal(allText(flat.after),allText(flat.before));assert.deepEqual(leafSignature(flat.after),leafSignature(flat.before));
    assert.deepEqual(node(flat.e,'task-7'),elements(flat.before).find(n=>n.id==='task-7'));assert.deepEqual(node(flat.e,'f03-jd_knowledge-2'),elements(flat.before).find(n=>n.id==='f03-jd_knowledge-2'));
    assert(!elements(flat.after).some(n=>['task-4','f03-task-4-outcomes','f03-task-4-requirements'].includes(n.id)));
  });
  t.flatReopened=fresh('F03-D-flatten',flat.after);check('合法 flatten 新程序全等',()=>{assert.deepEqual(t.flatReopened.value,flat.after);assertFinite(t.flatReopened.value);});
  const removedGroup=await variant('singleGroupDelete',e=>e.tf.removeNodes({at:path(e,'f03-task-4-requirements')}));
  check('單刪群組原生不阻擋，但 final group-count 不成立',()=>assert(removedGroup.issues.some(x=>x.code==='group_count'&&x.id==='task-4'&&x.type==='jd_requirements')));
  const clear=await variant('clearGroupBody',e=>batch(e,()=>{
    const at=path(e,'f03-task-4-requirements');for(let i=node(e,'f03-task-4-requirements').children.length-1;i>=0;i--)e.tf.removeNodes({at:[...at,i]});
    e.tf.insertNodes(p(''),{at:[...at,0]});
  }));
  check('清空內容保留原要求組與合法空 p，不生成假工作',()=>{assertFinite(clear.after);assert.equal(textOf(node(clear.e,'f03-task-4-requirements')),'');assert.equal(node(clear.e,'f03-task-4-requirements').children[0].type,'p');assert.deepEqual(node(clear.e,'f03-task-4-outcomes'),elements(clear.before).find(n=>n.id==='f03-task-4-outcomes'));});
  const dangling=await variant('deleteReferencedKnowledge',e=>e.tf.removeNodes({at:path(e,'f03-jd_knowledge-2')}));
  check('刪被引用K原生不阻擋，固定端點檢查辨識所有受影響Task',()=>{
    assert.deepEqual(dangling.issues.filter(x=>x.code==='link_target').map(x=>x.id).sort(),['task-4','task-7']);assert(elements(dangling.after).some(n=>n.id==='task-4'));assert(elements(dangling.after).some(n=>n.id==='task-7'));
  });
  const unlinked=await variant('explicitUnlinkThenDelete',e=>batch(e,()=>{
    e.tf.setNodes({knowledge_ids:['f03-jd_knowledge-4']},{at:path(e,'task-4')});e.tf.setNodes({knowledge_ids:[]},{at:path(e,'task-7')});e.tf.removeNodes({at:path(e,'f03-jd_knowledge-2')});
  }));
  check('同批明示解除全部相關links後可刪K，Task／其他引用不連帶刪除',()=>{
    assertFinite(unlinked.after);assert.equal(elements(unlinked.after).filter(n=>n.type==='jd_task').length,8);assert.deepEqual(node(unlinked.e,'task-4').knowledge_ids,['f03-jd_knowledge-4']);assert.deepEqual(node(unlinked.e,'task-7').knowledge_ids,[]);
    assert.deepEqual(node(unlinked.e,'task-8'),elements(unlinked.before).find(n=>n.id==='task-8'));assert.deepEqual(node(unlinked.e,'task-4').skill_ids,['f03-jd_skill-3','f03-jd_skill-4']);
  });
  t.unlinkedReopened=fresh('F03-D-unlink-delete',unlinked.after);check('合法解除／刪除後新程序全等',()=>{assert.deepEqual(t.unlinkedReopened.value,unlinked.after);assertFinite(t.unlinkedReopened.value);});
});

const summary={node:process.version,profile,results,passed:results.filter(r=>r.passed).length,failed:results.filter(r=>!r.passed).length,checkCount:results.reduce((n,r)=>n+r.checks.length,0)};
json('summary.json',summary);writeFileSync(new URL('./latest-run.txt',import.meta.url),fileURLToPath(directory));console.log(JSON.stringify({directory:fileURLToPath(directory),passed:summary.passed,failed:summary.failed,checks:summary.checkCount}));if(summary.failed)process.exitCode=1;
