"""Actual new query vectors, exact DB checks and file-hand-off warm trials."""
import sys
import time
import statistics
import httpx
import numpy as np
from qdrant_client import QdrantClient, models
from pipeline import *


def prepare():
    check_manifest()
    corpus, queries = read(HERE / 'corpus.json'), read(HERE / 'queries.json')
    wanted = {text_sha(doc['text']) for doc in corpus}
    cached = {}
    with DOC_CACHE.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['text_sha256'] in wanted:
                cached[row['text_sha256']] = row['embedding']['dense']
    vectors = np.asarray([cached[text_sha(doc['text'])] for doc in corpus], dtype=np.float64)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    embeddings = []
    if (HERE / 'query-vectors.json').exists():
        embeddings = read(HERE / 'query-vectors.json')
        runtime = read(HERE / 'embedding-runtime.json')
        assert {r['query_id']:r['text_sha256'] for r in embeddings} == {q['query_id']:q['text_sha256'] for q in queries}
    else:
      with httpx.Client(base_url='http://127.0.0.1:8082', timeout=180, trust_env=False) as client:
        runtime = client.get('/runtime').raise_for_status().json()
        assert runtime == read(OLD / 'prepared.json')['embedding_runtime']
        for query in queries:
            tick = time.perf_counter()
            tokens = client.post('/token-lengths', json={'texts':[query['text']]}).raise_for_status().json()['lengths'][0]
            assert tokens <= 8192
            token_time = time.perf_counter() - tick
            tick = time.perf_counter()
            raw = client.post('/embed', json={'texts':[query['text']]}).raise_for_status().json()['embeddings'][0]['dense']
            elapsed = time.perf_counter() - tick
            value = np.asarray(raw, dtype=np.float64)
            assert value.shape == (1024,) and np.isfinite(value).all()
            value /= np.linalg.norm(value)
            embeddings.append({'query_id':query['query_id'],'text_sha256':query['text_sha256'],
                               'tokens':tokens,'token_count_seconds':token_time,'embed_seconds':elapsed,
                               'raw_dense':raw,'dense':value.tolist(),'cache_reused':False})
            print(f"embedded {query['query_id']}: {elapsed:.3f}s", flush=True)
      dump('embedding-runtime.json', runtime)
      dump('query-vectors.json', embeddings)
    vector_map = {row['query_id']: row['dense'] for row in embeddings}
    rankings, checks = [], []
    db = QdrantClient(url='http://127.0.0.1:6335', timeout=60, trust_env=False)
    try:
        assert db.get_collection(COLLECTION).points_count == 805
        for query in queries:
            values = vectors @ np.asarray(vector_map[query['query_id']], dtype=np.float64)
            order = sorted(range(len(corpus)), key=lambda i: (-float(values[i]), corpus[i]['id']))
            ranked = [{'id':corpus[i]['id'],'score':float(values[i])} for i in order]
            tick = time.perf_counter()
            points = db.query_points(COLLECTION, query=vector_map[query['query_id']], using='dense', limit=20,
                                    with_payload=True, search_params=models.SearchParams(exact=True)).points
            elapsed = time.perf_counter() - tick
            native = [{'id':point.payload['ocs_code'],'point_id':str(point.id),'score':point.score} for point in points]
            assert [r['id'] for r in native] == [r['id'] for r in ranked[:20]]
            error = max(abs(a['score'] - b['score']) for a,b in zip(native,ranked[:20],strict=True))
            assert error < 1e-6
            rankings.append({'query_id':query['query_id'],'ranked':ranked})
            checks.append({'query_id':query['query_id'],'seconds':elapsed,'max_score_error':error,'exact':True,'returned':native})
    finally:
        db.close()
    dump('dense-rankings.json', rankings)
    dump('database-checks.json', checks)
    dump('gpu-input-manifest.json', {'inputs':{str((HERE/name).relative_to(ROOT)).replace('\\','/'):
         {'sha256':sha(HERE/name)} for name in ('execution-manifest-02.json','query-vectors.json','dense-rankings.json')},
         'model_sha256':MODEL_SHA})
    print('15 native exact searches verified; 300 reranker pairs prepared.', flush=True)


def selections(queries, ranks, pair_scores):
    result = []
    corpus = {doc['id']:doc for doc in read(HERE / 'corpus.json')}
    for case in read(PARENT / 'cases-v1.json')['cases']:
        for method in ('R01','R02','R03','R04'):
            variant = 'whole' if method in ('R01','R02') else 'segments'
            chosen = [query for query in queries if query['case_id'] == case['case_id'] and query['variant'] == variant]
            pools = []
            for query in chosen:
                pool = ranks[query['query_id']][:20]
                if method in ('R02','R04'):
                    pool = sorted([{'id':row['id'],'score':pair_scores[(query['query_id'],row['id'])]} for row in pool],
                                  key=lambda row:(-row['score'],row['id']))
                pools.append(pool)
            ranked = pools[0] if len(pools) == 1 else fuse(pools,2)
            selected = ranked[:5]
            assert len(selected) == len({row['id'] for row in selected}) == 5
            result.append({'case_id':case['case_id'],'method':method,'query_ids':[q['query_id'] for q in chosen],
                           'query_rankings':pools,'merged_ranking':ranked,'selected':selected,
                           'characters':sum(len(corpus[row['id']]['text']) for row in selected)})
    return result


def bench():
    check_manifest()
    queries = read(HERE / 'queries.json')
    by_query = {q['query_id']:q for q in queries}
    vectors = {row['query_id']:row['dense'] for row in read(HERE / 'query-vectors.json')}
    ranks = {row['query_id']:row['ranked'] for row in read(HERE / 'dense-rankings.json')}
    pairs = {}
    with (HERE / 'pairs.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            pairs[(row['query_id'],row['id'])] = row['logit']
    selected = selections(queries,ranks,pairs)
    dump('results.json',selected)
    rows = []
    db = QdrantClient(url='http://127.0.0.1:6335', timeout=60, trust_env=False)
    try:
        for case in ('F01','F02','F03','F04','F05'):
            for repeat in (1,2,3):
                for method in ('R01','R02','R03','R04'):
                    task_id = f'{case}-{method}-{repeat}'
                    variant = 'whole' if method in ('R01','R02') else 'segments'
                    chosen = [q for q in queries if q['case_id'] == case and q['variant'] == variant]
                    begin = time.perf_counter()
                    pools, searches = [], []
                    for query in chosen:
                        tick = time.perf_counter()
                        points = db.query_points(COLLECTION, query=vectors[query['query_id']], using='dense',limit=20,
                           with_payload=True,search_params=models.SearchParams(exact=True)).points
                        returned = [{'id':p.payload['ocs_code'],'score':p.score} for p in points]
                        assert [r['id'] for r in returned] == [r['id'] for r in ranks[query['query_id']][:20]]
                        assert max(abs(a['score']-b['score']) for a,b in zip(returned,ranks[query['query_id']][:20],strict=True)) < 1e-6
                        searches.append({'query_id':query['query_id'],'seconds':time.perf_counter()-tick,'returned':returned})
                        pools.append(returned)
                    gpu_response = None
                    if method in ('R02','R04'):
                        request = {'task_id':task_id,'query_ids':[q['query_id'] for q in chosen],
                                   'pools':pools,'fresh_gpu_required':True}
                        request_path = HERE / 'benchmark-requests' / (task_id + '.json')
                        request_path.parent.mkdir(exist_ok=True)
                        temp = request_path.with_suffix('.tmp')
                        temp.write_text(json.dumps(request),encoding='utf-8'); temp.rename(request_path)
                        response_path = HERE / 'benchmark-responses' / (task_id + '.json')
                        deadline = time.monotonic()+120
                        while not response_path.exists():
                            if time.monotonic() > deadline:
                                raise TimeoutError('GPU benchmark response deadline')
                            time.sleep(.02)
                        gpu_response = read(response_path)
                        assert gpu_response['task_id'] == task_id
                        scored = {(row['query_id'],row['id']):row['logit'] for row in gpu_response['pairs']}
                        assert set(scored) == {(query['query_id'],row['id']) for query,pool in zip(chosen,pools,strict=True) for row in pool}
                        pools = [sorted([{'id':r['id'],'score':scored[(q['query_id'],r['id'])]} for r in pool],
                                    key=lambda r:(-r['score'],r['id'])) for q,pool in zip(chosen,pools,strict=True)]
                    tick = time.perf_counter()
                    final = pools[0][:5] if len(pools)==1 else fuse(pools,2)[:5]
                    merge_time = time.perf_counter()-tick
                    quality = next(row for row in selected if row['case_id']==case and row['method']==method)
                    assert [r['id'] for r in final] == [r['id'] for r in quality['selected']]
                    rows.append({'task_id':task_id,'case_id':case,'method':method,'repeat':repeat,
                                 'cached_query_embeddings':True,'total_seconds':time.perf_counter()-begin,
                                 'database_seconds':sum(r['seconds'] for r in searches),'merge_seconds':merge_time,
                                 'gpu_worker_seconds':gpu_response['worker_seconds'] if gpu_response else 0,
                                 'query_count':len(chosen),'pair_count':len(gpu_response['pairs']) if gpu_response else 0,
                                 'searches':searches,'selected_ids':[r['id'] for r in final]})
                    print(f"benchmark {task_id}: {rows[-1]['total_seconds']:.3f}s",flush=True)
                    # Persist each trial immediately so failures cannot erase earlier trials.
                    with (HERE / 'benchmark-results.jsonl').open('a',encoding='utf-8') as stream:
                        stream.write(json.dumps(rows[-1],ensure_ascii=False)+'\n')
    finally:
        db.close()
    dump('timing-summary.json',[{'case_id':case,'method':method,
          'samples_seconds':[r['total_seconds'] for r in rows if r['case_id']==case and r['method']==method],
          'median_seconds':statistics.median(r['total_seconds'] for r in rows if r['case_id']==case and r['method']==method)}
          for case in ('F01','F02','F03','F04','F05') for method in ('R01','R02','R03','R04')])


if __name__ == '__main__':
    prepare() if sys.argv[1] == 'prepare' else bench()
