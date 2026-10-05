"""Independent reconstruction of stored point scores and every candidate group."""
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXP = HERE.parents[1]
MEM = EXP / '2026-10-04-memory-layer-retrieval/run-01'
PUBLIC = EXP / '2026-10-04-public-chunk-retrieval/run-01'
PRIOR = EXP / '2026-10-05-memory-public-unit-retrieval/run-01'
DEPTH = EXP / '2026-10-05-initial-retrieval-depth/run-01'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main(output):
    for rel, expected in read(HERE / 'input-manifest.json')['inputs'].items():
        path = ROOT / rel
        assert path.stat().st_size == expected['bytes'] and sha(path) == expected['sha256'], rel
    sealed = 0
    for record in read(HERE / 'prior-seals-before.json'):
        directory = ROOT / record['directory']
        assert sha(directory / 'artifact-hashes.json') == record['manifest_sha256']
        for rel, expected in read(directory / 'artifact-hashes.json')['files'].items():
            assert sha(directory / rel) == expected['sha256'] and (directory / rel).stat().st_size == expected['bytes']
            sealed += 1
    qrows = read(HERE / 'queries.json')
    qsource = {q['query_id']: q for q in read(MEM / 'queries.json')}
    vsource = {v['query_id']: v for v in read(MEM / 'query-vectors.json')}
    groups = read(HERE / 'method-groups.json')
    oldgroups = read(MEM / 'method-groups.json')
    methods = {'O': 'O-W', 'B1-W': 'B1-W', 'B1-S': 'B1-S', 'B2-S': 'B2-S'}
    assert len(qrows) == len({q['query_id'] for q in qrows}) == 63 and len(groups) == 32
    for g in groups:
        expected = next(o for o in oldgroups if o['case_id'] == g['case_id'] and o['method'] == methods[g['variant']])
        assert g['query_ids'] == expected['query_ids']
    for q in qrows:
        old = qsource[q['query_id']]
        assert q['text'] == old['text']
        assert hashlib.sha256(q['text'].encode('utf-8')).hexdigest() == q['text_sha256'] == vsource[q['query_id']]['text_sha256']
    vectors = {}
    for path in sorted((PUBLIC / 'vector-batches').glob('*.npz')):
        with np.load(path, allow_pickle=False) as z:
            vectors.update({str(h): v for h, v in zip(z['hashes'], z['dense'], strict=True)})
    chunks = read(PUBLIC / 'chunks.json')
    rows = {rep: [c for c in chunks if c['representation'] == rep] for rep in ('document', 'task')}
    mats = {rep: np.array([vectors[hashlib.sha256(c['text'].encode('utf-8')).hexdigest()] for c in cs], dtype=np.float64)
            for rep, cs in rows.items()}
    for rep, m in mats.items():
        assert m.shape == (len(rows[rep]), 1024) and np.isfinite(m).all()
        m /= np.sqrt(np.sum(m * m, axis=1))[:, None]
    ranked = {(r['query_id'], r['representation']): r['parents'] for r in read(HERE / 'all-rankings.json')}
    ranks, point_count, max_error = {}, 0, 0.
    assert len(ranked) == 126
    with np.load(HERE / 'chunk-scores.npz', allow_pickle=False) as z:
        assert len(z.files) == 126
        for i, q in enumerate(qrows):
            v = np.array(vsource[q['query_id']]['dense'], dtype=np.float64)
            assert v.shape == (1024,) and np.isfinite(v).all() and np.linalg.norm(v) > 0
            v /= np.sqrt(np.sum(v * v))
            for rep in ('document', 'task'):
                saved = z[f'q{i}_{rep}']
                # Different rowwise dot path to avoid trusting the scoring implementation.
                independent = np.einsum('ij,j->i', mats[rep], v)
                error = float(np.max(np.abs(saved - independent)))
                assert error < 1e-12 and np.isfinite(saved).all()
                max_error = max(max_error, error)
                point_count += len(saved)
                parent_hits = {}
                for c, s in zip(rows[rep], saved, strict=True):
                    parent_hits.setdefault(c['parent_id'], []).append((float(s), c['chunk_id']))
                order = sorted(parent_hits, key=lambda p: (-max(s for s, _ in parent_hits[p]), p))
                parents = ranked[(q['query_id'], rep)]
                assert len(order) == len(parents) == 805 and order == [p['id'] for p in parents]
                for p in parents:
                    hits = sorted(parent_hits[p['id']], key=lambda x: (-x[0], x[1]))
                    assert p['score'] == p['max_score'] == hits[0][0]
                    assert p['available_chunks'] == len(hits)
                    assert [(h['score'], h['chunk_id']) for h in p['top_chunks']] == hits[:3]
                ranks[(q['query_id'], rep)] = order
    prior = {(r['query_id'], r['representation']): r['parents'] for r in read(PRIOR / 'all-rankings.json')}
    oldd = {r['query_id']: r['ranking'] for r in read(MEM / 'all-rankings.json')}
    controls = read(HERE / 'control-checks.json')
    assert len(controls) == 83
    for c in controls:
        key = (c['query_id'], c['representation'])
        expected = prior[key] if c['control'] == 'prior_dual_route' else oldd[c['query_id']]
        assert ranks[key] == [r['id'] for r in expected]
        error = max(abs(a['score']-b['score']) for a, b in zip(ranked[key], expected, strict=True))
        assert error == c['max_score_error'] and error < 1e-12
    targets = read(DEPTH / 'targets.json')
    cases = {c['case_id']: c for c in read(MEM / 'cases.json')}
    results = read(HERE / 'results.json')
    assert len(results) == 96
    for r in results:
        group = next(g for g in groups if g['case_id'] == r['case_id'] and g['variant'] == r['variant'])
        assert r['query_ids'] == group['query_ids'] and r['depth_each_route'] in (20, 40, 80)
        collected, pairs = set(), 0
        for qid, pool in zip(r['query_ids'], r['query_pools'], strict=True):
            assert pool['query_id'] == qid
            d = ranks[(qid, 'document')][:r['depth_each_route']]
            t = ranks[(qid, 'task')][:r['depth_each_route']]
            combined = set(d) | set(t)
            assert pool['D_ids'] == d and pool['T_ids'] == t and pool['union_ids'] == sorted(combined)
            collected.update(combined); pairs += len(combined)
        assert r['employee_candidate_ids'] == sorted(collected)
        assert r['employee_unique_parents'] == len(collected) and r['query_parent_pair_workload'] == pairs
        for label in ('known', 'clear'):
            tt = [t for t in targets if t['case_id'] == r['case_id'] and (label == 'known' or not t['sensitivity_excluded'])]
            ids = [t['id'] for t in tt]; kept = [ident for ident in ids if ident in collected]
            assert r[label + '_targets'] == {'known_ids': ids, 'retained_ids': kept,
                'missing_ids': [ident for ident in ids if ident not in collected], 'coverage': len(kept)/len(ids) if ids else None}
            facets = cases[r['case_id']]['major_work_facets']
            known = {f for t in tt for f in t['main_work']}; retained = {f for t in tt if t['id'] in collected for f in t['main_work']}
            assert r[label + '_facets'] == {'known': [f for f in facets if f in known], 'retained': [f for f in facets if f in retained],
                'missing': [f for f in facets if f in known-retained], 'unassessed': [f for f in facets if f not in known],
                'known_coverage': len(retained)/len(known) if known else None}
    olddepth = read(DEPTH / 'results.json')
    for r in results:
        if r['variant'] in ('O', 'B2-S'):
            old = next(o for o in olddepth if o['case_id'] == r['case_id'] and o['variant'] == ('O' if r['variant'] == 'O' else 'B2') and o['depth_each_route'] == r['depth_each_route'])
            assert r['employee_candidate_ids'] == old['employee_candidate_ids'] and r['query_parent_pair_workload'] == old['rerank_pair_workload']
    traces = read(HERE / 'target-ranks.json')
    assert len(traces) == 48
    for t in traces:
        group = next(g for g in groups if g['case_id'] == t['case_id'] and g['variant'] == t['variant'])
        assert [p['query_id'] for p in t['paths']] == group['query_ids']
        for path in t['paths']:
            for label, rep in (('D', 'document'), ('T', 'task')):
                rank = ranks[(path['query_id'], rep)].index(t['id']) + 1
                assert path[label] == {'rank': rank, 'score': ranked[(path['query_id'], rep)][rank-1]['score']}
        assert t['minimum_N'] == min(p[label]['rank'] for p in t['paths'] for label in ('D', 'T'))
    summary = read(HERE / 'summary.json')
    assert len(summary) == 12
    for s in summary:
        rr = [r for r in results if r['variant'] == s['variant'] and r['depth_each_route'] == s['depth_each_route']]
        assert len(rr) == 8
        for label in ('known', 'clear'):
            assert s[label+'_targets_total'] == sum(len(r[label+'_targets']['known_ids']) for r in rr)
            assert s[label+'_targets_retained'] == sum(len(r[label+'_targets']['retained_ids']) for r in rr)
            assert s[label+'_facets_total'] == sum(len(r[label+'_facets']['known']) for r in rr)
            assert s[label+'_facets_retained'] == sum(len(r[label+'_facets']['retained']) for r in rr)
        assert s['query_count'] == sum(len(r['query_ids']) for r in rr)
        assert s['query_parent_pair_workload'] == sum(r['query_parent_pair_workload'] for r in rr)
        assert s['employee_unique_parents_total'] == sum(r['employee_unique_parents'] for r in rr)
        assert s['unassessed_cases'] == ['H01']
    scope = read(HERE / 'scope.json')
    assert scope == {'new_embedding_calls': 0, 'new_memory_calls': 0, 'new_rerank_calls': 0,
        'new_provider_calls': 0, 'external_cost_usd': 0, 'fresh_db_calls': 0,
        'fresh_service_latency_measured': False, 'new_holdout': False, 'full_corpus_recall': False}
    result = {'queries': 63, 'complete_parent_rankings': 126, 'point_cosines_independently_checked': point_count,
              'max_cosine_error': max_error, 'control_rankings_unchanged': 83, 'prior_depth_groups_unchanged': 48,
              'candidate_groups': 96, 'target_path_rows': 48, 'old_sealed_files_unchanged': sealed,
              'new_provider_calls': 0, 'fresh_service_latency_measured': False}
    with (HERE / output).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'verification.json')
