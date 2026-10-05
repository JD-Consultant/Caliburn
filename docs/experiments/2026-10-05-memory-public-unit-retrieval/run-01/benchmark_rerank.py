"""Fresh DB plus fresh GPU file handoff, measured separately from replay math."""
import time
from qdrant_client import QdrantClient
from common import *
from retrieve import data,exact,local
def main():
 check_manifest();check_manifest('rerank-input-manifest.json');check_manifest('benchmark-code-manifest.json')
 started=time.monotonic()
 while not (HERE/'rerank-results.json').exists():
  if time.monotonic()-started>3600:raise TimeoutError('quality worker deadline')
  time.sleep(.1)
 expected={(r['case_id'],r['method']):r for r in read(HERE/'rerank-results.json')}
 qs=read(HERE/'queries.json');cases=read(HERE/'cases.json');vectors={v['query_id']:v['dense'] for v in read(HERE/'query-vectors.json')};rows,matrices=data();names=read(HERE/'collections.json');db=QdrantClient(url='http://127.0.0.1:6335',timeout=120,trust_env=False)
 methods=list(METHODS);trials=[]
 for repeat in range(3):
  order=methods[repeat:]+methods[:repeat]
  for case in cases:
   for method in order:
    variant,rep=METHODS[method];queries=method_queries(case['case_id'],variant,qs);qids=[q['query_id'] for q in queries];lp=[];dbs=coss=0;at=time.perf_counter()
    for qid in qids:
     now={}
     for nr in (('document','task') if rep=='M' else ('document',) if rep=='D' else ('task',)):
      pool,check,_,_=exact(db,names[nr],rows[nr],matrices[nr],vectors[qid]);now[(qid,nr)]=pool;dbs+=check['db_seconds'];coss+=check['cosine_and_sort_seconds']
     lp.append(local(rep,now,qid))
    index=len(trials);task_id=f"{case['case_id']}-{method}-R-{repeat+1}";request={'task_id':task_id,'query_ids':qids,'pools':lp,'fresh_gpu_required':True};directory=HERE/'benchmark-requests';directory.mkdir(exist_ok=True);tmp=directory/f'{index:03}.tmp';tmp.write_text(json.dumps(request),encoding='utf-8');tmp.rename(directory/f'{index:03}.json')
    response=HERE/'benchmark-responses'/f'{index:03}.json'
    while not response.exists():
     if time.monotonic()-started>3600:raise TimeoutError('benchmark response deadline')
     time.sleep(.02)
    answer=read(response);elapsed=time.perf_counter()-at;assert answer['task_id']==task_id
    assert answer['selected_ids']==[p['id'] for p in expected[(case['case_id'],method+'-R')]['selected']],task_id
    trials.append({'case_id':case['case_id'],'method':method+'-R','repeat':repeat+1,'method_order':[m+'-R' for m in order],'seconds':elapsed,'db_seconds':dbs,'cosine_and_sort_seconds':coss,'gpu_seconds':answer['gpu_seconds'],'queries':len(qids),'routes_per_query':2 if rep=='M' else 1,'selected_ids':answer['selected_ids'],'cached_query_embeddings':True,'fresh_gpu_pairs':20*len(qids)})
    if len(trials)%12==0:print(f'controller {len(trials)}/144',flush=True)
 dump('rerank-benchmark.json',trials);db.close();print('144 fresh DB+GPU timed tasks complete',flush=True)
if __name__=='__main__':main()

