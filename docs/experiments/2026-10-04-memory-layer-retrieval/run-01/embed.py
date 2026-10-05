import time, numpy as np, httpx
from common import *
def main():
 check_manifest();check_manifest('query-input-manifest.json')
 qs=read(HERE/'queries.json');old={v['text_sha256']:v for v in read(HERE/'original-vectors.json')}
 byhash={}
 for q in qs:byhash.setdefault(q['text_sha256'],q['text'])
 new=[h for h in byhash if h not in old];cache={};records=[]
 with httpx.Client(base_url='http://127.0.0.1:8082',timeout=300,trust_env=False) as client:
  runtime=client.get('/runtime').raise_for_status().json();assert runtime==read(H/'embedding-runtime.json');dump('embedding-runtime.json',runtime)
  for h in new:
   tick=time.perf_counter();n=client.post('/token-lengths',json={'texts':[byhash[h]]}).raise_for_status().json()['lengths'][0];token_seconds=time.perf_counter()-tick
   assert 0<n<=8192,(h,n)
   tick=time.perf_counter();e=client.post('/embed',json={'texts':[byhash[h]]}).raise_for_status().json()['embeddings'][0];seconds=time.perf_counter()-tick
   v=np.asarray(e['dense'],dtype=np.float64);assert v.shape==(1024,) and np.isfinite(v).all();v/=np.linalg.norm(v)
   cache[h]={'dense':v.tolist(),'tokens':n,'embedding_seconds':seconds,'token_seconds':token_seconds,'cache_reused':False}
   append('embedding-trials.jsonl',{'text_sha256':h,'tokens':n,'embedding_seconds':seconds,'token_seconds':token_seconds})
   if len(cache)%10==0:print('new query embeddings '+str(len(cache))+'/'+str(len(new)),flush=True)
 for q in qs:
  h=q['text_sha256'];v=old[h] if h in old else cache[h]
  records.append(v|{'query_id':q['query_id'],'text_sha256':h,'cache_reused':h in old,'model_revision':runtime['revision']})
 dump('query-vectors.json',records)
 dump('embedding-complete.json',{'queries':len(records),'fresh_unique_texts':len(new),'reused_original_texts':len({q['text_sha256'] for q in qs if q['text_sha256'] in old}),'new_token_max':max(v['tokens'] for v in cache.values()),'fresh_embedding_seconds':sum(v['embedding_seconds'] for v in cache.values())})
 print('all query vectors saved')
if __name__=='__main__':main()
