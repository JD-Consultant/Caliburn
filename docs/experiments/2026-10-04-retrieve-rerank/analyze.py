"""Evaluate saved pools; select on development before evaluating new holdout."""
import itertools
import json
import statistics
from pathlib import Path

from evaluate import coverage, pipeline, select
from prepare import HERE, ROOT, dump, sha

N_VALUES = (20,50,100,200)
COSINES = (None,0.5,0.6,0.65,0.7)
K_VALUES = (5,10,20,50)
CROSS_SCORES = (None,0.1,0.3,0.5,0.7)


def main():
    prepared = json.loads((HERE/'prepared.json').read_text(encoding='utf-8'))
    original = json.loads((HERE/'frozen.json').read_text(encoding='utf-8'))
    for name,expected_sha in original['sources'].items():
        assert sha(ROOT/name) == expected_sha
    execution = json.loads((HERE/'execution-manifest.json').read_text(encoding='utf-8'))
    for name,expected_sha in execution['sources'].items():
        assert sha(HERE/name) == expected_sha
    assert prepared['frozen_sha256'] == sha(HERE/'frozen.json')
    effective = json.loads((HERE/'frozen-v4.json').read_text(encoding='utf-8'))
    for name,expected_sha in effective['sources'].items():
        assert sha(HERE/name) == expected_sha
    cases = {c['case_id']:c for c in json.loads((HERE/effective['effective_cases']).read_text(encoding='utf-8'))}
    pairs = {(r['case_id'],r['arm']):r for r in (json.loads(line) for line in (HERE/'rerank-pairs.jsonl').open(encoding='utf-8'))}
    expected = {(q['case_id'],q['arm']) for q in prepared['queries']}
    assert set(pairs) == expected and len(pairs) == 32
    assert all(len(r['pairs']) == 200 for r in pairs.values())
    corpus = {r['id']:r for r in prepared['corpus']}
    corpus_chars = sum(len(r['text']) for r in corpus.values())
    broad_rows, final_rows = [],[]
    query_by_key = {(q['case_id'],q['arm']):q for q in prepared['queries']}

    def row(q, selected):
        case = cases[q['case_id']]
        ids = [r['id'] for r in selected]
        required = {k for k,v in case['grades'].items() if v >= 2}
        return {'case_id':q['case_id'],'arm':q['arm'],'split':case['split'],
                'kind':case['kind'],**coverage(ids,case['topics']),
                'returned':len(ids),'characters':sum(len(corpus[k]['text']) for k in ids),
                'character_retention_ratio':sum(len(corpus[k]['text']) for k in ids)/corpus_chars,
                'embedding_tokens':sum(corpus[k]['embedding_tokens'] for k in ids),
                'labeled_relevant_recall':len(required&set(ids))/len(required) if required else None,
                'primary_retained':all(k in ids for k,v in case['grades'].items() if v == 3) if required else None,
                'known_conflicting_retained':[k for k in case['hard_negatives'] if k in ids],
                'selected_ids':ids}

    for q in prepared['queries']:
        p = pairs[(q['case_id'],q['arm'])]['pairs']
        for n,cosine in itertools.product(N_VALUES,COSINES):
            broad = select(q['ranking'],n,cosine)
            broad_rows.append({'n':n,'cosine':cosine,**row(q,broad)})
            for k in K_VALUES:
                final_rows.append({'n':n,'cosine':cosine,'k':k,'cross':None,'method':'dense_only',
                                   **row(q,broad[:k])})
                for cross in CROSS_SCORES:
                    result = pipeline(q['ranking'],p,n,cosine,k,cross)
                    final_rows.append({'n':n,'cosine':cosine,'k':k,'cross':cross,'method':'rerank',
                                       **row(q,result)})

    def aggregate(rows):
        positive = [r for r in rows if r['total']]
        secondary = [r for r in rows if r['secondary_total']]
        return {'queries':len(rows),'positive_queries':len(positive),
                'complete_queries':sum(r['complete'] for r in positive),
                'topic_coverage_macro':statistics.mean(r['coverage'] for r in positive),
                'secondary_covered':sum(r['secondary_covered'] for r in secondary),
                'secondary_total':sum(r['secondary_total'] for r in secondary),
                'mean_documents':statistics.mean(r['returned'] for r in rows),
                'mean_characters':statistics.mean(r['characters'] for r in rows),
                'mean_character_retention_ratio':statistics.mean(r['character_retention_ratio'] for r in rows),
                'labeled_relevant_recall_macro':statistics.mean(r['labeled_relevant_recall'] for r in positive)}

    settings = list(itertools.product(('dense_only','rerank'),N_VALUES,COSINES,K_VALUES,CROSS_SCORES))
    summaries = []
    for method,n,cosine,k,cross in settings:
        if method == 'dense_only' and cross is not None:
            continue
        group = [r for r in final_rows if (r['method'],r['n'],r['cosine'],r['k'],r['cross']) == (method,n,cosine,k,cross)]
        dev = [r for r in group if r['split'] != 'holdout']
        summaries.append({'method':method,'n':n,'cosine':cosine,'k':k,'cross':cross,'development':aggregate(dev)})
    # Labels/family overlap means this is engineering evidence, not statistical generalization.
    chosen = {}
    for method in ('dense_only','rerank'):
        passing = [s for s in summaries if s['method'] == method and
                   s['development']['complete_queries'] == s['development']['positive_queries']]
        chosen[method] = min(passing,key=lambda s:(s['development']['mean_characters'],s['n'],
                                s['development']['mean_documents'],s['k'],str(s['cosine']),str(s['cross']))) if passing else None
    dump(HERE/'selection-development.json',{'status':'experimental only; no production threshold',
             'criteria':'complete coverage of engineering-labeled source-supported topics in development; then fewer mean characters, smaller N',
             'chosen':chosen,'inputs_sha256':{p.name:sha(p) for p in (HERE/'frozen-v4.json',HERE/'execution-manifest.json',HERE/'prepared.json',HERE/'rerank-pairs.jsonl',Path(__file__))}})
    # Only now expose new holdout outcomes. Do not retune after this point.
    comparisons = []
    for method,setting in chosen.items():
        if setting is None:
            continue
        selected = [r for r in final_rows if all(r[k] == setting[k] for k in ('method','n','cosine','k','cross'))]
        comparisons.append({**setting,'holdout':aggregate([r for r in selected if r['split'] == 'holdout']),
                            'all':aggregate(selected),'cases':selected})
    dump(HERE/'comparison.json',comparisons)
    dump(HERE/'parameter-summary-development.json',summaries)
    for name,rows in [('broad-metrics.jsonl',broad_rows),('final-metrics.jsonl',final_rows)]:
        with (HERE/name).open('w',encoding='utf-8') as stream:
            for r in rows:
                stream.write(json.dumps(r,ensure_ascii=False)+'\n')
    timings = [json.loads(line) for line in (HERE/'timings.jsonl').open(encoding='utf-8')]
    time_summary = []
    for query,n in itertools.product([('E01','raw_employee'),('E04','B2')],(20,50,100,200,805)):
        values = [r['rerank_seconds'] for r in timings if (r['case_id'],r['arm'],r['n']) == (*query,n)]
        assert len(values) == 2
        q = query_by_key[query]
        time_summary.append({'case_id':query[0],'arm':query[1],'n':n,'samples':values,
                             'rerank_median_seconds':statistics.median(values),
                             'dense_exact_median_seconds':statistics.median(q['dense_exact_seconds'])})
    dump(HERE/'timing-summary.json',time_summary)
    print(json.dumps({'chosen':chosen,'holdout':[{k:v for k,v in r.items() if k != 'cases'} for r in comparisons]},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
