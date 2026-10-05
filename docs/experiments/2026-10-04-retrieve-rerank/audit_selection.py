"""Audit saved summaries from already verified per-query results and frozen labels."""
import itertools
import statistics
from collections import defaultdict

FIELDS = ('method', 'n', 'cosine', 'k', 'cross')


def key(row):
    return tuple(row[field] for field in FIELDS)


def aggregate(rows):
    positive = [r for r in rows if r['total']]
    assert positive
    return {'queries': len(rows), 'positive_queries': len(positive),
            'complete_queries': sum(r['complete'] for r in positive),
            'topic_coverage_macro': statistics.mean(r['coverage'] for r in positive),
            'secondary_covered': sum(r['secondary_covered'] for r in rows),
            'secondary_total': sum(r['secondary_total'] for r in rows),
            'mean_documents': statistics.mean(r['returned'] for r in rows),
            'mean_characters': statistics.mean(r['characters'] for r in rows),
            'mean_character_retention_ratio': statistics.mean(r['character_retention_ratio'] for r in rows),
            'labeled_relevant_recall_macro': statistics.mean(r['labeled_relevant_recall'] for r in positive)}


def check_selection(rows, cases, corpus_chars, saved_summaries, chosen, comparisons):
    grouped = defaultdict(list)
    for row in rows:
        case = cases[row['case_id']]
        assert row['split'] == case['split'] and row['kind'] == case['kind']
        assert row['total'] == len(case['topics'])
        assert row['secondary_total'] == sum(t['secondary'] for t in case['topics'])
        assert row['secondary_covered'] == sum(t['secondary'] and t['topic_id'] not in row['missing'] for t in case['topics'])
        assert row['character_retention_ratio'] == row['characters'] / corpus_chars
        required = {ident for ident, grade in case['grades'].items() if grade >= 2}
        assert row['labeled_relevant_recall'] == (len(required & set(row['selected_ids'])) / len(required) if required else None)
        grouped[key(row)].append(row)
    expected_keys = {(method, n, cosine, k, cross) for method, n, cosine, k, cross in
                     itertools.product(('dense_only', 'rerank'), (20, 50, 100, 200), (None, .5, .6, .65, .7), (5, 10, 20, 50), (None, .1, .3, .5, .7))
                     if method != 'dense_only' or cross is None}
    assert set(grouped) == expected_keys
    assert len(saved_summaries) == len(expected_keys)
    assert {key(s) for s in saved_summaries} == expected_keys
    recomputed = []
    for saved in saved_summaries:
        dev = [r for r in grouped[key(saved)] if cases[r['case_id']]['split'] != 'holdout']
        summary = {field: saved[field] for field in FIELDS}
        summary['development'] = aggregate(dev)
        assert summary == saved, f'development summary differs: {key(saved)}'
        recomputed.append(summary)
    assert set(chosen) == {'dense_only', 'rerank'}
    for method, selected in chosen.items():
        passing = [s for s in recomputed if s['method'] == method and s['development']['complete_queries'] == s['development']['positive_queries']]
        expected = min(passing, key=lambda s: (s['development']['mean_characters'], s['n'], s['development']['mean_documents'], s['k'], str(s['cosine']), str(s['cross']))) if passing else None
        assert selected == expected, f'selection differs: {method}'
    expected_comparisons = {key(s) for s in chosen.values() if s is not None}
    assert len(comparisons) == len(expected_comparisons)
    assert {key(c) for c in comparisons} == expected_comparisons
    for compared in comparisons:
        selected = grouped[key(compared)]
        assert compared['cases'] == selected
        for split in ('development', 'holdout', 'all'):
            group = [r for r in selected if split == 'all' or (cases[r['case_id']]['split'] == 'holdout') == (split == 'holdout')]
            assert compared[split] == aggregate(group), f'comparison summary differs: {split}'
