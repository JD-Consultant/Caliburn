import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
const here = name => new URL(name, import.meta.url);
const source = new URL('../jd-official-profile-probe/results/2026-09-09T16-26-50-933Z/F02-A-canonical-input.json', import.meta.url);
const bytes = readFileSync(source), before = JSON.parse(bytes), value = structuredClone(before);
const walk = ns => ns.flatMap(n => [n, ...(n.children ? walk(n.children) : [])]);
const get = id => { const ns = walk(value).filter(n => n.id === id); assert.equal(ns.length, 1); return ns[0]; };
const text = n => typeof n.text === 'string' ? n.text : n.children.map(text).join('');
const leaves = ns => walk(ns).filter(n => typeof n.text === 'string' && (n.text.length || Object.keys(n).length > 1));
const p = id => ({ type:'p', id, children:[{text:''}] });

// These IDs were read from the fixed full r2 fixture. No prefix/text classifier.
const taskMapping = [
  { task:'task-1', list:'r2-38', body:[], outcomes:['r2-35'], requirements:['r2-37'] },
  { task:'task-2', list:'r2-42', body:[], outcomes:[], requirements:['r2-41'] },
  { task:'task-3', list:'r2-49', body:[], outcomes:['r2-46'], requirements:['r2-48'] },
  { task:'task-4', list:'r2-60', body:[], outcomes:[], requirements:['r2-59'] },
  { task:'task-5', list:'r2-67', body:[], outcomes:['r2-64'], requirements:['r2-66'] },
  { task:'task-6', list:'r2-73', body:[], outcomes:['r2-70'], requirements:['r2-72'] },
  { task:'task-7', list:'r2-80', body:['r2-77'], outcomes:[], requirements:['r2-79'] },
  { task:'task-8', list:'r2-88', body:['r2-83'], outcomes:['r2-85'], requirements:['r2-87'] },
];
for (const map of taskMapping) {
  const task=get(map.task), list=get(map.list), originalItems=list.children;
  assert.deepEqual([...map.body,...map.outcomes,...map.requirements], originalItems.map(n=>n.id));
  const base=task.children.filter(n=>n.id!==map.list);
  assert.equal(task.children.length-base.length,1);
  let usedOriginalList=false;
  const block = (which, ids) => {
    if (!ids.length) return [];
    const result={...structuredClone(list), id:usedOriginalList?`f03-${map.task}-${which}-list`:list.id, children:ids.map(id=>originalItems.find(n=>n.id===id))};
    usedOriginalList=true;
    return [result];
  };
  const narrative=block('body',map.body), outputs=block('outcomes',map.outcomes), requirements=block('requirements',map.requirements);
  task.children=[...base,...narrative,
    {type:'jd_outcomes',id:`f03-${map.task}-outcomes`,children:outputs.length?outputs:[p(`f03-${map.task}-empty-outcome`)]},
    {type:'jd_requirements',id:`f03-${map.task}-requirements`,children:requirements.length?requirements:[p(`f03-${map.task}-empty-requirement`)]},
  ];
}
const itemMapping=[
  {section:'section-knowledge',table:'knowledge-table',header:'r2-94',type:'jd_knowledge',rows:['r2-99','r2-104','r2-109','r2-114','r2-119']},
  {section:'section-skills',table:'skills-table',header:'r2-125',type:'jd_skill',rows:['r2-130','r2-135','r2-140','r2-145','r2-150']},
];
for (const map of itemMapping) {
  const section=get(map.section), table=get(map.table);
  assert.deepEqual(table.children.map(n=>n.id),[map.header,...map.rows]);
  const flattenCells=row=>row.children.flatMap(cell=>cell.children);
  const replacement=[...flattenCells(table.children[0]),...table.children.slice(1).map((row,index)=>({type:map.type,id:`f03-${map.type}-${index+1}`,children:flattenCells(row)}))];
  const index=section.children.findIndex(n=>n.id===map.table);
  section.children.splice(index,1,...replacement);
}
const syntheticLinks={
  'task-4':{knowledge_ids:['f03-jd_knowledge-2','f03-jd_knowledge-4'],skill_ids:['f03-jd_skill-3','f03-jd_skill-4']},
  'task-7':{knowledge_ids:['f03-jd_knowledge-2'],skill_ids:['f03-jd_skill-3']},
  'task-8':{knowledge_ids:['f03-jd_knowledge-5'],skill_ids:['f03-jd_skill-5']},
};
for(const [id,links] of Object.entries(syntheticLinks))Object.assign(get(id),links);
assert.equal(value.map(text).join(''),before.map(text).join(''));
assert.deepEqual(leaves(value),leaves(before));
const oldElements=walk(before).filter(n=>n.children), newElements=walk(value).filter(n=>n.children), newIds=new Set(newElements.map(n=>n.id));
const retired=oldElements.filter(n=>!newIds.has(n.id)).map(n=>({id:n.id,type:n.type,reason:'fixed K/S table-to-complete-item fixture mapping; no content deleted'}));
for(const old of oldElements.filter(n=>n.source_refs)){
  const found=newElements.find(n=>n.id===old.id);
  assert(found,`Retired source-bearing node ${old.id} requires explicit preservation review`);
  assert.deepEqual(found.source_refs,old.source_refs);
}
assert.equal(newIds.size,newElements.length);
const mapping={sourceFile:source.href,sourceSha256:createHash('sha256').update(bytes).digest('hex'),taskMapping,itemMapping,syntheticLinks,syntheticLinksAreNotEmployeeFacts:true,retiredWrapperIds:retired,preservedTextAndMarkedLeaves:true,sourceRefPolicy:'All prior source-bearing Element IDs and source_refs retained exactly; no new source facts'};
writeFileSync(here('fixture.json'),JSON.stringify(value,null,2));
writeFileSync(here('fixture-mapping.json'),JSON.stringify(mapping,null,2));
console.log(JSON.stringify({ok:true,retiredWrapperCount:retired.length,originalElements:oldElements.length,newElements:newElements.length,sourceSha256:mapping.sourceSha256}));

