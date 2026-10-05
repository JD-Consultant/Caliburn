"""Independent quality recomputation, deliberately does not call selection.py."""
import statistics

def check_quote(case,topic,phase):
    indices = topic.get('employee_message_indices',[topic['employee_message']])
    assert indices and len(indices)==len(set(indices))
    assert all(1<=i<=len(case['employee_messages']) for i in indices)
    joined = '\n'.join(case['employee_messages'][i-1] for i in indices)
    legacy = {('E02','E02-T03'),('E03','E03-T02'),('E08','E08-T03')}
    if phase=='development' and (case['case_id'],topic['topic_id']) in legacy:
        assert indices==[1,2] and topic['employee_message']==1
        assert topic['employee_quote']==case['employee_messages'][0],'wrong legacy anchor'
    else:
        assert topic['employee_quote']==joined,'incomplete quote'
    return joined

def expected_selection(q,pairs,config):
    n,k = config['n'],config['k']
    rerank = config['method'].endswith('rerank')
    if config['method'].startswith('global'):
        maximum = {}
        for pool in q['pools']:
            for row in pool:
                maximum[row['id']] = max(maximum.get(row['id'],-float('inf')),row['score'])
        ids = sorted(maximum,key=lambda d:(-maximum[d],d))[:n]
        if rerank:
            values = {d:max(pairs[(p,d)] for p in range(1,len(q['passages'])+1)) for d in ids}
            ids.sort(key=lambda d:(-values[d],d))
        return [{'id':d,'matches':[{'passage':p,'logit':pairs.get((p,d))} for p in range(1,len(q['passages'])+1)]} for d in ids[:k]]
    retained = {}
    for p,pool in enumerate(q['pools'],1):
        by_id = {r['id']:(rank,r['score']) for rank,r in enumerate(pool[:n],1)}
        ids = sorted(by_id,key=lambda d:(-pairs[(p,d)] if rerank else -by_id[d][1],d))[:k]
        for position,d in enumerate(ids,1):
            retained.setdefault(d,[]).append({'passage':p,'dense_rank':by_id[d][0],'cosine':by_id[d][1],
                 'rerank_rank':position if rerank else None,'logit':pairs[(p,d)] if rerank else None})
    field = 'logit' if rerank else 'cosine'
    return [{'id':d,'matches':retained[d]} for d in sorted(retained,key=lambda d:(-max(m[field] for m in retained[d]),d))]

def summary(rows):
    return {'cases':len(rows),'positive_cases':sum(bool(r['total']) for r in rows),
            'complete_cases':sum(r['complete'] for r in rows if r['total']),
            'covered':sum(r['covered'] for r in rows),'total':sum(r['total'] for r in rows),
            'secondary_covered':sum(r['secondary_covered'] for r in rows),'secondary_total':sum(r['secondary_total'] for r in rows),
            'mean_characters':statistics.mean(r['characters'] for r in rows),'mean_documents':statistics.mean(r['returned'] for r in rows),
            'mean_pair_comparisons':statistics.mean(r['pair_comparisons'] for r in rows)}

def check_summaries(rows,configs,summaries,chosen=None):
    assert len(summaries)==len(configs),'missing parameter comparisons'
    computed = []
    for config in configs:
        group = [r for r in rows if all(r[key]==value for key,value in config.items())]
        assert group and len({r['case_id'] for r in group})==len(group)
        computed.append({**config,'metrics':summary(group)})
    assert summaries==computed,'forged aggregate'
    if chosen is not None:
        assert set(chosen)=={'global_dense','global_rerank','quota_dense','quota_rerank'}
        for method in chosen:
            passing = [r for r in computed if r['method']==method and r['metrics']['complete_cases']==12 and r['metrics']['covered']==64]
            expected = min(passing,key=lambda r:(r['metrics']['mean_characters'],r['metrics']['mean_pair_comparisons'],r['n'],r['k'])) if passing else None
            assert chosen[method]==expected,'forged development choice'

def check_native(q,search):
    pool = q['pools'][search['passage']-1][:search['limit']]
    assert search['exact'] is True
    assert [r['id'] for r in search['returned']]==[r['id'] for r in pool],'wrong native candidate IDs'
    error = max(abs(a['score']-b['score']) for a,b in zip(search['returned'],pool,strict=True))
    assert error<1e-6,'wrong native candidate score'
    if 'max_score_error' in search:
        assert search['max_score_error']==error
    assert search['seconds']>0

def check_benchmark_task(row,expected,q,response=None):
    assert all(row[key]==expected[key] for key in ('request_id','case_id','repeat','config')),'benchmark task mislabeled'
    searches = row['database_searches']
    if row['config']['method']=='full_rerank':
        assert searches==[]
    else:
        assert len(searches)==len(q['passages']),'missing benchmark DB search'
        assert [s['passage'] for s in searches]==list(range(1,len(q['passages'])+1))
        assert all(s['limit']==row['config']['n'] for s in searches)
    if response is not None:
        assert response['request_id']==row['request_id'],'mislabeled worker response'
