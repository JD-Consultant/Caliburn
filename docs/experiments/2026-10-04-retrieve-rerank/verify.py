"""Independent recomputation of result columns and retained topic references."""
import argparse
import hashlib
import json
import math
import statistics
import itertools
from datetime import datetime, UTC
from pathlib import Path

from audit_selection import check_selection
import numpy as np

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))


def lines(name):
    return [json.loads(line) for line in (HERE/name).read_text(encoding='utf-8').splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    execution = read('execution-manifest.json')
    for name,expected in execution['sources'].items():
        assert sha(HERE/name) == expected, name
    prepared = read('prepared.json')
    previous = HERE.parent/'2026-10-04-occupation-retrieval-generalization/cache/20f95996a7ef4d574c29bed8625e84277aee1a73b8d097f5b45b5320ddb27bd8.jsonl'
    assert sha(previous) == prepared['cache_sha256']
    with previous.open(encoding='utf-8') as stream:
        entries = {r['text_sha256']:r['embedding']['dense'] for r in map(json.loads,stream)}
    entries.update({r['text_sha256']:r['embedding']['dense'] for r in lines('new-query-cache.jsonl')})
    text_sha = lambda value:hashlib.sha256(value.encode()).hexdigest()
    vectors = np.asarray([entries[text_sha(r['text'])] for r in prepared['corpus']],dtype=np.float64)
    vectors /= np.linalg.norm(vectors,axis=1,keepdims=True)
    for q in prepared['queries']:
        assert text_sha(q['text']) == q['text_sha256']
        query_vector = np.asarray(entries[q['text_sha256']],dtype=np.float64)
        query_vector /= np.linalg.norm(query_vector)
        scores = vectors@query_vector
        order = sorted(range(805),key=lambda i:(-float(scores[i]),prepared['corpus'][i]['id']))
        assert [prepared['corpus'][i]['id'] for i in order] == [r['id'] for r in q['ranking']]
        assert max(abs(float(scores[i])-r['score']) for i,r in zip(order,q['ranking'],strict=True)) < 1e-12
    runtime = read('gpu-runtime.json')
    assert runtime['execution_manifest_sha256'] == sha(HERE/'execution-manifest.json')
    assert runtime['prepared_sha256'] == sha(HERE/'prepared.json')
    assert runtime['model_revision'] == read('model.json')['revision'] == execution['model_revision']
    assert read('model.json')['files']['model.safetensors']['sha256'] == execution['model_lfs_sha256']
    expected = {(q['case_id'],q['arm']) for q in prepared['queries']}
    queries = {(q['case_id'],q['arm']):q for q in prepared['queries']}
    results = lines('rerank-pairs.jsonl')
    assert len(results) == len(expected) == 32
    assert {(r['case_id'],r['arm']) for r in results} == expected
    pairs = {}
    for record in results:
        key = record['case_id'],record['arm']
        rows = record['pairs']
        assert len(rows) == len({r['id'] for r in rows}) == 200
        assert [r['id'] for r in rows] == [r['id'] for r in queries[key]['ranking'][:200]]
        for rank,r in enumerate(rows,1):
            assert r['dense_rank'] == rank and r['dense_score'] == queries[key]['ranking'][rank-1]['score']
            assert math.isfinite(r['logit']) and r['pair_seconds'] > 0
            assert abs(r['score']-1/(1+math.exp(-r['logit']))) < 1e-12
            windows = r['windows']
            assert windows and max(w['pair_tokens'] for w in windows) <= runtime['max_pair_tokens']
            assert sum(w['passage_tokens'] for w in windows)-64*(len(windows)-1) == r['document_tokens']
            assert all(w['pair_tokens'] == r['query_tokens']+w['passage_tokens']+4 for w in windows)
            assert r['logit'] == max(w['logit'] for w in windows)
        pairs[key] = rows
    cases = {c['case_id']:c for c in read('cases-v4.json')}
    assert sum(len(c['topics']) for c in cases.values()) == 64
    corpus = {r['id']:r for r in prepared['corpus']}
    rows = lines('final-metrics.jsonl')
    assert len(rows) == 15360
    assert len({(r['case_id'],r['arm'],r['method'],r['n'],r['cosine'],r['k'],r['cross']) for r in rows}) == len(rows)
    for r in rows:
        key = r['case_id'],r['arm']
        broad = [p for p in queries[key]['ranking'] if r['cosine'] is None or p['score'] >= r['cosine']][:r['n']]
        if r['method'] == 'dense_only':
            ids = [p['id'] for p in broad[:r['k']]]
        else:
            available = {p['id'] for p in broad}
            scores = sorted((p for p in pairs[key] if p['id'] in available),key=lambda p:(-p['score'],p['id']))
            ids = [p['id'] for p in scores if r['cross'] is None or p['score'] >= r['cross']][:r['k']]
        assert r['selected_ids'] == ids and r['returned'] == len(ids)
        assert r['characters'] == sum(len(corpus[k]['text']) for k in ids)
        topic = cases[key[0]]['topics']
        missing = [t['topic_id'] for t in topic if not {p['id'] for p in t['support']}&set(ids)]
        assert r['missing'] == missing and r['covered'] == len(topic)-len(missing)
        assert r['complete'] == (bool(topic) and not missing)
        assert r['coverage'] == ((len(topic)-len(missing))/len(topic) if topic else None)
        assert r['secondary_covered'] == sum(t['secondary'] and t['topic_id'] not in missing for t in topic)
    chosen = read('selection-development.json')
    summaries = read('parameter-summary-development.json')
    check_selection(rows, cases, sum(len(r['text']) for r in corpus.values()), summaries, chosen['chosen'], read('comparison.json'))
    for method,setting in chosen['chosen'].items():
        passing = [s for s in summaries if s['method'] == method and s['development']['complete_queries'] == s['development']['positive_queries']]
        expected_setting = min(passing,key=lambda s:(s['development']['mean_characters'],s['n'],s['development']['mean_documents'],s['k'],str(s['cosine']),str(s['cross']))) if passing else None
        assert setting == expected_setting
    for compared in read('comparison.json'):
        selected = [r for r in rows if all(r[k] == compared[k] for k in ('method','n','cosine','k','cross'))]
        assert compared['cases'] == selected
        for split in ('development','holdout','all'):
            group = [r for r in selected if split == 'all' or (r['split'] == 'holdout') == (split == 'holdout')]
            positives = [r for r in group if r['total']]
            summary = compared[split]
            assert summary['positive_queries'] == len(positives)
            assert summary['complete_queries'] == sum(r['complete'] for r in positives)
            assert summary['topic_coverage_macro'] == statistics.mean(r['coverage'] for r in positives)
            assert summary['mean_characters'] == statistics.mean(r['characters'] for r in group)
    timings = lines('timings.jsonl')
    assert len(timings) == 20
    assert len({(r['case_id'],r['arm'],r['repeat'],r['n']) for r in timings}) == 20
    assert all(len(r['pair_seconds']) == r['n'] and r['rerank_seconds'] >= sum(r['pair_seconds']) for r in timings)
    assert read('database-complete.json') == {'queries':640,'correct':True,'exact':True,'ANN_tuned':False}
    db = lines('database-checks.jsonl')
    db_key = lambda r:(r['case_id'],r['arm'],r['n'],r['cosine'])
    expected_db = {(case_id,arm,n,cosine) for (case_id,arm),n,cosine in itertools.product(expected,(20,50,100,200),(None,.5,.6,.65,.7))}
    assert len(db) == len({db_key(r) for r in db}) == 640
    assert {db_key(r) for r in db} == expected_db
    for r in db:
        q = queries[(r['case_id'],r['arm'])]
        ids = [p['id'] for p in q['ranking'] if r['cosine'] is None or p['score'] >= r['cosine']][:r['n']]
        assert r['returned_ids'] == ids and r['count'] == len(ids)
        assert r['seconds'] > 0 and 0 <= r['max_score_error'] < 1e-6
    provenance = read('database-provenance-amendment.json')
    assert sha(HERE/'database-prepared-reconstructed.json') == read('database-manifest.json')['prepared_sha256'] == provenance['database_prepared_sha256']
    assert sha(HERE/'prepared.json') == provenance['reranker_prepared_sha256']
    assert read('database-prepared-reconstructed.json')['corpus'] == prepared['corpus']
    for before,after in zip(read('database-prepared-reconstructed.json')['queries'],prepared['queries'],strict=True):
        assert all(before[k] == after[k] for k in ('case_id','arm','text','text_sha256','ranking','dense_exact_seconds'))
    assert read('gpu-complete.json')['quality_pairs'] == 6400
    return {'status':'passed','ranking_queries':32,'pair_scores':6400,'parameter_rows':len(rows),
            'topic_labels':64,'database_exact_queries':640,'warm_timing_samples':20,
            'full805_cosine_rankings_recomputed':32,
            'database_saved_ids_recomputed':640,
            'database_native_score_error_scope':'live assertion and saved statistics only; individual native scores were not saved',
            'scope':'offline recomputation of saved local GPU and Qdrant results; not employee expert validation'}


def seal():
    files = [p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ('artifact-hashes.json','verification.json')]
    value = {p.relative_to(HERE).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in files}
    (HERE/'artifact-hashes.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    return len(files)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seal',action='store_true')
    parser.add_argument('--check-seal',action='store_true')
    args = parser.parse_args()
    result = check()
    if args.seal:
        result['sealed_files'] = seal()
    if args.check_seal:
        value = read('artifact-hashes.json')
        for name,entry in value.items():
            assert sha(HERE/name) == entry['sha256'] and (HERE/name).stat().st_size == entry['bytes'],name
        result['artifact_seal'] = 'passed'
    result['verified_utc'] = datetime.now(UTC).isoformat()
    (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
