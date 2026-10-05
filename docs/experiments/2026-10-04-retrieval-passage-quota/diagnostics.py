"""Trace every labeled topic without changing parameters after reveal."""
from common import *

def main():
    corpus = {d['id']:d for d in documents()}
    pairs = load_pairs('holdout')
    traces = []
    for phase,case_name in [('development','development-cases.json'),('holdout','holdout-cases-2026-10-04-reviewed.json')]:
        cases = read(HERE/case_name)
        queries = {q['case_id']:q for q in read(HERE/f'prepared-{phase}.json')['queries']}
        metrics = lines(HERE/f'metrics-{phase}.jsonl')
        chosen = read(HERE/'selection-development.json')['chosen']
        for c in cases:
            q = queries[c['case_id']]
            for topic in c['topics']:
                supports = []
                for ident in dict.fromkeys(s['id'] for s in topic['support']):
                    positions = []
                    for p,pool in enumerate(q['pools'],1):
                        rank_,row = next((i,r) for i,r in enumerate(pool,1) if r['id']==ident)
                        pair = pairs.get(pair_key(q['passages'][p-1],corpus[ident]))
                        positions.append({'passage':p,'dense_rank':rank_,'cosine':row['score'],
                            'logit':pair['logit'] if pair else None,'score_available':pair is not None})
                    supports.append({'id':ident,'title':corpus[ident]['title'],
                        'global_dense_rank':next(i for i,r in enumerate(q['global_pool'],1) if r['id']==ident),'passages':positions})
                outcomes = []
                for method,config in chosen.items():
                    if config:
                        row = next(r for r in metrics if r['case_id']==c['case_id'] and all(r[k]==config[k] for k in ('method','n','k')))
                        matched = [s for s in row['selected'] if s['id'] in {s['id'] for s in supports}]
                        outcomes.append({'method':method,'retained':topic['topic_id'] not in row['missing'],'matched':matched})
                traces.append({'phase':phase,'case_id':c['case_id'],'topic_id':topic['topic_id'],'work':topic['work'],
                    'secondary':topic['secondary'],'employee_quote':topic['employee_quote'],'support':supports,'outcomes':outcomes})
    dump('topic-diagnostics.json',traces)
    timings = lines(HERE/'benchmark-results.jsonl')
    groups = []
    for case,method in dict.fromkeys((t['case_id'],t['config']['method']) for t in timings):
        rows = [t for t in timings if t['case_id']==case and t['config']['method']==method]
        assert len(rows)==2
        groups.append({'case_id':case,'method':method,'config':rows[0]['config'],'samples_seconds':[r['total_seconds'] for r in rows],
            'median_total_seconds':statistics.median(r['total_seconds'] for r in rows),
            'median_database_seconds':statistics.median(r['database_seconds'] for r in rows),
            'median_tokenize_seconds':statistics.median(r['tokenize_seconds'] for r in rows),
            'median_worker_seconds':statistics.median(r['worker_seconds'] for r in rows),
            'median_file_transport_overhead_seconds':statistics.median(r['file_transport_overhead_seconds'] for r in rows),
            'pair_counts':[r['pairs'] for r in rows],'returned_counts':[len(r['selected_ids']) for r in rows]})
    dump('timing-summary.json',groups)
    print(json.dumps(groups,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
