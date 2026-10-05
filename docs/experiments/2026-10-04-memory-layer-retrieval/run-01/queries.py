"""Build six methods from fixed original inputs and exact published bodies."""
from common import *
METHODS={'O-W':('original','whole'),'O-S':('original','segments'),'B1-W':('work_situation','whole'),'B1-S':('work_situation','objects'),'B2-W':('work_understanding','whole'),'B2-S':('work_understanding','objects')}
def main():
 check_manifest();assert read(HERE/'memory-complete.json')['cases']==8
 qs=[];groups=[];snapshots={}
 for case in read(HERE/'cases.json'):
  cid=case['case_id'];snap=read(HERE/'snapshots'/f'{cid}.json');snapshots[cid]=snap
  for method,(layer,variant) in METHODS.items():
   if layer=='original':
    local=[q for q in read(HERE/'original-queries.json') if q['case_id']==cid and q['variant']==variant]
   else:
    objects=sorted([o for o in snap['objects'] if o['layer']==layer],key=lambda o:(text_sha(o['content']['body']),o['object_id']))
    local=[]
    if variant=='whole' and objects:
     body='\n\n'.join(o['content']['body'] for o in objects)
     local=[{'query_id':cid+'-'+method+'-0','text':body,'object_revisions':[{'object_id':o['object_id'],'revision_id':o['revision_id']} for o in objects]}]
    elif variant=='objects':
     local=[{'query_id':cid+'-'+method+'-'+str(i),'text':o['content']['body'],'object_revisions':[{'object_id':o['object_id'],'revision_id':o['revision_id']}]} for i,o in enumerate(objects)]
    local=[q|{'case_id':cid,'layer':layer,'variant':variant,'text_sha256':text_sha(q['text']),'snapshot_id':snap['snapshot']['snapshot_id']} for q in local]
   for q in local:
    if q['text_sha256']!=text_sha(q['text']):raise ValueError('body hash mismatch')
    if not any(v['query_id']==q['query_id'] for v in qs):qs.append(q)
   groups.append({'case_id':cid,'method':method,'query_ids':[q['query_id'] for q in local],'has_input':bool(local)})
 assert len(groups)==48 and len({q['query_id'] for q in qs})==len(qs)
 dump('queries.json',qs);dump('method-groups.json',groups)
 dump('query-input-manifest.json',{'inputs':{str(p.relative_to(ROOT)).replace('\\','/'):{'sha256':sha(p)} for p in [HERE/'queries.json',HERE/'method-groups.json',Path(__file__),*[HERE/'snapshots'/f"{c['case_id']}.json" for c in read(HERE/'cases.json')]]}})
 print(str(len(qs))+' queries, 48 method groups, exact published body binding')
if __name__=='__main__':main()
