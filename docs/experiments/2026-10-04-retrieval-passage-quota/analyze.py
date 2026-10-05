"""Choose on observed development; held outcomes never enter the selector."""
from common import *

def main():
    phase = sys.argv[1]
    prepared = read(HERE/f'prepared-{phase}.json')
    corpus = prepared['corpus']
    cases = {c['case_id']:c for c in read(HERE/('development-cases.json' if phase=='development' else 'holdout-cases-2026-10-04-reviewed.json'))}
    scores = load_pairs(phase)
    if phase=='development':
        configurations = configs()
    else:
        freeze = read(HERE/'selection-frozen.json')
        assert sha(HERE/'selection-development.json')==freeze['selection_sha256']
        configurations = [{k:s[k] for k in ('method','n','k')} for s in read(HERE/'selection-development.json')['chosen'].values() if s]
    rows = []
    for q in prepared['queries']:
        pairs = score_map(q,corpus,scores)
        for config in configurations:
            rows.append(metric(q,cases[q['case_id']],corpus,select(q,pairs,config),config))
    summaries = [{**config,'metrics':aggregate([r for r in rows if all(r[k]==v for k,v in config.items())])} for config in configurations]
    dump_lines(f'metrics-{phase}.jsonl',rows)
    dump(f'summary-{phase}.json',summaries)
    if phase=='development':
        chosen = {}
        for method in ('global_dense','global_rerank','quota_dense','quota_rerank'):
            passing = [s for s in summaries if s['method']==method and s['metrics']['complete_cases']==12 and s['metrics']['covered']==64]
            chosen[method] = min(passing,key=lambda s:(s['metrics']['mean_characters'],s['metrics']['mean_pair_comparisons'],s['n'],s['k'])) if passing else None
        dump('selection-development.json',{'criteria':'12/12 known positives and 64/64 supported topics, then mean characters, pair comparisons, N, K',
                                         'chosen':chosen,'holdout_not_used':True})
        dump('selection-frozen.json',{'selection_sha256':sha(HERE/'selection-development.json'),
              'sources':{n:sha(HERE/n) for n in ('execution-development.json','metrics-development.jsonl','summary-development.json','supplemental-development-pairs.jsonl','analyze.py')},
              'before_holdout_embeddings':True})
        print(json.dumps(chosen,ensure_ascii=False,indent=2))
    else:
        print(json.dumps(summaries,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
