// Static artifact extraction / provenance only. Does not import or run an editor.
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const read=(base,name)=>JSON.parse(readFileSync(new URL(name,base),'utf8'));
const write=(name,value)=>writeFileSync(new URL(name,import.meta.url),JSON.stringify(value,null,2));
const hash=file=>createHash('sha256').update(readFileSync(file)).digest('hex');
const old=new URL('../jd-official-profile-probe/',import.meta.url);
const installed=new URL('../../../../.research-tmp/jd-editor-official-profile-probe/',import.meta.url);
const current=new URL('./results/2026-09-09T22-38-20-172Z/',import.meta.url);
const v=read(import.meta.url,'fixture.json'),mapping=read(import.meta.url,'fixture-mapping.json');
const walk=ns=>ns.flatMap(n=>[n,...(n.children?walk(n.children):[])]);
const els=walk(v).filter(n=>n.children),counts={};for(const n of els)counts[n.type]=(counts[n.type]??0)+1;
const sourceNodes=els.filter(n=>n.source_refs).map(n=>({id:n.id,source_refs:n.source_refs}));
const expected=structuredClone(v),work=expected.find(n=>n.id==='section-work');
const originalIndex=work.children.findIndex(n=>n.id==='task-8');
if(originalIndex<0)throw Error('Fixed fixture Task8 no longer directly under work section');
const task8=work.children.splice(originalIndex,1)[0],duty=work.children.find(n=>n.id==='duty-1');
if(!duty)throw Error('Fixed fixture duty-1 missing');
const destinationIndex=duty.children.length;duty.children.push(task8);
write('task8-subtree-expected.json',task8);
write('task8-move-full-expected.json',expected);
const c=read(current,'F03-C.json');
write('fixture-statistics.json',{
  origin:'Static extraction after F03; no additional editor execution',fixtureSha256:hash(new URL('./fixture.json',import.meta.url)),
  elements:els.length,counts,sourceNodes,retiredWrapperCount:mapping.retiredWrapperIds.length,
  textUtf16Length:walk(v).filter(n=>typeof n.text==='string').reduce((n,x)=>n+x.text.length,0),
  task8:{from:{parent:'section-work',index:originalIndex},to:{parent:'duty-1',index:destinationIndex},subtree:'task8-subtree-expected.json',fullExpected:'task8-move-full-expected.json',
    fullExpectedScope:'Explicit fixture oracle for a future isolated Task8-only move. F03-C actually performs copies, explicit link mapping, then Task8 move; its entire actual after is F03-C.json. No claim that this separate full expected was executed as a standalone native case.',
    actualObservedAfter:'results/2026-09-09T22-38-20-172Z/F03-C.json',actualObservedTask8:walk(c.after).find(n=>n.id==='task-8')}
});
const inventory=read(old,'license-inventory.json'),sources=read(old,'sources/installed-source-manifest.json');
const licenses=inventory.packages.flatMap(p=>p.licenses.map(l=>{
  const original=new URL(l.source,installed),archived=new URL(l.archivedAs,old);
  return {package:p.name,version:p.version,declaredLicense:p.declaredLicense,installed:fileURLToPath(original),installedExists:existsSync(original),installedSha256:existsSync(original)?hash(original):null,archived:`../jd-official-profile-probe/${l.archivedAs}`,archivedSha256:hash(archived),expectedSha256:l.sha256};
}));
const sourceFiles=sources.files.map(s=>({package:s.package,source:s.source,installedSha256:hash(new URL(s.source,installed)),archived:`../jd-official-profile-probe/${s.archivedAs}`,archivedSha256:hash(new URL(s.archivedAs,old)),expectedSha256:s.sha256}));
const run=read(current,'run-metadata.json');
write('dependency-provenance.json',{
  checkedOn:'2026-09-10',newInstall:false,versions:run.dependencyVersions,
  lock:{path:'../jd-official-profile-probe/package-lock.json',archivedSha256:hash(new URL('package-lock.json',old)),installedSha256:hash(new URL('package-lock.json',installed))},
  licenses,sourceFiles,note:'F02 archival source/license files are reused by exact relative link; absent installed LICENSE entries retain F02 fixed release-source licenses. No copied node_modules or vendor changes.'
});
console.log(JSON.stringify({counts,elements:els.length,retiredWrappers:mapping.retiredWrapperIds.length,sourceNodes:sourceNodes.length,sourceFiles:sourceFiles.length,licenses:licenses.length,sourceMismatch:sourceFiles.filter(s=>s.installedSha256!==s.expectedSha256||s.archivedSha256!==s.expectedSha256).length,licenseMismatch:licenses.filter(l=>l.archivedSha256!==l.expectedSha256||(l.installedExists&&l.installedSha256!==l.expectedSha256)).length}));
