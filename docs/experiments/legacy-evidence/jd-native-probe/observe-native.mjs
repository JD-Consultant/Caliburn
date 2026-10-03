import assert from 'node:assert/strict';
import {writeFileSync} from 'node:fs';
import {createSlateEditor} from 'platejs';

// Observe native Slate batches; do not repair computeDiff or persist a history.
const clone=value=>JSON.parse(JSON.stringify(value));
const results=[];
const observed={};
async function observe(name,value,mutate,check){
  const batches=[];
  const e=createSlateEditor({value:clone(value)});
  const previous=e.onChange;
  e.onChange=options=>{batches.push({operations:clone(e.operations),value:clone(e.children),marks:clone(e.marks)});previous(options);};
  try {
    mutate(e); await new Promise(resolve=>setImmediate(resolve));
    check(e,batches);
    assert.equal(e.operations.length,0);
    results.push({name,passed:true});
  }catch(error){results.push({name,passed:false,error:error.message});}
  observed[name]={batches,value:clone(e.children),marks:clone(e.marks),remainingOperations:e.operations.length};
}
await observe('falsy leaf via native setNodes',[{id:'a',type:'p',children:[{text:'工作',score:1}]}],e=>e.tf.setNodes({score:0},{at:[0,0]}),(e,batches)=>{
  assert.equal(e.children[0].children[0].score,0);
  const op=batches.flatMap(b=>b.operations).find(op=>op.type==='set_node');
  assert.equal(op.properties.score,1);assert.equal(op.newProperties.score,0);
});
await observe('empty text formatting via native setNodes',[{id:'a',type:'p',children:[{text:'',bold:true}]}],e=>e.tf.setNodes({bold:null,italic:true},{at:[0,0]}),(e,batches)=>{
  assert.equal(e.children[0].children[0].italic,true);assert.equal(e.children[0].children[0].bold,undefined);
  const op=batches.flatMap(b=>b.operations).find(op=>op.type==='set_node');
  assert.equal(op.properties.bold,true);assert.equal(op.newProperties.italic,true);
});
await observe('collapsed caret format is not yet document text mutation',[{id:'a',type:'p',children:[{text:''}]}],e=>{
  e.tf.select({path:[0,0],offset:0});e.tf.addMark('italic',true);
},(e,batches)=>{
  assert.equal(e.marks.italic,true);assert.deepEqual(e.children[0].children,[{text:''}]);
  assert(!batches.flatMap(b=>b.operations).some(op=>op.type==='set_node'));
});
const report={note:'Native per-batch observation only. Original 13-case report and its two failures are unchanged.',total:results.length,passed:results.filter(r=>r.passed).length,failed:results.filter(r=>!r.passed).length,results,observed};
writeFileSync('results/native-observation.json',JSON.stringify(report,null,2));
console.log(JSON.stringify({total:report.total,passed:report.passed,failed:report.failed,results},null,2));
if(report.failed)process.exitCode=1;
