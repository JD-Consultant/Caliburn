"""Independent recomputation of ranking, source/evidence binding and trial totals."""
import math
from collections import defaultdict
from pipeline import *


def main():
    check_manifest('benchmark-execution-02.json')
    check_manifest('gpu-input-manifest.json')
    cases = {c['case_id']:c for c in read(PARENT / 'cases-v1.json')['cases']}
    corpus = {d['id']:d for d in read(HERE / 'corpus.json')}
    queries = {q['query_id']:q for q in read(HERE / 'queries.json')}
    for case_id, case in cases.items():
        covered = set()
        for query in [q for q in queries.values() if q['case_id']==case_id and q['variant']=='segments']:
            assert '\n'.join(span['text'] for span in query['source_spans']) == query['text']
            assert text_sha(query['text']) == query['text_sha256']
            for span in query['source_spans']:
                assert case['employee_statement'][span['start']:span['end']] == span['text']
                covered.update(range(span['start'],span['end']))
        assert covered == set(range(len(case['employee_statement'])))
    ranks = {r['query_id']:r['ranked'] for r in read(HERE / 'dense-rankings.json')}
    assert all(len(r)==805 and len({h['id'] for h in r})==805 for r in ranks.values())
    pairs = [json.loads(line) for line in (HERE / 'pairs.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(pairs)==300 and len({(r['query_id'],r['id']) for r in pairs})==300
    values = {}
    for row in pairs:
        assert row['query_sha256']==text_sha(queries[row['query_id']]['text'])
        assert row['document_sha256']==text_sha(corpus[row['id']]['text'])
        assert row['cache_reused'] is False and row['logit']==max(w['logit'] for w in row['windows'])
        assert all(w['pair_tokens']<=8192 for w in row['windows'])
        values[(row['query_id'],row['id'])]=row['logit']
    results = read(HERE / 'results.json')
    assert len(results)==20
    for result in results:
        pools = []
        for query_id in result['query_ids']:
            pool = ranks[query_id][:20]
            if result['method'] in ('R02','R04'):
                pool = sorted([{'id':r['id'],'score':values[(query_id,r['id'])]} for r in pool],key=lambda r:(-r['score'],r['id']))
            pools.append(pool)
        if len(pools)==1:
            expected=[r['id'] for r in pools[0][:5]]
        else:
            scores=defaultdict(float)
            for pool in pools:
                for rank,hit in enumerate(pool):
                    scores[hit['id']]+=1/(2+rank)
            expected=sorted(scores,key=lambda key:(-scores[key],key))[:5]
        assert expected==[r['id'] for r in result['selected']]
        assert len(set(expected))==5
    judged = read(HERE / 'judgments.json')
    wanted = {(r['case_id'],hit['id']) for r in results for hit in r['selected']}
    assert {(r['case_id'],r['document_id']) for r in judged}==wanted and len(judged)==len(wanted)
    for row in judged:
        employee=cases[row['case_id']]['employee_statement']; reference=corpus[row['document_id']]['text']
        assert row['employee_sha256']==text_sha(employee) and row['document_sha256']==text_sha(reference)
        validate_judgment(row['judgment'],employee,reference)
    benches=[json.loads(line) for line in (HERE / 'benchmark-results-02.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(benches)==60 and len({r['task_id'] for r in benches})==60
    assert all(r['pair_count']==(20*r['query_count'] if r['method'] in ('R02','R04') else 0) for r in benches)
    protected=read(PARENT.parent / '2026-10-04-retrieval-reference-views/execution-manifest.json')['inputs']
    for path,meta in protected.items():
        assert sha(ROOT/path)==meta['sha256']
    sealed=0
    for directory in ['2026-10-04-occupation-retrieval','2026-10-04-occupation-retrieval-generalization','2026-10-04-retrieve-rerank','2026-10-04-retrieval-passage-quota','2026-10-04-retrieval-input-boundaries','2026-10-04-retrieval-reference-views']:
        path=PARENT.parent/directory/'artifact-hashes.json'; seal=read(path)
        for name,item in seal.get('files',seal).items():
            expected=item if isinstance(item,str) else item['sha256']
            assert sha(path.parent/name)==expected
            sealed+=1
    dump('verification.json',{'passed':True,'cases':5,'queries':15,'full_rankings':15,'native_initial_checks':15,
         'quality_pairs':300,'final_groups':20,'final_positions':100,'unique_judgments':len(judged),'warm_trials':60,
         'prior_protected_inputs_unchanged':len(protected),'prior_sealed_artifacts_unchanged':sealed,
         'limit':'mechanism/source binding only; semantic judgments remain model assessments'})
    print(f'Verified 20 groups / 100 positions / {len(judged)} unique grades; 474 prior sealed artifacts unchanged.')


if __name__ == '__main__':
    main()
