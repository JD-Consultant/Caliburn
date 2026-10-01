import {readFileSync,writeFileSync} from 'node:fs';
import {editor,capture,flush,profile,clone,finiteIssues} from './engine.mjs';
const [inputFile,outputFile]=process.argv.slice(2);
const value=JSON.parse(readFileSync(inputFile,'utf8'));
const e=editor(value),batches=capture(e);
try{
  e.tf.normalize({force:true});await flush();
  writeFileSync(outputFile,JSON.stringify({ok:true,pid:process.pid,node:process.version,profile,value:clone(e.children),issues:finiteIssues(e.children),batches},null,2));
}catch(error){
  writeFileSync(outputFile,JSON.stringify({ok:false,pid:process.pid,error:{message:error.message,stack:error.stack},value:clone(e.children),batches},null,2));process.exitCode=1;
}
