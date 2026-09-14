// Narrow pure-JS review probe: compile the frozen actual JdSession, no HTTP/DB.
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('../experiments/jd-editor/node_modules/typescript');
const path = '.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task-5-snapshot/experiments/jd-editor/web/src/jd/useJdSession.ts';
const js = ts.transpileModule(fs.readFileSync(path, 'utf8'), {compilerOptions: {target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
const mod = {exports:{}};
function fakeRequire(name) {
  if (name === 'react') return {};
  if (name === './api') return {api:{},ApiError:class ApiError extends Error {}};
  if (name === './submissionCache') return {submissionCache:()=>({read:()=>null})};
  if (name === './requestRecoveryCache') return {requestRecoveryCache:()=>({readRun:()=>null})};
  throw Error('Unexpected import '+name);
}
vm.runInNewContext(js,{module:mod,exports:mod.exports,require:fakeRequire,structuredClone,crypto:require('node:crypto').webcrypto});
(async()=>{
  for (const status of ['save_failed','committed']) {
    let pending=true,posts=0;
    const result={status,receipt_durability:'confirmed',result_revision_ref:status==='committed'?'r2':null};
    const port={
      document:async()=>({id:'A',archived:false}),messages:async()=>[],runs:async()=>[],
      read:async()=>({status:'ok',revision_ref:'r1',fragment:[{id:'p',type:'p',children:[{text:'saved'}]}],change_refs:[]}),
      readRecovery:async()=>pending?{status:'unknown',request_key:'original-A',write_blocked:true,can_recover:true}:{status:'no_pending',request_key:null,write_blocked:false,can_recover:false},
      recover:async()=>{posts++;pending=false;return {status:'available',request_key:'original-A',write_blocked:false,can_recover:false,result};},
    };
    const session=new mod.exports.JdSession('A',port,{});
    await session.load();
    await session.recoverManual();
    console.log(JSON.stringify({case:'cachelost_terminal_'+status,posts,recovery:session.recovery,error:session.error,notice:session.notice,locked:session.locked,terminalStillVisible:session.recovery?.status==='available'}));
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
