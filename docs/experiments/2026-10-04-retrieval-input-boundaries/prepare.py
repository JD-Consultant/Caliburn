"""Fixed input representations, new local vectors and actual native DB scores."""
import time
import httpx
import numpy as np
from qdrant_client import QdrantClient,models
from support import *

def main():
    for name,digest in read(HERE/'input-manifest.json')['files'].items():
        assert sha(HERE/name)==digest
    corpus = prior.documents(); vectors = prior.doc_vectors(corpus)
    cache = {}
    for filename in (QUOTA.parent/'2026-10-04-retrieve-rerank/passage-pool/passage-cache.jsonl',QUOTA/'holdout-passage-cache.jsonl'):
        for r in lines(filename):
            cache[r['text_sha256']] = {**r,'cache_reused':True,'origin':str(filename.relative_to(HERE.parent)).replace('\\','/')}
    inputs = read(HERE/'inputs.json')
    new = []
    with httpx.Client(base_url='http://127.0.0.1:8082',timeout=300,trust_env=False) as client:
        runtime = client.get('/runtime').raise_for_status().json()
        assert runtime==read(prior.OLD/'prepared.json')['embedding_runtime']
        for text in dict.fromkeys(t for q in inputs for t in q['passages']):
            digest = text_sha(text)
            if digest in cache:
                continue
            tokens = client.post('/token-lengths',json={'texts':[text]}).raise_for_status().json()['lengths'][0]
            assert tokens<=8192
            tick = time.perf_counter()
            raw = client.post('/embed',json={'texts':[text]}).raise_for_status().json()['embeddings'][0]['dense']
            elapsed = time.perf_counter()-tick
            v = np.asarray(raw,dtype=np.float64); assert v.shape==(1024,) and np.isfinite(v).all()
            v /= np.linalg.norm(v)
            record = {'text_sha256':digest,'text':text,'tokens':tokens,'raw_dense':raw,'dense':v.tolist(),
                      'seconds':elapsed,'cache_reused':False}
            cache[digest] = record; new.append(record)
    dump_lines('new-passage-cache.jsonl',new)
    wanted = {text_sha(t) for q in inputs for t in q['passages']}
    dump_lines('all-passage-cache.jsonl',[cache[k] for k in sorted(wanted)])
    dump('embedding-runtime.json',runtime)
    queries,checks = [],[]
    db = QdrantClient(url='http://127.0.0.1:6335',timeout=60,trust_env=False)
    try:
        assert db.get_collection(COLLECTION).points_count==805
        for q in inputs:
            pools,global_pool = prior.rank(corpus,vectors,q['passages'],cache)
            for index,text in enumerate(q['passages'],1):
                tick = time.perf_counter()
                actual = db.query_points(COLLECTION,query=cache[text_sha(text)]['dense'],using='dense',limit=20,
                     with_payload=True,search_params=models.SearchParams(exact=True)).points
                elapsed = time.perf_counter()-tick
                returned = [{'id':p.payload['ocs_code'],'point_id':str(p.id),'score':p.score} for p in actual]
                error = max(abs(a['score']-b['score']) for a,b in zip(returned,pools[index-1][:20],strict=True))
                assert [r['id'] for r in returned]==[r['id'] for r in pools[index-1][:20]] and error<1e-6
                checks.append({'case_id':q['case_id'],'variant':q['variant'],'passage':index,'exact':True,'limit':20,
                               'seconds':elapsed,'max_score_error':error,'returned':returned})
            queries.append({**q,'pools':pools,'global_pool':global_pool})
    finally:
        db.close()
    prepared = {'corpus':corpus,'queries':queries}
    dump('prepared.json',prepared); dump('database-checks.json',checks)
    scores = prior.load_pairs('holdout')
    jobs = prior.jobs(queries,corpus,scores,[CONFIGS[1]])
    dump('jobs.json',jobs)
    names = ['protocol.md','input-manifest.json','input-amendment-01.json','cases.json','cases-observed.json','inputs.json','inputs.py','support.py','prepare.py',
             'gpu_worker.py','analyze.py','benchmark.py','prepared.json','jobs.json','benchmark-plan.json',
             'all-passage-cache.jsonl','new-passage-cache.jsonl','database-checks.json','embedding-runtime.json']
    dump('execution.json',{'created_utc':time.time(),'before_new_scores':True,'sources':{n:sha(HERE/n) for n in names},
          'model_sha256':MODEL_SHA,'prior_sources':{n:sha(QUOTA/n) for n in ('common.py','selection.py','audit.py','artifact-hashes.json',
              'borrowed-pairs.jsonl','supplemental-development-pairs.jsonl','supplemental-holdout-pairs.jsonl')},
          'document_cache_sha256':sha(prior.CACHE)})
    print(json.dumps({'case_variants':len(queries),'all_queries':len(checks),'unique_new_embeddings':len(new),
                      'missing_pairs':sum(len(j['documents']) for j in jobs)},indent=2))

if __name__=='__main__':
    main()
