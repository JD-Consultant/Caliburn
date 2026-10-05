"""Describe saved failures without choosing parameters on observed holdout."""
import hashlib
import json
import statistics
from pathlib import Path

from evaluate import select

HERE = Path(__file__).resolve().parent


def read(folder, name):
    return json.loads((folder / name).read_text(encoding='utf-8'))


def lines(folder, name):
    return [json.loads(line) for line in (folder / name).read_text(encoding='utf-8').splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases = {c['case_id']: c for c in read(HERE, 'cases-v4.json')}
    child = HERE / 'passage-pool'
    prepared = read(child, 'prepared.json')
    queries = {q['case_id']: q for q in prepared['queries']}
    pairs = {r['case_id']: r['pairs'] for r in lines(child, 'rerank-pairs.jsonl')}
    setting = read(child, 'selection-development.json')['chosen']['rerank']
    selected = read(child, 'comparison.json')[0]['cases']
    trace = []
    for row in selected:
        case_id = row['case_id']
        q = queries[case_id]
        broad = select(q['ranking'], setting['n'], setting['cosine'])
        broad_ids = {r['id'] for r in broad}
        pair_by_id = {r['id']: r for r in pairs[case_id]}
        unfiltered_order = sorted(pairs[case_id], key=lambda r: (-r['score'], r['id']))
        final_order = sorted((r for r in pairs[case_id] if r['id'] in broad_ids), key=lambda r: (-r['score'], r['id']))
        for topic in cases[case_id]['topics']:
            refs = []
            for support in topic['support']:
                ident = support['id']
                rank, score = next((i, r['score']) for i, r in enumerate(q['ranking'], 1) if r['id'] == ident)
                pair = pair_by_id.get(ident)
                refs.append({'id': ident, 'max_cosine_rank': rank, 'max_cosine': score,
                             'passes_candidate_depth': rank <= setting['n'],
                             'passes_cosine': score >= setting['cosine'],
                             'broad_retained': ident in broad_ids,
                             'rerank_logit': pair['logit'] if pair else None,
                             'rerank_sigmoid': pair['score'] if pair else None,
                             'rerank_rank_in_saved_top200_without_cosine': next((i for i, p in enumerate(unfiltered_order, 1) if p['id'] == ident), None),
                             'rerank_rank_after_cosine': next((i for i, p in enumerate(final_order, 1) if p['id'] == ident), None),
                             'final_retained': ident in row['selected_ids']})
            trace.append({'case_id': case_id, 'split': row['split'], 'topic_id': topic['topic_id'],
                          'work': topic['work'], 'secondary': topic['secondary'], 'support': refs,
                          'covered': topic['topic_id'] not in row['missing']})
    assert len(trace) == 64
    chosen_broad = [r for r in lines(child, 'broad-metrics.jsonl') if (r['n'], r['cosine']) == (setting['n'], setting['cosine'])]
    assert len(chosen_broad) == 18
    controlled = []
    for folder, arm in ((HERE, 'raw_employee'), (child, 'raw_segments')):
        rows = lines(folder, 'final-metrics.jsonl')
        for method in ('dense_only', 'rerank'):
            # Same parameters, raw input and development cases in both representations.
            group = [r for r in rows if r['arm'] == arm and r['split'] != 'holdout'
                     and (r['method'], r['n'], r['cosine'], r['k'], r['cross']) == (method, 200, None, 50, None)]
            positives = [r for r in group if r['total']]
            assert len(positives) == 10
            controlled.append({'representation': arm, 'method': method, 'n': 200, 'cosine': None,
                               'k': 50, 'cross': None, 'development_cases': len(group),
                               'positive_cases': len(positives), 'complete_cases': sum(r['complete'] for r in positives),
                               'missing': {r['case_id']: r['missing'] for r in positives if r['missing']},
                               'mean_characters_all_development': statistics.mean(r['characters'] for r in group)})
    timing = read(child, 'timing-summary.json')
    t200 = next(r['rerank_median_seconds'] for r in timing if r['n'] == 200)
    t805 = next(r['rerank_median_seconds'] for r in timing if r['n'] == 805)
    value = {'scope': 'post-selection descriptive failure diagnosis; no held-out retuning or adopted threshold',
             'sources_sha256': {str(p.relative_to(HERE)): sha(p) for p in (HERE / 'cases-v4.json', HERE / 'final-metrics.jsonl', child / 'prepared.json', child / 'rerank-pairs.jsonl', child / 'comparison.json', child / 'final-metrics.jsonl', child / 'timing-summary.json', Path(__file__))},
             'chosen_development_setting': {k: setting[k] for k in ('method', 'n', 'cosine', 'k', 'cross')},
             'controlled_development_comparison': controlled,
             'broad_topic_counts': {'covered': sum(r['covered'] for r in chosen_broad), 'total': sum(r['total'] for r in chosen_broad)},
             'final_topic_counts': {'covered': sum(r['covered'] for r in selected), 'total': sum(r['total'] for r in selected)},
             'broad_documents': {r['case_id']: r['returned'] for r in chosen_broad},
             'failure_trace': [r for r in trace if not r['covered']], 'all_topic_traces': trace,
             'warm_no_cutoff_benchmark': {'candidate200_seconds': t200, 'all805_seconds': t805,
                                        'model_loop_reduction': 1 - t200 / t805, 'ratio': t805 / t200,
                                        'scope': 'E01, 3 passages/document, 2 repeats, pretokenized, no cosine cutoff; not chosen-setting or end-to-end latency'}}
    (HERE / 'result-diagnostics.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in value.items() if k not in ('all_topic_traces', 'sources_sha256')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
