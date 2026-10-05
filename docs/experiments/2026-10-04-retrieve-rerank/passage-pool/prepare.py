"""One employee, several original work passages; exact max-cosine union."""
import hashlib
import json
import time
from pathlib import Path

import httpx
import numpy as np
from qdrant_client import QdrantClient, models

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SECOND = HERE.parent.parent/'2026-10-04-occupation-retrieval-generalization'


def dump(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not (HERE/'prepared.json').exists()
    cases = json.loads((PARENT/'cases-v4.json').read_text(encoding='utf-8'))
    parent = json.loads((PARENT/'prepared.json').read_text(encoding='utf-8'))
    corpus = parent['corpus']
    cache_path = SECOND/'cache/20f95996a7ef4d574c29bed8625e84277aee1a73b8d097f5b45b5320ddb27bd8.jsonl'
    wanted = {sha_text(r['text']) for r in corpus}
    cached = {r['text_sha256']:r for r in map(json.loads,cache_path.open(encoding='utf-8')) if r['text_sha256'] in wanted}
    docs = np.asarray([cached[sha_text(r['text'])]['embedding']['dense'] for r in corpus],dtype=np.float64)
    docs /= np.linalg.norm(docs,axis=1,keepdims=True)
    passages = list(dict.fromkeys(text for c in cases for text in c['employee_messages']))
    passage_vectors = {}
    with httpx.Client(base_url='http://127.0.0.1:8082',timeout=300,trust_env=False) as client:
        assert client.get('/runtime').raise_for_status().json() == parent['embedding_runtime']
        with (HERE/'passage-cache.jsonl').open('x',encoding='utf-8') as stream:
            for text in passages:
                tokens = client.post('/token-lengths',json={'texts':[text]}).raise_for_status().json()['lengths'][0]
                assert tokens <= 8192
                start = time.perf_counter()
                value = client.post('/embed',json={'texts':[text]}).raise_for_status().json()['embeddings'][0]['dense']
                v = np.asarray(value,dtype=np.float64); assert v.shape == (1024,) and np.isfinite(v).all()
                v /= np.linalg.norm(v)
                record = {'text_sha256':sha_text(text),'tokens':tokens,'dense':v.tolist(),'seconds':time.perf_counter()-start}
                passage_vectors[text] = v
                stream.write(json.dumps(record)+'\n')
    queries,checks = [],[]
    db = QdrantClient(url='http://127.0.0.1:6335',timeout=60,trust_env=False)
    collection = json.loads((PARENT/'database-manifest.json').read_text())['collection']
    try:
        assert db.get_collection(collection).points_count == 805
        for c in cases:
            texts = c['employee_messages']
            start = time.perf_counter()
            scores = np.max(docs@np.stack([passage_vectors[t] for t in texts]).T,axis=1)
            order = sorted(range(805),key=lambda i:(-float(scores[i]),corpus[i]['id']))
            dense_seconds = time.perf_counter()-start
            ranking = [{'id':corpus[i]['id'],'score':float(scores[i])} for i in order]
            returned = {}
            elapsed = 0
            for index,text in enumerate(texts,1):
                start = time.perf_counter()
                actual = db.query_points(collection,query=passage_vectors[text].tolist(),using='dense',limit=200,
                         with_payload=True,search_params=models.SearchParams(exact=True)).points
                took = time.perf_counter()-start; elapsed += took
                for point in actual:
                    key = point.payload['ocs_code']; returned[key] = max(returned.get(key,-1),point.score)
                checks.append({'case_id':c['case_id'],'passage':index,'seconds':took,
                               'returned':[{'id':p.payload['ocs_code'],'score':p.score} for p in actual]})
            merged = sorted(returned,key=lambda k:(-returned[k],k))[:200]
            assert merged == [r['id'] for r in ranking[:200]],c['case_id']
            assert max(abs(returned[r['id']]-r['score']) for r in ranking[:200]) < 1e-6
            queries.append({'case_id':c['case_id'],'arm':'raw_segments','passages':texts,'ranking':ranking,
                             'dense_exact_seconds':dense_seconds,'database_seconds':elapsed,'database_union_top200_correct':True})
    finally:
        db.close()
    dump('prepared.json',{'corpus':corpus,'queries':queries,'model_path':'/model',
                        'parent_execution_sha256':sha(PARENT/'execution-manifest.json'),
                        'effective_cases_sha256':sha(PARENT/'cases-v4.json')})
    dump('database-checks.json',checks)
    source_names = ['protocol.md','prepare.py','gpu_worker.py','analyze.py','prepared.json','passage-cache.jsonl','database-checks.json']
    dump('execution-manifest.json',{'before_reranker_scores':True,'sources':{n:sha(HERE/n) for n in source_names},
                  'cases_sha256':sha(PARENT/'cases-v4.json'),'model_sha256':'d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286'})
    print(f'{len(queries)} employees, {len(passages)} unique passage embeddings, {len(checks)} actual Qdrant searches; union correct')


def sha_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


if __name__ == '__main__':
    main()
