"""Recompute full max-cosine ranks, MAX cross scores, and all retained topics."""
import hashlib
import json
import math
import statistics
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
from audit_selection import check_selection

import numpy as np

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def read(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))


def lines(name):
    return [json.loads(l) for l in (HERE/name).read_text(encoding='utf-8').splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    execution = read('execution-manifest.json')
    for name,expected in execution['sources'].items():
        assert sha(HERE/name) == expected,name
    assert sha(PARENT/'cases-v4.json') == execution['cases_sha256']
    amendment = read('analysis-amendment.json')
    assert sha(HERE/'analyze-v2.py') == amendment['analysis_v2_sha256']
    assert sha(HERE/'execution-manifest.json') == amendment['original_execution_sha256']
    prepared = read('prepared.json')
    assert prepared['parent_execution_sha256'] == sha(PARENT/'execution-manifest.json')
    parent_execution = read('../execution-manifest.json')
    assert sha(PARENT/'evaluate.py') == parent_execution['sources']['evaluate.py']
    assert read('gpu-runtime.json')['execution_manifest_sha256'] == sha(HERE/'execution-manifest.json')
    cases = {c['case_id']:c for c in read('../cases-v4.json')}
    corpus = {r['id']:r for r in prepared['corpus']}
    query = {q['case_id']:q for q in prepared['queries']}
    # Recompute all805, independent of saved max-cosine rankings and DB union.
    previous = PARENT.parent/'2026-10-04-occupation-retrieval-generalization/cache/20f95996a7ef4d574c29bed8625e84277aee1a73b8d097f5b45b5320ddb27bd8.jsonl'
    with previous.open(encoding='utf-8') as stream:
        entries = {r['text_sha256']:r['embedding']['dense'] for r in map(json.loads,stream)}
    text_sha = lambda text:hashlib.sha256(text.encode()).hexdigest()
    docs = np.asarray([entries[text_sha(r['text'])] for r in prepared['corpus']],dtype=np.float64)
    docs /= np.linalg.norm(docs,axis=1,keepdims=True)
    part = {r['text_sha256']:r['dense'] for r in lines('passage-cache.jsonl')}
    assert len(part) == 46
    database = read('database-checks.json')
    database_by_key = {(r['case_id'],r['passage']):r for r in database}
    assert len(database_by_key) == len(database) == 58
    expected_database_keys = {(q['case_id'],i) for q in prepared['queries'] for i in range(1,len(q['passages'])+1)}
    assert set(database_by_key) == expected_database_keys
    database_score_errors = []
    for q in prepared['queries']:
        assert q['passages'] == cases[q['case_id']]['employee_messages']
        passage_scores = docs@np.asarray([part[text_sha(t)] for t in q['passages']]).T
        for passage in range(len(q['passages'])):
            native = database_by_key[(q['case_id'],passage+1)]
            order = sorted(range(805),key=lambda i:(-float(passage_scores[i,passage]),prepared['corpus'][i]['id']))[:200]
            assert [prepared['corpus'][i]['id'] for i in order] == [r['id'] for r in native['returned']]
            error = max(abs(float(passage_scores[i,passage])-r['score']) for i,r in zip(order,native['returned'],strict=True))
            assert error < 1e-6 and native['seconds'] > 0
            database_score_errors.append(error)
        scores = np.max(passage_scores,axis=1)
        ids = [prepared['corpus'][i]['id'] for i in sorted(range(805),key=lambda i:(-float(scores[i]),prepared['corpus'][i]['id']))]
        assert ids == [r['id'] for r in q['ranking']]
    results = lines('rerank-pairs.jsonl')
    assert len(results) == len(query) == 18 and {r['case_id'] for r in results} == set(query)
    pair = {}
    for record in results:
        q = query[record['case_id']]
        assert len(record['pairs']) == 200
        assert [r['id'] for r in record['pairs']] == [r['id'] for r in q['ranking'][:200]]
        for r in record['pairs']:
            assert len(r['passages']) == len(q['passages'])
            assert r['logit'] == max(p['logit'] for p in r['passages'])
            assert math.isfinite(r['logit']) and abs(r['score']-1/(1+math.exp(-r['logit']))) < 1e-12
            for p in r['passages']:
                windows = p['windows']
                assert p['logit'] == max(w['logit'] for w in windows)
                assert all(w['pair_tokens'] == p['query_tokens']+w['document_tokens']+4 <= 8192 for w in windows)
                assert sum(w['document_tokens'] for w in windows)-64*(len(windows)-1) == r['document_tokens']
        pair[record['case_id']] = record['pairs']
    rows = lines('final-metrics.jsonl')
    assert len(rows) == 8640 and len({(r['case_id'],r['method'],r['n'],r['cosine'],r['k'],r['cross']) for r in rows}) == 8640
    for r in rows:
        q = query[r['case_id']]
        broad = [p for p in q['ranking'] if r['cosine'] is None or p['score'] >= r['cosine']][:r['n']]
        if r['method'] == 'dense_only':
            ids = [p['id'] for p in broad[:r['k']]]
        else:
            available = {p['id'] for p in broad}
            scored = sorted((p for p in pair[r['case_id']] if p['id'] in available),key=lambda p:(-p['score'],p['id']))
            ids = [p['id'] for p in scored if r['cross'] is None or p['score'] >= r['cross']][:r['k']]
        assert r['selected_ids'] == ids and r['characters'] == sum(len(corpus[k]['text']) for k in ids)
        topics = cases[r['case_id']]['topics']
        missing = [t['topic_id'] for t in topics if not {p['id'] for p in t['support']}&set(ids)]
        assert r['missing'] == missing and r['covered'] == len(topics)-len(missing)
        assert r['complete'] == (bool(topics) and not missing)
        assert r['coverage'] == ((len(topics)-len(missing))/len(topics) if topics else None)
    summaries = read('parameter-summary-development.json')
    check_selection(rows, cases, sum(len(r['text']) for r in corpus.values()), summaries, read('selection-development.json')['chosen'], read('comparison.json'))
    for method,setting in read('selection-development.json')['chosen'].items():
        passing = [s for s in summaries if s['method'] == method and s['development']['complete_queries'] == s['development']['positive_queries']]
        expected = min(passing,key=lambda s:(s['development']['mean_characters'],s['n'],s['development']['mean_documents'],s['k'],str(s['cosine']),str(s['cross']))) if passing else None
        assert setting == expected
    for compared in read('comparison.json'):
        selected = [r for r in rows if all(r[k] == compared[k] for k in ('method','n','cosine','k','cross'))]
        assert compared['cases'] == selected
        for split in ('development','holdout','all'):
            group = [r for r in selected if split == 'all' or (r['split'] == 'holdout') == (split == 'holdout')]
            positives = [r for r in group if r['total']]
            assert compared[split]['complete_queries'] == sum(r['complete'] for r in positives)
            assert compared[split]['topic_coverage_macro'] == statistics.mean(r['coverage'] for r in positives)
            assert compared[split]['mean_characters'] == statistics.mean(r['characters'] for r in group)
    assert len(read('database-checks.json')) == 58
    assert len(lines('timings.jsonl')) == 10
    result = {'status':'passed','employees':18,'topics':64,'full805_max_cosine_rankings':18,
              'qdrant_passage_queries':58,'candidate_document_scores':3600,'parameter_rows':8640,'warm_timing_samples':10,
              'database_native_scores_recomputed':58,'database_max_score_error':max(database_score_errors)}
    (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    check()
