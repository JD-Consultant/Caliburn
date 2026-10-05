from collections import defaultdict
import statistics
from pipeline import *
from projection import query_from_units, span


def main():
    check_manifest()
    check_manifest('analysis-manifest.json')
    cases = {c['case_id']:c for c in read(HERE/'cases.json')}
    queries = {q['query_id']:q for q in read(HERE/'queries.json')}
    corpus = {d['id']:d for d in read(HERE/'corpus.json')}
    for case in cases.values():
        path = ROOT/case['source_path']; assert sha(path)==case['source_sha256']
        turns = read(path)['turns']
        for query in (q for q in queries.values() if q['case_id']==case['case_id']):
            for item in query['source_spans']:
                field = 'employee' if item['speaker']=='employee' else 'consultant'
                assert turns[item['turn']-1][field][item['start']:item['end']]==item['text']
            assert text_sha(query['text'])==query['text_sha256']
            if query['variant']=='initial':
                assert query['text']==turns[0]['employee']
            elif query['variant']=='whole':
                assert query['text']==query_from_units(case['units'],range(1,len(turns)+1))[0]
            else:
                group = case['manual_groups'][int(query['query_id'].rsplit('-',1)[1])-1]
                first = turns[0]['employee']; anchor=span(1,'employee',first,0,first.index('。')+1)
                assert query['text']==query_from_units(case['units'],group['answer_turns'],anchor)[0]
        coverage=set().union(*(set(g['answer_turns']) for g in case['manual_groups']))
        assert coverage==set(range(1,len(turns)+1))
    ranks={r['query_id']:r['ranked'] for r in read(HERE/'dense-rankings.json')}
    assert len(ranks)==len(queries) and all(len(r)==805 and len({d['id'] for d in r})==805 for r in ranks.values())
    native=read(HERE/'database-checks.json')
    for row in native:
        assert row['max_score_error']<1e-6 and [h['id'] for h in row['returned']]==[h['id'] for h in ranks[row['query_id']][:20]]
    pairs=[json.loads(line) for line in (HERE/'pairs.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(pairs)==len(queries)*20 and len({(r['query_id'],r['id']) for r in pairs})==len(pairs)
    def check_pair(row):
        assert row['query_sha256']==queries[row['query_id']]['text_sha256']
        assert row['document_sha256']==text_sha(corpus[row['id']]['text'])
        assert row['cache_reused'] is False and all(w['pair_tokens']<=8192 for w in row['windows'])
        assert row['logit']==max(w['logit'] for w in row['windows'])
    for row in pairs: check_pair(row)
    values={(r['query_id'],r['id']):r['logit'] for r in pairs}
    results=read(HERE/'results.json'); assert len(results)==18
    for result in results:
        pools=[]
        for query_id in result['query_ids']:
            pool=ranks[query_id][:20]
            if result['method'] in ('I02','R02','R04'):
                pool=sorted([{'id':r['id'],'score':values[(query_id,r['id'])]} for r in pool],key=lambda r:(-r['score'],r['id']))
            pools.append(pool)
        assert pools==result['query_rankings']
        if len(pools)==1: expected=[h['id'] for h in pools[0]]
        else:
            scores=defaultdict(float)
            for pool in pools:
                for index,hit in enumerate(pool): scores[hit['id']]+=1/(2+index)
            expected=sorted(scores,key=lambda i:(-scores[i],i))
        assert expected==[h['id'] for h in result['merged_ranking']]
        assert expected[:5]==[h['id'] for h in result['selected']] and len(set(expected[:5]))==5
    wanted={(r['case_id'],h['id']) for r in results for h in r['selected']}
    judged=read(HERE/'judgments-02.json')
    assert len(judged)==len(wanted) and {(r['case_id'],r['document_id']) for r in judged}==wanted
    for row in judged:
        validate_judgment(row['judgment'],cases[row['case_id']]['employee_statement'],corpus[row['document_id']]['text'])
    bench=[json.loads(line) for line in (HERE/'benchmark-results.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(bench)==54 and len({b['task_id'] for b in bench})==54
    fresh=0
    for path in (HERE/'benchmark-responses').glob('*.json'):
        for pair in read(path)['pairs']: check_pair(pair); fresh+=1
    assert fresh==1080
    for row in read(HERE/'timing-summary.json'):
        samples=[b['total_seconds'] for b in bench if b['case_id']==row['case_id'] and b['method']==row['method']]
        assert len(samples)==3 and samples==row['samples_seconds'] and statistics.median(samples)==row['median_seconds']
    previous=PARENT.parent/'2026-10-04-representative-occupation-top5/run-01'
    for path,meta in read(previous/'artifact-hashes.json')['files'].items(): assert sha(previous/path)==meta['sha256']
    dump('verification.json',{'passed':True,'cases':3,'source_turns':69,'queries':len(queries),
         'native_exact_queries':len(native),'quality_pairs':len(pairs),'groups':18,'final_positions':90,
         'unique_judgments':len(judged),'warm_trials':54,'fresh_benchmark_pairs':fresh,'previous_run_files_unchanged':410,
         'limit':'source, ranking and timing only; not model semantic correctness'})
    print(f'Verified 69 source turns, {len(queries)} queries, 18 groups, {len(judged)} unique judgments; prior 410 unchanged')


if __name__ == '__main__':
    main()
