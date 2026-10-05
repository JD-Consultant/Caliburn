"""Recompute from native scores, source quotes, vectors, pair traces and labels."""
import math
import argparse
from audit import expected_selection,check_summaries,check_native,check_quote,check_benchmark_task
from common import *

def check():
    initial_cases = read(HERE/'case-manifest.json')
    for name,digest in initial_cases['files_sha256'].items():
        assert sha(HERE/name)==digest
    assert sha(OLD/'cases-v4.json')==initial_cases['parent_cases_sha256']
    restored = read(HERE/'development-cases.json')
    for c in restored:
        c['split'] = c.pop('previous_split')
    assert restored==read(OLD/'cases-v4.json')
    amended = read(HERE/'holdout-cases-2026-10-04-reviewed.json')
    originals = read(HERE/'holdout-cases.json')
    assert all(a['employee_messages']==b['employee_messages'] for a,b in zip(amended,originals,strict=True))
    assert sum(len(c['topics']) for c in amended)==22
    assert sha(HERE/'holdout-cases-2026-10-04-reviewed.json')==read(HERE/'case-amendment-01.json')['effective_sha256']
    execution = read(HERE/'execution-development-02.json')
    assert sha(HERE/'execution-development.json')==execution['previous_manifest_sha256']
    for phase,manifest in [('development',execution),('holdout',read(HERE/'execution-holdout.json'))]:
        for name,digest in manifest['sources'].items():
            assert sha(HERE/name)==digest,(phase,name)
        runtime = read(HERE/f'gpu-runtime-{phase}.json')
        assert runtime['execution_sha256']==sha(HERE/('execution-development-02.json' if phase=='development' else 'execution-holdout.json'))
        assert runtime['model_sha256']==MODEL_SHA and runtime['attention']=='sdpa'
        assert runtime['batch_size']==1 and runtime['max_pair_tokens']==8192 and runtime['overlap']==64
    for name,digest in read(HERE/'selection-frozen.json')['sources'].items():
        assert sha(HERE/name)==digest
    assert sha(HERE/'selection-development.json')==read(HERE/'selection-frozen.json')['selection_sha256']
    assert sha(OLD/'passage-pool/rerank-pairs.jsonl')==execution['borrowed_source_sha256']
    assert sha(CACHE)==execution['document_cache_sha256']
    assert sha(OLD/'passage-pool/passage-cache.jsonl')==execution['passage_cache_sha256']
    corpus = documents(); vectors = doc_vectors(corpus)
    old_cache = {r['text_sha256']:r for r in lines(OLD/'passage-pool/passage-cache.jsonl')}
    new_cache = {r['text_sha256']:r for r in lines(HERE/'holdout-passage-cache.jsonl')}
    assert read(HERE/'holdout-embedding-runtime.json')==read(OLD/'prepared.json')['embedding_runtime']
    for r in new_cache.values():
        assert text_sha(r['text'])==r['text_sha256'] and 0<r['tokens']<=8192 and r['seconds']>0
        raw = np.asarray(r['raw_dense'],dtype=np.float64)
        assert raw.shape==(1024,) and np.isfinite(raw).all()
        assert np.max(np.abs(raw/np.linalg.norm(raw)-np.asarray(r['dense'])))<1e-12
    old_records = {r['case_id']:r for r in lines(OLD/'passage-pool/rerank-pairs.jsonl')}
    old_queries = {q['case_id']:q for q in read(OLD/'passage-pool/prepared.json')['queries']}
    by_doc = {d['id']:d for d in corpus}
    for r in lines(HERE/'borrowed-pairs.jsonl'):
        for index,origin in enumerate(r['origins']):
            source = next(d for d in old_records[origin['case_id']]['pairs'] if d['id']==origin['document_id'])
            p = source['passages'][origin['passage']-1]
            assert text_sha(old_queries[origin['case_id']]['passages'][origin['passage']-1])==r['query_sha256']
            assert text_sha(by_doc[origin['document_id']]['text'])==r['document_sha256']
            assert p['logit']==r['logit'] and p['query_tokens']==r['query_tokens']
            if index==0:
                assert p['windows']==r['windows']  # First origin owns the reused timing trace.
            else:
                assert [{k:v for k,v in w.items() if k!='forward_seconds'} for w in p['windows']]==[{k:v for k,v in w.items() if k!='forward_seconds'} for w in r['windows']]
            assert source['document_tokens']==r['document_tokens']
    for phase in ('development','holdout'):
        generated = lines(HERE/f'supplemental-{phase}-pairs.jsonl')
        jobs_ = read(HERE/f'{phase}-jobs.json')
        expected = {(j['query_sha256'],digest) for j in jobs_ for digest in j['documents'].values()}
        assert {(r['query_sha256'],r['document_sha256']) for r in generated}==expected
        assert len(generated)==len(expected)==read(HERE/f'gpu-complete-{phase}.json')['pairs']
    pairs = load_pairs('holdout')
    for r in pairs.values():
        assert r['model_sha256']==MODEL_SHA and math.isfinite(r['logit'])
        windows = r['windows']; assert windows and r['logit']==max(w['logit'] for w in windows)
        assert sum(w['document_tokens'] for w in windows)-64*(len(windows)-1)==r['document_tokens']
        assert all(w['pair_tokens']==r['query_tokens']+w['document_tokens']+4 and w['pair_tokens']<=8192 and w['forward_seconds']>0 for w in windows)
    all_queries = {}
    for phase in ('development','holdout'):
        prepared = read(HERE/f'prepared-{phase}.json'); assert prepared['corpus']==corpus
        case_file = 'development-cases.json' if phase=='development' else 'holdout-cases-2026-10-04-reviewed.json'
        cases = {c['case_id']:c for c in read(HERE/case_file)}
        cache = old_cache if phase=='development' else new_cache
        queries = {q['case_id']:q for q in prepared['queries']}; assert set(queries)==set(cases)
        all_queries.update(queries)
        for ident,q in queries.items():
            assert q['passages']==cases[ident]['employee_messages']
            pools,global_pool = rank(corpus,vectors,q['passages'],cache)
            assert pools==q['pools'] and global_pool==q['global_pool']
            for t in cases[ident]['topics']:
                check_quote(cases[ident],t,phase)
                for s in t['support']:
                    path = HERE.parents[2]/s['source']; assert sha(path)==s['source_sha256']
                    doc = read(path)
                    task = next(task for unit in doc['ocs_content']['ocu_units'] for task in unit['tasks'] if any(c['code']==s['task_code'] for c in task['task_codes']))
                    assert task['task_codes']==s['task_name']
                    actual = {p['code']:p for block in task['competency_blocks'] for p in block['indicators']}
                    assert all(actual[p['code']]==p for p in s['indicators'])
        configurations = configs() if phase=='development' else [{k:s[k] for k in ('method','n','k')} for s in read(HERE/'selection-development.json')['chosen'].values() if s]
        rows = lines(HERE/f'metrics-{phase}.jsonl')
        expected_keys = {(q,c['method'],c['n'],c['k']) for q in queries for c in configurations}
        assert {(r['case_id'],r['method'],r['n'],r['k']) for r in rows}==expected_keys
        assert len(rows)==len(expected_keys)
        for r in rows:
            q,case = queries[r['case_id']],cases[r['case_id']]
            scores = score_map(q,corpus,pairs)
            config = {k:r[k] for k in ('method','n','k')}
            assert r['selected']==expected_selection(q,scores,config)
            ids = {s['id'] for s in r['selected']}
            missing = [t['topic_id'] for t in case['topics'] if not any(s['id'] in ids for s in t['support'])]
            assert r['missing']==missing and r['covered']==len(case['topics'])-len(missing) and r['total']==len(case['topics'])
            assert r['complete']==(bool(case['topics']) and not missing)
            assert r['coverage']==(r['covered']/r['total'] if r['total'] else None)
            assert r['returned']==len(ids) and r['characters']==sum(len(by_doc[d]['text']) for d in ids)
            assert r['pair_comparisons']==len(required(q,config))
            assert r['secondary_total']==sum(t['secondary'] for t in case['topics'])
            assert r['secondary_covered']==sum(t['secondary'] and t['topic_id'] not in missing for t in case['topics'])
            assert r['known_conflicting_retained']==[d for d in case['hard_negatives'] if d in ids]
            relevant = {k for k,v in case['grades'].items() if v>=2}
            assert r['labeled_relevant_recall']==(len(relevant&ids)/len(relevant) if relevant else None)
        check_summaries(rows,configurations,read(HERE/f'summary-{phase}.json'),read(HERE/'selection-development.json')['chosen'] if phase=='development' else None)
    for search in read(HERE/'database-holdout.json'):
        check_native(all_queries[search['case_id']],search)
    old_checks = read(OLD/'passage-pool/database-checks.json')
    for search in old_checks:
        check_native(all_queries[search['case_id']],{**search,'limit':200,'exact':True})
    plan = read(HERE/'benchmark-plan.json'); assert plan['selection_sha256']==sha(HERE/'selection-development.json')
    timings = lines(HERE/'benchmark-results.jsonl')
    expected_tasks = {r['request_id']:r for r in plan['requests']}
    for case in ('E01','M04'):
        for method,s in read(HERE/'selection-development.json')['chosen'].items():
            if s and method.endswith('dense'):
                for i in (1,2):
                    ident = f'{case}-{method}-{i}'
                    expected_tasks[ident] = {'request_id':ident,'case_id':case,'repeat':i,'config':{k:s[k] for k in ('method','n','k')}}
    assert {t['request_id'] for t in timings}==set(expected_tasks) and len(timings)==len(expected_tasks)
    for t in timings:
        q = all_queries[t['case_id']]; config = t['config']
        check_benchmark_task(t,expected_tasks[t['request_id']],q)
        for search in t['database_searches']:
            check_native(q,search)
        assert t['database_seconds']==sum(s['seconds'] for s in t['database_searches'])
        assert t['total_seconds']>=t['database_seconds']+t['handoff_seconds']+t['merge_seconds']>0
        if t['pairs']:
            response = read(HERE/'benchmark-responses'/f'{t["request_id"]}.json')
            check_benchmark_task(t,expected_tasks[t['request_id']],q,response)
            wanted = {(i,d) for i in range(1,len(q['passages'])+1) for d in by_doc} if config['method']=='full_rerank' else required(q,config)
            assert {(r['passage'],r['id']) for r in response['pairs']}==wanted
            assert len(response['pairs'])==len(wanted)==t['pairs']
            assert 0<t['tokenize_seconds']==response['tokenize_seconds']<t['worker_seconds']==response['worker_seconds']<=t['handoff_seconds']
            assert t['file_transport_overhead_seconds']==max(0,t['handoff_seconds']-t['worker_seconds'])
            scores = {(r['passage'],r['id']):r['logit'] for r in response['pairs']}
            evaluate_config = {'method':'global_rerank','n':805,'k':805} if config['method']=='full_rerank' else config
            assert t['selected_ids']==[r['id'] for r in expected_selection(q,scores,evaluate_config)]
        else:
            assert t['selected_ids']==[r['id'] for r in expected_selection(q,{},config)]
    time_summaries = read(HERE/'timing-summary.json')
    assert len(time_summaries)==len({(t['case_id'],t['config']['method']) for t in timings})
    for s in time_summaries:
        rows = [t for t in timings if t['case_id']==s['case_id'] and t['config']['method']==s['method']]
        assert len(rows)==2 and s['samples_seconds']==[r['total_seconds'] for r in rows]
        assert s['config']==rows[0]['config']==rows[1]['config']
        assert s['pair_counts']==[r['pairs'] for r in rows] and s['returned_counts']==[len(r['selected_ids']) for r in rows]
        for suffix in ('total_seconds','database_seconds','tokenize_seconds','worker_seconds','file_transport_overhead_seconds'):
            assert s['median_'+suffix]==statistics.median(r[suffix] for r in rows)
    diagnostics = read(HERE/'topic-diagnostics.json')
    all_topics = {t['topic_id']:t for c in read(HERE/'development-cases.json')+amended for t in c['topics']}
    assert len(diagnostics)==len(all_topics)==86 and {t['topic_id'] for t in diagnostics}==set(all_topics)
    all_rows = lines(HERE/'metrics-development.jsonl')+lines(HERE/'metrics-holdout.jsonl')
    for trace in diagnostics:
        topic = all_topics[trace['topic_id']]; q = all_queries[trace['case_id']]
        assert trace['work']==topic['work'] and trace['employee_quote']==topic['employee_quote'] and trace['secondary']==topic['secondary']
        support_ids = {s['id'] for s in topic['support']}
        assert {s['id'] for s in trace['support']}==support_ids
        for support in trace['support']:
            ident = support['id']; assert support['title']==by_doc[ident]['title']
            assert support['global_dense_rank']==next(i for i,r in enumerate(q['global_pool'],1) if r['id']==ident)
            assert len(support['passages'])==len(q['passages'])
            for p in support['passages']:
                rank_,row = next((i,r) for i,r in enumerate(q['pools'][p['passage']-1],1) if r['id']==ident)
                assert p['dense_rank']==rank_ and p['cosine']==row['score']
                pair = pairs.get(pair_key(q['passages'][p['passage']-1],by_doc[ident]))
                assert p['score_available']==(pair is not None) and p['logit']==(pair['logit'] if pair else None)
        chosen = read(HERE/'selection-development.json')['chosen']
        assert {o['method'] for o in trace['outcomes']}=={m for m,c in chosen.items() if c}
        for outcome in trace['outcomes']:
            config = chosen[outcome['method']]
            row = next(r for r in all_rows if r['case_id']==trace['case_id'] and all(r[k]==config[k] for k in ('method','n','k')))
            assert outcome['retained']==(trace['topic_id'] not in row['missing'])
            assert outcome['matched']==[s for s in row['selected'] if s['id'] in support_ids]
    state = read(HERE/'service-state-native.json')
    assert state['process_stopped'] is True and state['listening_ports']==[]
    states = [json.loads(line) for line in (HERE/'service-state-containers.jsonl').read_text(encoding='utf-8-sig').splitlines()]
    assert len(states)==4 and all(s['Status']=='exited' and s['Running'] is False for s in states)
    assert [s['ExitCode'] for s in states]==[1,0,0,137]  # Failed import, success, success, stopped embedder.
    assert read(HERE/'gpu-complete-development.json')['elapsed_seconds']+read(HERE/'gpu-benchmark-complete.json')['elapsed_seconds']<2700
    return {'development_rows':len(lines(HERE/'metrics-development.jsonl')),'held_rows':len(lines(HERE/'metrics-holdout.jsonl')),
            'borrowed_pairs':len(lines(HERE/'borrowed-pairs.jsonl')),'supplemented_pairs':sum(len(lines(HERE/f'supplemental-{p}-pairs.jsonl')) for p in ('development','holdout')),
            'benchmark_samples':len(timings),'passed':True}

def seal():
    files = [p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='artifact-hashes.json']
    dump('artifact-hashes.json',{str(p.relative_to(HERE)).replace('\\','/'):sha(p) for p in sorted(files)})

if __name__=='__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--seal',action='store_true'); parser.add_argument('--check-seal',action='store_true')
    args = parser.parse_args()
    if args.check_seal:
        hashes = read(HERE/'artifact-hashes.json')
        for name,digest in hashes.items():
            assert sha(HERE/name)==digest,name
        print(f'{len(hashes)} sealed hashes verified')
    else:
        result = check(); print(json.dumps(result,indent=2))
        if args.seal:
            seal()
