"""Read-only actual Qdrant exact search/threshold agreement and local timings."""
import hashlib
import json
import time

import numpy as np
from qdrant_client import QdrantClient, models

from evaluate import select
from prepare import HERE, FIRST, SECOND, dump, sha


def main():
    prepared = json.loads((HERE/'prepared.json').read_text(encoding='utf-8'))
    wanted = {q['text_sha256'] for q in prepared['queries']}
    vectors = {}
    paths = [SECOND/'cache/20f95996a7ef4d574c29bed8625e84277aee1a73b8d097f5b45b5320ddb27bd8.jsonl',HERE/'new-query-cache.jsonl']
    for path in paths:
        for line in path.open(encoding='utf-8'):
            r = json.loads(line)
            if r['text_sha256'] in wanted:
                v = np.asarray(r['embedding']['dense'],dtype=np.float64)
                vectors[r['text_sha256']] = (v/np.linalg.norm(v)).tolist()
    name = json.loads((FIRST/'candidate-01/collection.json').read_text())['name']
    client = QdrantClient(url='http://127.0.0.1:6335',timeout=60,trust_env=False)
    try:
        info = client.get_collection(name)
        assert info.points_count == 805
        dump(HERE/'database-manifest.json',{'collection':name,'configuration':info.model_dump(mode='json'),
                 'prepared_sha256':sha(HERE/'prepared.json'),'script_sha256':sha(HERE/'database_check.py'),
                 'operation':'read-only exact query; existing independent research collection'})
        with (HERE/'database-checks.jsonl').open('x',encoding='utf-8') as stream:
            count = 0
            for q in prepared['queries']:
                for n in (20,50,100,200):
                    for cosine in (None,0.5,0.6,0.65,0.7):
                        expected = select(q['ranking'],n,cosine)
                        start = time.perf_counter()
                        actual = client.query_points(name,query=vectors[q['text_sha256']],using='dense',limit=n,
                            score_threshold=cosine,with_payload=True,search_params=models.SearchParams(exact=True)).points
                        elapsed = time.perf_counter()-start
                        ids = [p.payload['ocs_code'] for p in actual]
                        assert ids == [r['id'] for r in expected], (q['case_id'],q['arm'],n,cosine)
                        error = max((abs(p.score-r['score']) for p,r in zip(actual,expected,strict=True)),default=0)
                        assert error < 1e-6
                        stream.write(json.dumps({'case_id':q['case_id'],'arm':q['arm'],'n':n,'cosine':cosine,
                            'seconds':elapsed,'count':len(actual),'max_score_error':error,'returned_ids':ids})+'\n')
                        count += 1
            stream.flush()
        dump(HERE/'database-complete.json',{'queries':count,'correct':True,'exact':True,'ANN_tuned':False})
        print(f'{count} actual Qdrant exact queries agree with full cosine rankings and thresholds')
    finally:
        client.close()


if __name__ == '__main__':
    main()
