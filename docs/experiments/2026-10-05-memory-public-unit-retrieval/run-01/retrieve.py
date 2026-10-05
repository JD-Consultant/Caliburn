"""Read existing real exact DB; preserve full scores and canonical boundaries."""
import time,numpy as np
from qdrant_client import QdrantClient,models
from common import *

def data():
 raw={}
 for path in sorted((PUBLIC/'vector-batches').glob('*.npz')):
  z=np.load(path,allow_pickle=False)
  for h,v in zip(z['hashes'],z['dense'],strict=True):raw[str(h)]=v
 chunks=read(PUBLIC/'chunks.json');rows={rep:[r for r in chunks if r['representation']==rep] for rep in ('document','task')}
 matrices={rep:np.asarray([raw[text_sha(r['text'])] for r in rr],dtype=np.float64) for rep,rr in rows.items()}
 for m in matrices.values():m/=np.linalg.norm(m,axis=1,keepdims=True)
 return rows,matrices

def exact(db,name,rows,matrix,vector):
 start=time.perf_counter();v=np.asarray(vector,dtype=np.float64);v/=np.linalg.norm(v)
 scores=matrix@v
 hits=[{'parent_id':r['parent_id'],'chunk_id':r['chunk_id'],'score':float(s)} for r,s in zip(rows,scores,strict=True)]
 parents=aggregate(hits,'max',805);canonical=parents[:20];cosine_seconds=time.perf_counter()-start
 wanted={r['id'] for r in canonical};limit=21;checks=[];db_seconds=0
 while True:
  tick=time.perf_counter();gs=db.query_points_groups(name,query=v.tolist(),using='dense',group_by='parent_id',group_size=3,limit=limit,with_payload=True,search_params=models.SearchParams(exact=True)).groups;elapsed=time.perf_counter()-tick;db_seconds+=elapsed
  native=[]
  for g in gs:
   for p in g.hits:
    row=rows[int(p.id)];assert row['parent_id']==g.id==p.payload['parent_id'] and row['chunk_id']==p.payload['chunk_id']
    native.append({'parent_id':row['parent_id'],'chunk_id':row['chunk_id'],'score':p.score})
  actual=aggregate(native,'max',805);ids={r['id'] for r in actual}
  checks.append({'limit':limit,'returned_parents':len(ids),'native_parent_order':[r['id'] for r in actual]})
  if wanted<=ids:break
  if limit==805:raise ValueError('canonical candidates missing from exact DB')
  limit=min(805,limit*2)
 lookup={r['id']:r for r in actual};error=max(abs(r['score']-lookup[r['id']]['score']) for r in canonical);assert error<1e-6,error
 return canonical,{'max_native_error':error,'native_attempts':checks,'db_seconds':db_seconds,'cosine_and_sort_seconds':cosine_seconds},hits,parents

def local(rep,pools,qid):
 if rep!='M':return pools[(qid,'document' if rep=='D' else 'task')]
 return merge_pools([pools[(qid,'document')],pools[(qid,'task')]],[qid+':D',qid+':T'])[:20]

def main():
 check_manifest();qs=read(HERE/'queries.json');cases=read(HERE/'cases.json');vectors={v['query_id']:v['dense'] for v in read(HERE/'query-vectors.json')}
 rows,matrices=data();names=read(HERE/'collections.json');db=QdrantClient(url='http://127.0.0.1:6335',timeout=120,trust_env=False)
 configs=[]
 for rep,name in names.items():
  info=db.get_collection(name);assert info.points_count==len(rows[rep]);assert info.config.params.vectors['dense'].size==1024
  configs.append({'representation':rep,'collection':name,'points':info.points_count,'configuration':info.model_dump(mode='json')})
 dump('database-reuse.json',configs)
 pools={};allr=[];checks=[]
 for q in qs:
  for rep,name in names.items():
   pool,check,hits,parents=exact(db,name,rows[rep],matrices[rep],vectors[q['query_id']]);pools[(q['query_id'],rep)]=pool
   checks.append({'query_id':q['query_id'],'representation':rep,**check});allr.append({'query_id':q['query_id'],'representation':rep,'chunk_scores':hits,'parents':parents})
  print('verified '+q['query_id'],flush=True)
 results=[];quality_pairs=set();controls=[];prior=read(MEM/'results.json');cross=read(CROSS/'results.json')
 for case in cases:
  for method,(variant,rep) in METHODS.items():
   queries=method_queries(case['case_id'],variant,qs);qids=[q['query_id'] for q in queries];lp=[local(rep,pools,qid) for qid in qids];merged=merge_pools(lp,qids)
   r={'case_id':case['case_id'],'method':method,'variant':variant,'representation':rep,'query_ids':qids,'query_pools':lp,'merged_ranking':merged,'selected':merged[:5],'union_parents':len({p['id'] for pool in lp for p in pool})};results.append(r)
   quality_pairs.update((qid,p['id']) for qid,pool in zip(qids,lp,strict=True) for p in pool)
   old=None
   if rep=='D':old=next(r for r in prior if r['case_id']==case['case_id'] and r['method']==('O-W' if variant=='O' else 'B2-S'))
   elif method=='O-T':old=next(r for r in cross if r['case_id']==case['case_id'] and r['method']=='W-Tmax')
   if old is not None:
    assert [p['id'] for p in old['selected']]==[p['id'] for p in r['selected']],method
    controls.append({'case_id':case['case_id'],'method':method,'same_prior_top5':True})
 dump('all-rankings.json',allr);dump('database-checks.json',checks);dump('results.json',results);dump('control-checks.json',controls)
 dump('rerank-pair-inputs.json',[{'query_id':qid,'document_id':ident} for qid,ident in sorted(quality_pairs)])
 trials=[];methods=list(METHODS)
 for repeat in range(3):
  order=methods[repeat:]+methods[:repeat]
  for case in cases:
   for method in order:
    variant,rep=METHODS[method];queries=method_queries(case['case_id'],variant,qs);qids=[q['query_id'] for q in queries];lp=[];dbs=coss=0;at=time.perf_counter()
    for qid in qids:
     now={}
     for native_rep in (('document','task') if rep=='M' else ('document',) if rep=='D' else ('task',)):
      pool,check,_,_=exact(db,names[native_rep],rows[native_rep],matrices[native_rep],vectors[qid]);now[(qid,native_rep)]=pool;dbs+=check['db_seconds'];coss+=check['cosine_and_sort_seconds']
     lp.append(local(rep,now,qid))
    merged=merge_pools(lp,qids);elapsed=time.perf_counter()-at;expected=next(r for r in results if r['case_id']==case['case_id'] and r['method']==method)
    assert [p['id'] for p in merged[:5]]==[p['id'] for p in expected['selected']]
    trials.append({'case_id':case['case_id'],'method':method,'repeat':repeat+1,'method_order':order,'seconds':elapsed,'db_seconds':dbs,'cosine_and_sort_seconds':coss,'queries':len(qids),'routes_per_query':2 if rep=='M' else 1,'selected_ids':[p['id'] for p in merged[:5]],'cached_query_embeddings':True})
 dump('benchmark.json',trials);db.close();print(f'{len(results)} groups, {len(quality_pairs)} rerank pairs, {len(controls)} controls, {len(trials)} warm trials',flush=True)
if __name__=='__main__':main()

