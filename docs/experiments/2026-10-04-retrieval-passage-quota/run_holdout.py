"""Reveal new synthetic cases only after development selection is hash-frozen."""
import time
import httpx
from qdrant_client import QdrantClient,models
from common import *

def main():
    freeze = read(HERE/'selection-frozen.json')
    assert sha(HERE/'selection-development.json')==freeze['selection_sha256']
    for name,digest in freeze['sources'].items():
        assert sha(HERE/name)==digest
    cases = read(HERE/'holdout-cases-2026-10-04-reviewed.json')
    amendment = read(HERE/'case-amendment-01.json')
    # Effective case file was itself frozen in the pre-development execution manifest.
    assert sha(HERE/'holdout-cases-2026-10-04-reviewed.json')==read(HERE/'execution-development.json')['sources']['holdout-cases-2026-10-04-reviewed.json']
    selected = read(HERE/'selection-development.json')['chosen']
    configurations = [{k:s[k] for k in ('method','n','k')} for s in selected.values() if s]
    assert configurations
    limit = max(c['n'] for c in configurations)
    corpus = documents(); vectors = doc_vectors(corpus)
    cache = {}
    runtime = read(OLD/'prepared.json')['embedding_runtime']
    with httpx.Client(base_url='http://127.0.0.1:8082',timeout=300,trust_env=False) as client:
        actual_runtime = client.get('/runtime').raise_for_status().json()
        assert actual_runtime==runtime
        for text in dict.fromkeys(t for c in cases for t in c['employee_messages']):
            tokens = client.post('/token-lengths',json={'texts':[text]}).raise_for_status().json()['lengths'][0]
            assert tokens<=8192
            tick = time.perf_counter()
            raw = client.post('/embed',json={'texts':[text]}).raise_for_status().json()['embeddings'][0]['dense']
            elapsed = time.perf_counter()-tick
            v = np.asarray(raw,dtype=np.float64)
            assert v.shape==(1024,) and np.isfinite(v).all()
            v /= np.linalg.norm(v)
            cache[text_sha(text)] = {'text_sha256':text_sha(text),'text':text,'raw_dense':raw,'dense':v.tolist(),'tokens':tokens,'seconds':elapsed}
    dump_lines('holdout-passage-cache.jsonl',cache.values())
    queries,checks = [],[]
    db = QdrantClient(url='http://127.0.0.1:6335',timeout=60,trust_env=False)
    try:
        assert db.get_collection(COLLECTION).points_count==805
        for c in cases:
            pools,global_pool = rank(corpus,vectors,c['employee_messages'],cache)
            for i,text in enumerate(c['employee_messages'],1):
                tick = time.perf_counter()
                actual = db.query_points(COLLECTION,query=cache[text_sha(text)]['dense'],using='dense',limit=limit,
                     with_payload=True,search_params=models.SearchParams(exact=True)).points
                seconds = time.perf_counter()-tick
                returned = [{'id':p.payload['ocs_code'],'point_id':str(p.id),'score':p.score} for p in actual]
                assert [r['id'] for r in returned]==[r['id'] for r in pools[i-1][:limit]]
                error = max(abs(a['score']-b['score']) for a,b in zip(returned,pools[i-1]))
                assert error<1e-6
                checks.append({'case_id':c['case_id'],'passage':i,'limit':limit,'exact':True,'using':'dense',
                               'seconds':seconds,'max_score_error':error,'returned':returned})
            queries.append({'case_id':c['case_id'],'passages':c['employee_messages'],'pools':pools,'global_pool':global_pool})
    finally:
        db.close()
    dump('prepared-holdout.json',{'corpus':corpus,'queries':queries})
    dump('database-holdout.json',checks)
    dump('holdout-embedding-runtime.json',actual_runtime)
    missing = jobs(queries,corpus,load_pairs('development'),configurations)
    dump('holdout-jobs.json',missing)
    names = ['common.py','selection.py','gpu_worker.py','analyze.py','run_holdout.py','benchmark.py','benchmark-plan.json',
             'selection-frozen.json','selection-development.json','case-amendment-01.json','holdout-cases-2026-10-04-reviewed.json',
             'prepared-holdout.json','holdout-passage-cache.jsonl','holdout-jobs.json','database-holdout.json','prepared-development.json']
    dump('execution-holdout.json',{'created_utc':time.time(),'before_new_rerank':True,'selection_sha256':freeze['selection_sha256'],
          'sources':{n:sha(HERE/n) for n in names},'model_sha256':MODEL_SHA})
    print(json.dumps({'new_cases':len(queries),'new_passages':len(cache),'database_queries':len(checks),
                      'missing_pairs':sum(len(j['documents']) for j in missing)},indent=2))

if __name__=='__main__':
    main()
