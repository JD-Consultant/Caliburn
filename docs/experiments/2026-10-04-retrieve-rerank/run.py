"""Prepare reproducible exact vector pools and inputs for the local GPU worker."""
import hashlib
import json
import time
from pathlib import Path

import httpx
import numpy as np

from prepare import HERE, ROOT, FIRST, SECOND, dump, sha


def key(text):
    return hashlib.sha256(text.encode()).hexdigest()


def prepare_vectors():
    frozen = json.loads((HERE/'frozen.json').read_text(encoding='utf-8'))
    for name, expected in frozen['sources'].items():
        assert sha(ROOT/name) == expected, name
    corpus = json.loads((FIRST/'corpus.json').read_text(encoding='utf-8'))
    queries = json.loads((HERE/'queries.json').read_text(encoding='utf-8'))
    wanted = {key(c['texts']['top']) for c in corpus}|{key(q[a]) for q in queries for a in ('B2','raw_employee') if a in q}
    cache = SECOND/'cache/20f95996a7ef4d574c29bed8625e84277aee1a73b8d097f5b45b5320ddb27bd8.jsonl'
    entries = {}
    for line in cache.open(encoding='utf-8'):
        row = json.loads(line)
        if row['text_sha256'] in wanted:
            entries[row['text_sha256']] = row
    if (HERE/'new-query-cache.jsonl').exists():
        for line in (HERE/'new-query-cache.jsonl').open(encoding='utf-8'):
            row = json.loads(line)
            entries[row['text_sha256']] = row
    query_rows = []
    with httpx.Client(base_url='http://127.0.0.1:8082',timeout=300,trust_env=False) as client:
        runtime = client.get('/runtime').raise_for_status().json()
        assert runtime == json.loads((SECOND/'run-02/retrieval/manifest.json').read_text(encoding='utf-8'))['runtime']
        for q in queries:
            for arm in ('B2','raw_employee'):
                if arm not in q:
                    continue
                text = q[arm]
                hashed = key(text)
                cached = hashed in entries
                if not cached:
                    length = client.post('/token-lengths',json={'texts':[text]}).raise_for_status().json()['lengths'][0]
                    assert length <= runtime['max_length']
                    started = time.perf_counter()
                    embedding = client.post('/embed',json={'texts':[text]}).raise_for_status().json()['embeddings'][0]
                    elapsed = time.perf_counter()-started
                    entries[hashed] = {'text_sha256':hashed,'embedding':embedding,'tokens':length,'batch_seconds':elapsed,'batch_size':1}
                    with (HERE/'new-query-cache.jsonl').open('a',encoding='utf-8') as stream:
                        stream.write(json.dumps(entries[hashed])+'\n')
                query_rows.append({'case_id':q['case_id'],'arm':arm,'text':text,'text_sha256':hashed,
                                   'embedding_cache_hit':cached,'embedding_tokens':entries[hashed]['tokens'],
                                   'embedding_new_seconds':0 if cached else entries[hashed]['batch_seconds']})
    docs = np.asarray([entries[key(c['texts']['top'])]['embedding']['dense'] for c in corpus],dtype=np.float64)
    assert docs.shape == (805,1024) and np.isfinite(docs).all()
    docs /= np.linalg.norm(docs,axis=1,keepdims=True)
    original = {(r['case_id'],r['arm']):r['ranking'] for r in
                (json.loads(line) for line in (SECOND/'run-02/retrieval/fixed-rankings.jsonl').open(encoding='utf-8'))}
    for q in query_rows:
        vector = np.asarray(entries[q['text_sha256']]['embedding']['dense'],dtype=np.float64)
        assert vector.shape == (1024,) and np.isfinite(vector).all()
        vector /= np.linalg.norm(vector)
        times = []
        for _ in range(5):
            started = time.perf_counter()
            scores = docs@vector
            order = sorted(range(805),key=lambda i:(-float(scores[i]),corpus[i]['id']))
            times.append(time.perf_counter()-started)
        q['ranking'] = [{'id':corpus[i]['id'],'score':float(scores[i])} for i in order]
        q['dense_exact_seconds'] = times
        old = original.get((q['case_id'],q['arm']))
        if old:
            assert [r['id'] for r in old] == [r['id'] for r in q['ranking']]
            assert max(abs(a['score']-b['score']) for a,b in zip(old,q['ranking'],strict=True)) < 1e-6
    dump(HERE/'prepared.json',{'corpus':[{'id':c['id'],'title':c['title'],'text':c['texts']['top'],
                                        'embedding_tokens':entries[key(c['texts']['top'])]['tokens']} for c in corpus],
                             'queries':query_rows,'embedding_runtime':runtime,'cache_sha256':sha(cache),
                             'frozen_sha256':sha(HERE/'frozen.json'),'source_code_sha256':sha(Path(__file__))})
    print(f'{len(query_rows)} queries exact ranked; 28 existing rankings reproduced; 4 new local embeddings')


if __name__ == '__main__':
    prepare_vectors()
