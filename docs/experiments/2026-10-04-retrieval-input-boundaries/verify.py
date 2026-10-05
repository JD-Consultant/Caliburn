"""Recompute retained references, lossless input origins, native scores and timing."""
import argparse
import math
import statistics
import numpy as np
from support import *
from audit import check_quote
from audit_boundaries import check_task

def check():
    frozen = read(HERE/'input-manifest.json')
    for name,digest in frozen['files'].items():
        assert sha(HERE/name)==digest,name
    for name,digest in frozen['source_hashes'].items():
        assert sha(QUOTA/name)==digest,name
    amendment = read(HERE/'input-amendment-01.json')
    assert amendment['initial_cases_sha256']==sha(HERE/'cases.json')
    assert amendment['effective_cases_sha256']==sha(HERE/'cases-observed.json')
    cases = read(HERE/'cases-observed.json'); initial = read(HERE/'cases.json')
    for c,original in zip(cases,initial,strict=True):
        restored = dict(c); restored['split'] = restored.pop('source_split')
        assert c['split']=='observed_regression' and restored==original
    assert initial==read(QUOTA/'development-cases.json')+read(QUOTA/'holdout-cases-2026-10-04-reviewed.json')
    assert len(cases)==22 and sum(len(c['topics']) for c in cases)==86
    by_case = {c['case_id']:c for c in cases}
    inputs = read(HERE/'inputs.json')
    assert len(inputs)==66 and {(q['case_id'],q['variant']) for q in inputs}=={(c['case_id'],v) for c in cases for v in VARIANTS}
    for q in inputs:
        messages = by_case[q['case_id']]['employee_messages']
        assert q['passages']==[r['text'] for r in q['origins']]
        if q['variant']=='joined_employee':
            assert q['passages']==['\n\n'.join(messages)] and q['origins'][0]['message_indices']==list(range(1,len(messages)+1))
        else:
            for index,text in enumerate(messages,1):
                records = [r for r in q['origins'] if r['message']==index]
                assert ''.join(r['text'] for r in records)==text
                assert records[0]['start']==0 and records[-1]['end']==len(text)
                assert all(a['end']==b['start'] for a,b in zip(records,records[1:]))
                assert all(text[r['start']:r['end']]==r['text'] for r in records)
                if q['variant']=='original_messages':
                    assert len(records)==1
    execution = read(HERE/'execution.json')
    for name,digest in execution['sources'].items():
        assert sha(HERE/name)==digest,name
    for name,digest in execution['prior_sources'].items():
        assert sha(QUOTA/name)==digest,name
    assert sha(prior.CACHE)==execution['document_cache_sha256']
    assert read(HERE/'embedding-runtime.json')==read(prior.OLD/'prepared.json')['embedding_runtime']
    runtime = read(HERE/'gpu-runtime.json')
    assert runtime['execution_sha256']==sha(HERE/'execution.json') and runtime['model_sha256']==MODEL_SHA
    assert runtime['attention']=='sdpa' and runtime['batch_size']==1 and runtime['max_pair_tokens']==8192 and runtime['overlap']==64
    prepared = read(HERE/'prepared.json'); corpus = prepared['corpus']; assert corpus==prior.documents()
    by_doc = {d['id']:d for d in corpus}; vectors = prior.doc_vectors(corpus)
    entries = lines(HERE/'all-passage-cache.jsonl')
    cache = {r['text_sha256']:r for r in entries}
    assert len(cache)==len(entries) and set(cache)=={text_sha(t) for q in inputs for t in q['passages']}
    new = lines(HERE/'new-passage-cache.jsonl')
    assert {r['text_sha256'] for r in new}=={k for k,r in cache.items() if not r['cache_reused']}
    for digest,r in cache.items():
        v = np.asarray(r['dense'],dtype=np.float64)
        assert v.shape==(1024,) and np.isfinite(v).all() and abs(np.linalg.norm(v)-1)<1e-12
        assert 0<r['tokens']<=8192 and r['seconds']>0
        if not r['cache_reused']:
            assert text_sha(r['text'])==digest
            raw = np.asarray(r['raw_dense'],dtype=np.float64)
            assert np.max(np.abs(raw/np.linalg.norm(raw)-v))<1e-12
        else:
            filename = HERE.parent/r['origin']
            old = next(s for s in lines(filename) if s['text_sha256']==digest)
            assert all(r[k]==old[k] for k in old)
    queries = {(q['case_id'],q['variant']):q for q in prepared['queries']}
    assert len(queries)==66
    for raw in inputs:
        q = queries[(raw['case_id'],raw['variant'])]
        assert all(q[k]==raw[k] for k in raw)
        maximum = {}
        for p,text in enumerate(q['passages']):
            v = np.asarray(cache[text_sha(text)]['dense'],dtype=np.float64); v /= np.linalg.norm(v)
            values = vectors@v
            order = sorted(range(805),key=lambda i:(-float(values[i]),corpus[i]['id']))
            assert [r['id'] for r in q['pools'][p]]==[corpus[i]['id'] for i in order]
            assert max(abs(r['score']-float(values[i])) for r,i in zip(q['pools'][p],order,strict=True))<1e-12
            for r in q['pools'][p]:
                maximum[r['id']] = max(maximum.get(r['id'],-float('inf')),r['score'])
        assert q['global_pool']==sorted(({'id':k,'score':v} for k,v in maximum.items()),key=lambda r:(-r['score'],r['id']))
        for topic in by_case[q['case_id']]['topics']:
            phase = 'holdout' if q['case_id'].startswith('H') else 'development'
            check_quote(by_case[q['case_id']],topic,phase)
            for s in topic['support']:
                assert sha(HERE.parents[2]/s['source'])==s['source_sha256']
    checks = read(HERE/'database-checks.json')
    expected_searches = {(q['case_id'],q['variant'],p) for q in inputs for p in range(1,len(q['passages'])+1)}
    assert len(checks)==len(expected_searches)==256
    assert {(r['case_id'],r['variant'],r['passage']) for r in checks}==expected_searches
    for search in checks:
        assert search['limit']==20
        check_native(queries[(search['case_id'],search['variant'])],search)
        assert len({r['point_id'] for r in search['returned']})==20
    borrowed = prior.load_pairs('holdout')
    expected_missing = {}
    for q in queries.values():
        for p,pool in enumerate(q['pools'],1):
            for d in pool[:20]:
                key = prior.pair_key(q['passages'][p-1],by_doc[d['id']])
                if key not in borrowed:
                    expected_missing[key] = (q['passages'][p-1],d['id'])
    jobs = read(HERE/'jobs.json')
    job_keys = {j['query_sha256']+':'+digest for j in jobs for digest in j['documents'].values()}
    assert job_keys==set(expected_missing) and sum(len(j['documents']) for j in jobs)==len(job_keys)
    for j in jobs:
        assert text_sha(j['query'])==j['query_sha256']
        assert all(text_sha(by_doc[ident]['text'])==digest for ident,digest in j['documents'].items())
    generated = lines(HERE/'supplemental-pairs.jsonl')
    assert len(generated)==len(expected_missing)==read(HERE/'gpu-quality-complete.json')['pairs']
    assert {r['query_sha256']+':'+r['document_sha256'] for r in generated}==set(expected_missing)
    pairs = load_scores()
    for r in generated:
        assert r['model_sha256']==MODEL_SHA and math.isfinite(r['logit']) and r['score_seconds']>0
        windows = r['windows']; assert windows and r['logit']==max(w['logit'] for w in windows)
        assert sum(w['document_tokens'] for w in windows)-64*(len(windows)-1)==r['document_tokens']
        assert all(w['pair_tokens']==r['query_tokens']+w['document_tokens']+4 and w['pair_tokens']<=8192 and w['forward_seconds']>0 for w in windows)
    metrics = lines(HERE/'metrics.jsonl')
    expected_rows = {(q['case_id'],q['variant'],c['method']) for q in inputs for c in CONFIGS}
    assert len(metrics)==len(expected_rows)==132 and {(r['case_id'],r['variant'],r['method']) for r in metrics}==expected_rows
    previous = lines(QUOTA/'metrics-development.jsonl')+lines(QUOTA/'metrics-holdout.jsonl')
    summaries = []
    for r in metrics:
        q = queries[(r['case_id'],r['variant'])]; case = by_case[r['case_id']]
        assert r['n']==20 and r['k']==5
        scores = prior.score_map(q,corpus,pairs)
        assert r['selected']==expected_selection(q,scores,{k:r[k] for k in ('method','n','k')})
        ids = {d['id'] for d in r['selected']}; topics = case['topics']
        missing = [t['topic_id'] for t in topics if not {s['id'] for s in t['support']}&ids]
        assert r['missing']==missing and r['covered']==len(topics)-len(missing) and r['total']==len(topics)
        assert r['reference_complete']==(bool(topics) and not missing)
        assert r['reference_coverage']==(r['covered']/r['total'] if r['total'] else None)
        assert r['secondary_total']==sum(t['secondary'] for t in topics)
        assert r['secondary_covered']==sum(t['secondary'] and t['topic_id'] not in missing for t in topics)
        assert r['returned']==len(ids) and r['characters']==sum(len(by_doc[d]['text']) for d in ids)
        assert r['query_count']==len(q['passages']) and r['pair_comparisons']==(r['query_count']*20 if r['method']=='quota_rerank' else 0)
        relevant = {d for d,v in case['grades'].items() if v>=2}
        assert r['labeled_relevant_recall']==(len(relevant&ids)/len(relevant) if relevant else None)
        assert r['known_conflicting_retained']==[d for d in case['hard_negatives'] if d in ids]
        if r['variant']=='original_messages' and r['method']=='quota_rerank':
            control = next(s for s in previous if s['case_id']==r['case_id'] and s['method']=='quota_rerank' and s['n']==20 and s['k']==5)
            restored = {k:v for k,v in r.items() if k not in ('variant','query_count','reference_complete','reference_coverage')}
            restored.update(complete=r['reference_complete'],coverage=r['reference_coverage'])
            assert restored==control
    for variant in VARIANTS:
        for config in CONFIGS:
            rows = [r for r in metrics if r['variant']==variant and r['method']==config['method']]
            summaries.append({'variant':variant,**config,'metrics':{'cases':len(rows),'positive_cases':sum(bool(r['total']) for r in rows),
                'reference_complete_cases':sum(r['reference_complete'] for r in rows),'covered':sum(r['covered'] for r in rows),'total':sum(r['total'] for r in rows),
                'secondary_covered':sum(r['secondary_covered'] for r in rows),'secondary_total':sum(r['secondary_total'] for r in rows),
                'mean_documents':statistics.mean(r['returned'] for r in rows),'mean_characters':statistics.mean(r['characters'] for r in rows),
                'mean_queries':statistics.mean(r['query_count'] for r in rows),'mean_pair_comparisons':statistics.mean(r['pair_comparisons'] for r in rows)}})
    assert read(HERE/'summary.json')['comparisons']==summaries and read(HERE/'summary.json')['no_parameter_retuning'] is True
    if (HERE/'known-conflicts.json').exists():
        assert read(HERE/'known-conflicts.json')==[{'case_id':r['case_id'],'variant':r['variant'],'known_conflicting_retained':r['known_conflicting_retained']}
            for r in metrics if r['method']=='quota_rerank' and r['known_conflicting_retained']]
    diagnostics = read(HERE/'topic-diagnostics.json')
    assert len(diagnostics)==258 and len({(r['topic_id'],r['variant']) for r in diagnostics})==258
    for d in diagnostics:
        topic = next(t for t in by_case[d['case_id']]['topics'] if t['topic_id']==d['topic_id'])
        assert d['work']==topic['work'] and d['employee_quote']==topic['employee_quote'] and d['secondary']==topic['secondary']
        assert len(d['outcomes'])==2
        for outcome in d['outcomes']:
            r = next(r for r in metrics if r['case_id']==d['case_id'] and r['variant']==d['variant'] and r['method']==outcome['method'])
            assert outcome['retained']==(d['topic_id'] not in r['missing'])
            assert outcome['matched']==[s for s in r['selected'] if s['id'] in {s['id'] for s in topic['support']}]
    plan = read(HERE/'benchmark-plan.json')
    assert plan['input_manifest_sha256']==sha(HERE/'input-manifest.json')
    expected_tasks = {r['request_id']:r for r in plan['requests']}
    for t in plan['requests']:
        dense = {**t,'request_id':t['request_id']+'-dense','config':CONFIGS[0]}; expected_tasks[dense['request_id']] = dense
    timings = lines(HERE/'benchmark-results.jsonl')
    assert len(timings)==len(expected_tasks)==24 and {r['request_id'] for r in timings}==set(expected_tasks)
    for t in timings:
        q = queries[(t['case_id'],t['variant'])]
        check_task(t,expected_tasks[t['request_id']],q)
        for search in t['database_searches']:
            check_native(q,search)
        assert t['query_count']==len(q['passages']) and t['database_seconds']==sum(s['seconds'] for s in t['database_searches'])
        assert t['total_seconds']>=t['database_seconds']+t['handoff_seconds']+t['merge_seconds']>0
        scores = {}
        if t['config']['method']=='quota_rerank':
            request = read(HERE/'benchmark-requests'/f'{t["request_id"]}.json')
            assert all(request[k]==t[k] for k in ('request_id','case_id','variant','repeat','config'))
            response = read(HERE/'benchmark-responses'/f'{t["request_id"]}.json'); check_task(t,expected_tasks[t['request_id']],q,response)
            wanted = {(p,r['id']) for p,pool in enumerate(q['pools'],1) for r in pool[:20]}
            assert {(r['passage'],r['id']) for r in response['pairs']}==wanted=={(r['passage'],r['id']) for r in request['pairs']}
            assert len(response['pairs'])==t['pair_comparisons']==len(wanted)
            assert 0<t['tokenize_seconds']==response['tokenize_seconds']<t['worker_seconds']==response['worker_seconds']<=t['handoff_seconds']
            assert t['file_transport_overhead_seconds']==max(0,t['handoff_seconds']-t['worker_seconds'])
            scores = {(r['passage'],r['id']):r['logit'] for r in response['pairs']}
            for r in response['pairs']:
                quality = pairs[prior.pair_key(q['passages'][r['passage']-1],by_doc[r['id']])]
                assert r['logit']==quality['logit']
        else:
            assert t['pair_comparisons']==t['worker_seconds']==t['tokenize_seconds']==t['handoff_seconds']==0
        selected = expected_selection(q,scores,t['config'])
        assert t['selected_ids']==[r['id'] for r in selected]
        assert t['characters']==sum(len(by_doc[d]['text']) for d in t['selected_ids'])
    ts = read(HERE/'timing-summary.json')
    assert len(ts)==12 and len({(s['case_id'],s['variant'],s['config']['method']) for s in ts})==12
    for s in ts:
        rows = [t for t in timings if t['case_id']==s['case_id'] and t['variant']==s['variant'] and t['config']==s['config']]
        assert len(rows)==2 and s['samples_seconds']==[r['total_seconds'] for r in rows]
        for suffix in ('total_seconds','database_seconds','worker_seconds','tokenize_seconds','file_transport_overhead_seconds'):
            assert s['median_'+suffix]==statistics.median(r[suffix] for r in rows)
        assert s['query_counts']==[r['query_count'] for r in rows] and s['pair_counts']==[r['pair_comparisons'] for r in rows]
        assert s['returned_counts']==[len(r['selected_ids']) for r in rows]
    assert read(HERE/'gpu-complete.json')['elapsed_seconds']<2700 and read(HERE/'gpu-complete.json')['bench_requests']==12
    state = read(HERE/'service-state-native.json')
    assert state['process_stopped'] is True and state['listening_ports']==[]
    states = [line.split(' ',1) for line in (HERE/'service-state-containers.txt').read_text(encoding='utf-8-sig').splitlines()]
    assert [name for name,_ in states]==['/caliburn-ocs-rerank-boundaries','/caliburn-ocs-eval-embedder-1']
    assert all(json.loads(value)['Status']=='exited' and json.loads(value)['Running'] is False for _,value in states)
    assert json.loads(states[0][1])['ExitCode']==0
    for entry in read(HERE/'previous-seals.json'):
        assert sha(HERE.parent/entry['experiment']/'artifact-hashes.json')==entry['manifest_sha256']
    return {'passed':True,'scope':'Observed synthetic query-boundary sensitivity only; not semantic JD task equivalence/completeness',
       'case_variants':66,'quality_native_queries':256,'metric_rows':132,'topic_variant_traces':258,
       'new_embeddings':len(new),'supplemented_pairs':len(generated),'benchmark_samples':len(timings),
       'benchmark_native_queries':sum(len(t['database_searches']) for t in timings)}

def seal():
    paths = [p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='artifact-hashes.json']
    dump('artifact-hashes.json',{p.relative_to(HERE).as_posix():sha(p) for p in sorted(paths)})

if __name__=='__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--seal',action='store_true'); parser.add_argument('--check-seal',action='store_true')
    args = parser.parse_args()
    if args.check_seal:
        hashes = read(HERE/'artifact-hashes.json')
        for name,digest in hashes.items():
            assert sha(HERE/name)==digest,name
        print(f'{len(hashes)} sealed hashes verified')
    else:
        print(json.dumps(check(),indent=2))
        if args.seal:
            seal()
