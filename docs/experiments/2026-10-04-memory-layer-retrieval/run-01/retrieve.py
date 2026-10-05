import time, statistics, numpy as np
from qdrant_client import QdrantClient,models
from common import *
def main():
 check_manifest();check_manifest('query-input-manifest.json')
 qs=read(HERE/'queries.json');vs={r['query_id']:r for r in read(HERE/'query-vectors.json')}
 rows=[r for r in read(PUBLIC/'chunks.json') if r['representation']=='document'];assert len(rows)==805
 allvectors={}
 for p in sorted((PUBLIC/'vector-batches').glob('*.npz')):
  z=np.load(p,allow_pickle=False)
  for h,v in zip(z['hashes'],z['dense'],strict=True):allvectors[str(h)]=v
 matrix=np.asarray([allvectors[text_sha(r['text'])] for r in rows],dtype=np.float64);matrix/=np.linalg.norm(matrix,axis=1,keepdims=True)
 name=read(HERE/'collections.json')['document'];db=QdrantClient(url='http://127.0.0.1:6335',timeout=120,trust_env=False)
 info=db.get_collection(name);assert info.points_count==805 and info.config.params.vectors['dense'].size==1024
 dump('database-reuse.json',info.model_dump(mode='json'))
 pools={};nativechecks=[];rankings=[]
 def get_pool(q,scores):
  allrank=sorted([{'id':r['parent_id'],'score':float(scores[i])} for i,r in enumerate(rows)],key=lambda r:(-r['score'],r['id']))
  expected={r['id'] for r in allrank[:20]};limit=21;tick=time.perf_counter()
  while True:
   hits=db.query_points_groups(name,query=vs[q['query_id']]['dense'],using='dense',group_by='parent_id',group_size=1,limit=limit,with_payload=True,search_params=models.SearchParams(exact=True)).groups
   if expected.issubset({g.id for g in hits}):break
   if limit==805:raise ValueError('exact native candidate mismatch')
   limit=min(805,limit*2)
  native=[]
  for g in hits:
   p=g.hits[0];r=rows[int(p.id)];assert r['parent_id']==g.id==p.payload['parent_id']
   error=abs(float(scores[int(p.id)])-p.score);assert error<1e-6
   native.append({'id':g.id,'point_id':int(p.id),'native_score':p.score,'canonical_score':float(scores[int(p.id)]),'error':error})
  return allrank[:20],allrank,{'query_id':q['query_id'],'seconds':time.perf_counter()-tick,'limit':limit,'hits':native}
 for q in qs:
  v=np.asarray(vs[q['query_id']]['dense'],dtype=np.float64);v/=np.linalg.norm(v);scores=matrix@v
  pool,ranking,check=get_pool(q,scores);pools[q['query_id']]=pool;nativechecks.append(check)
  rankings.append({'query_id':q['query_id'],'ranking':ranking})
 results=[]
 for g in read(HERE/'method-groups.json'):
  local=[pools[i] for i in g['query_ids']];merged=merge_pools(local,g['query_ids']) if local else []
  results.append(g|{'query_pools':local,'merged_ranking':merged,'selected':merged[:5]})
 old=read(CROSS/'results.json');controls=[]
 for r in results:
  if r['method'].startswith('O-'):
   prior=next(p for p in old if p['case_id']==r['case_id'] and p['method']==('W-Dmax' if r['method']=='O-W' else 'S-Dmax'))
   assert [p['id'] for p in r['selected']]==[p['id'] for p in prior['selected']],r
   controls.append({'case_id':r['case_id'],'method':r['method'],'prior_top5_unchanged':True})
 dump('all-rankings.json',rankings);dump('database-checks.json',nativechecks);dump('results.json',results);dump('control-checks.json',controls)
 # Cached query embeddings; recompute cosine and sorting inside every timing trial.
 trials=[];byq={q['query_id']:q for q in qs}
 for repeat in range(3):
  ordered=results[repeat:]+results[:repeat]
  for r in ordered:
   tick=time.perf_counter();local=[];dbsec=0
   for qid in r['query_ids']:
    q=byq[qid];v=np.asarray(vs[qid]['dense'],dtype=np.float64);v/=np.linalg.norm(v)
    pool,_,check=get_pool(q,matrix@v);local.append(pool);dbsec+=check['seconds']
   merged=merge_pools(local,r['query_ids']) if local else []
   assert [p['id'] for p in merged[:5]]==[p['id'] for p in r['selected']]
   trials.append({'case_id':r['case_id'],'method':r['method'],'repeat':repeat+1,'seconds':time.perf_counter()-tick,'db_seconds':dbsec,'queries':len(local),'cached_query_embeddings':True,'includes_exact_cosine_and_canonical_sort':True})
 dump('benchmark.json',trials);db.close()
 print(str(len(results))+' groups; '+str(len(controls))+' original controls; '+str(len(trials))+' timing trials')
if __name__=='__main__':main()
