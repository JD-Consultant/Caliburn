from common import *
def main():
 # Reuse the prior bounded RAG baseline; other experiment families have
 # different manifest shapes and are outside this retrieval comparison.
 prior=read(MEM/'prior-seals.json')
 for rel,h in prior.items():assert sha(ROOT/rel)==h,rel
 for rel,v in read(MEM/'artifact-hashes.json')['files'].items():
  path=MEM/rel;assert sha(path)==v['sha256'],str(path)
  prior[path.relative_to(ROOT).as_posix()]=v['sha256']
 dump('prior-seals.json',prior)
 cases=read(MEM/'cases.json');groups=read(MEM/'method-groups.json');oldq={q['query_id']:q for q in read(MEM/'queries.json')}
 queries=[]
 for c in cases:
  for variant,method in [('O','O-W'),('B2','B2-S')]:
   g=next(g for g in groups if g['case_id']==c['case_id'] and g['method']==method)
   for qid in g['query_ids']:
    q=dict(oldq[qid]);q['input_variant']=variant;q['prior_query_file']=(MEM/'queries.json').relative_to(ROOT).as_posix();queries.append(q)
 assert len(queries)==20 and len({q['query_id'] for q in queries})==20
 vectors={v['query_id']:v for v in read(MEM/'query-vectors.json')}
 dump('cases.json',cases);dump('queries.json',queries);dump('query-vectors.json',[vectors[q['query_id']] for q in queries])
 dump('corpus.json',read(MEM/'corpus.json'));dump('collections.json',{k:v for k,v in read(MEM/'collections.json').items() if k in ('document','task')})
 pool={}
 for f in [MEM/'reused-judgments.json',MEM/'judgments.json']:
  for j in read(f):
   key=(j['case_id'],j['document_id'])
   if key in pool:assert j['judgment']==pool[key]['judgment']
   row=dict(j);row['prior_judgment_file']=f.relative_to(ROOT).as_posix();row['reused']=True;pool[key]=row
 dump('reused-judgments.json',list(pool.values()))
 paths=[HERE/'protocol.md',ROOT/'docs/plans/2026-10-05-memory-public-unit-retrieval.md',HERE/'common.py',HERE/'prepare.py',HERE/'retrieve.py',HERE/'gpu_worker.py',CROSS/'fusion.py',PUBLIC/'chunks.py',OLD/'evaluate.py',H/'pipeline.py',H/'judge-prompt.txt',H/'judge-schema.json',F/'judge-prompt-02.txt',MEM/'artifact-hashes.json',PUBLIC/'artifact-hashes.json',PUBLIC/'chunks.json',MEM/'method-groups.json',MEM/'queries.json',MEM/'query-vectors.json',MEM/'source-bindings.json']
 paths+=list((PUBLIC/'vector-batches').glob('*.npz'))+list((MEM/'snapshots').glob('*.json'))
 paths+=[HERE/n for n in ['cases.json','queries.json','query-vectors.json','corpus.json','collections.json','reused-judgments.json','prior-seals.json']]
 dump('input-manifest.json',{'inputs':{p.relative_to(ROOT).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in paths}})
 dump('execution-manifest.json',{'methods':list(METHODS),'rerank_methods':[m+'-R' for m in METHODS],'queries':20,'cases':8,'max_cost_usd':'1.00','max_calls':100,'query_embedding_reused':True,'reranker_image':'sha256:f21629b9ae4ed11231768edfaed0f40d41d85d6ea9a71e8096a3d96ea0311772'})
 print(f'{len(prior)} old sealed files intact; {len(queries)} fixed queries; {len(pool)} prior pair grades')
if __name__=='__main__':main()
