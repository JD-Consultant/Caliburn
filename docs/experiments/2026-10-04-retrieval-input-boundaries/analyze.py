"""Sensitivity only: no new parameter selection and no JD completeness verdict."""
import statistics
from support import *

def aggregate(rows):
    return {'cases':len(rows),'positive_cases':sum(bool(r['total']) for r in rows),
        'reference_complete_cases':sum(r['reference_complete'] for r in rows),'covered':sum(r['covered'] for r in rows),
        'total':sum(r['total'] for r in rows),'secondary_covered':sum(r['secondary_covered'] for r in rows),
        'secondary_total':sum(r['secondary_total'] for r in rows),'mean_documents':statistics.mean(r['returned'] for r in rows),
        'mean_characters':statistics.mean(r['characters'] for r in rows),'mean_queries':statistics.mean(r['query_count'] for r in rows),
        'mean_pair_comparisons':statistics.mean(r['pair_comparisons'] for r in rows)}

def main():
    prepared = read(HERE/'prepared.json'); corpus = prepared['corpus']
    cases = {c['case_id']:c for c in read(HERE/'cases-observed.json')}
    scores = load_scores(); rows = []
    previous = lines(QUOTA/'metrics-development.jsonl')+lines(QUOTA/'metrics-holdout.jsonl')
    for q in prepared['queries']:
        pairs = prior.score_map(q,corpus,scores)
        for config in CONFIGS:
            selected = per_passage(q['pools'],pairs,20,5,config['method'].endswith('rerank'))
            r = prior.metric(q,cases[q['case_id']],corpus,selected,config)
            if q['variant']=='original_messages' and config['method']=='quota_rerank':
                control = next(s for s in previous if s['case_id']==q['case_id'] and s['method']=='quota_rerank' and s['n']==20 and s['k']==5)
                assert r==control,'original control drift'
            r.update(variant=q['variant'],query_count=len(q['passages']))
            r['reference_complete'] = r.pop('complete'); r['reference_coverage'] = r.pop('coverage')
            rows.append(r)
    dump_lines('metrics.jsonl',rows)
    summaries = [{'variant':v,'method':config['method'],'n':20,'k':5,
                 'metrics':aggregate([r for r in rows if r['variant']==v and r['method']==config['method']])}
                 for v in VARIANTS for config in CONFIGS]
    dump('summary.json',{'status':'observed synthetic sensitivity probe; no adoption or JD completeness decision',
                        'no_parameter_retuning':True,'comparisons':summaries})
    traces = []
    for q in prepared['queries']:
        case = cases[q['case_id']]
        for topic in case['topics']:
            supports = {s['id'] for s in topic['support']}
            trace = {'case_id':q['case_id'],'variant':q['variant'],'topic_id':topic['topic_id'],'work':topic['work'],
                     'secondary':topic['secondary'],'employee_quote':topic['employee_quote'],'outcomes':[]}
            for config in CONFIGS:
                row = next(r for r in rows if r['case_id']==q['case_id'] and r['variant']==q['variant'] and r['method']==config['method'])
                trace['outcomes'].append({'method':config['method'],'retained':topic['topic_id'] not in row['missing'],
                    'matched':[s for s in row['selected'] if s['id'] in supports]})
            traces.append(trace)
    dump('topic-diagnostics.json',traces)
    print(json.dumps(summaries,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
