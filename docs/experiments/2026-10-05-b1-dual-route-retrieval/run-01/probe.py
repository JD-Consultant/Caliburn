"""Throwaway offline experiment: no provider, DB or production wiring."""
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXP = HERE.parents[1]
MEM = EXP / '2026-10-04-memory-layer-retrieval/run-01'
PUBLIC = EXP / '2026-10-04-public-chunk-retrieval/run-01'
PRIOR = EXP / '2026-10-05-memory-public-unit-retrieval/run-01'
DEPTH = EXP / '2026-10-05-initial-retrieval-depth/run-01'
UNION = EXP / '2026-10-05-rerank-union-candidate-replay/run-01'
METHODS = {'O': 'O-W', 'B1-W': 'B1-W', 'B1-S': 'B1-S', 'B2-S': 'B2-S'}
DEPTHS = (20, 40, 80)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def dump(name, value):
    with (HERE / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


chunks_api = load_module('b1_probe_chunks', PUBLIC / 'chunks.py')
depth_api = load_module('b1_probe_depth', DEPTH / 'evaluate.py')


def score_route(rows, matrix, vector):
    matrix = np.asarray(matrix, dtype=np.float64)
    vector = np.asarray(vector, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape != (len(rows), len(vector)):
        raise ValueError('vector shape mismatch')
    norms, qnorm = np.linalg.norm(matrix, axis=1, keepdims=True), np.linalg.norm(vector)
    if not np.isfinite(matrix).all() or not np.isfinite(vector).all() or qnorm == 0 or (norms == 0).any():
        raise ValueError('invalid vector')
    scores = (matrix / norms) @ (vector / qnorm)
    hits = [{'parent_id': r['parent_id'], 'chunk_id': r['chunk_id'], 'score': float(s)}
            for r, s in zip(rows, scores, strict=True)]
    parents = chunks_api.aggregate(hits, 'max', len(rows))
    return scores, parents


def check_seals():
    checks = []
    for directory in (MEM, PUBLIC, PRIOR, UNION, DEPTH):
        seal = read(directory / 'artifact-hashes.json')
        for relative, expected in seal['files'].items():
            path = directory / relative
            if path.stat().st_size != expected['bytes'] or sha(path) != expected['sha256']:
                raise ValueError('old artifact changed: ' + str(path))
        checks.append({'directory': directory.relative_to(ROOT).as_posix(),
                       'manifest_sha256': sha(directory / 'artifact-hashes.json'),
                       'files': len(seal['files']), 'mismatches': 0})
    return checks


def freeze():
    files = [MEM / name for name in ('queries.json', 'query-vectors.json', 'method-groups.json',
                                    'all-rankings.json', 'graded-results.json', 'cases.json', 'corpus.json')]
    files += [PUBLIC / 'chunks.json', PUBLIC / 'chunks.py', PRIOR / 'all-rankings.json',
              DEPTH / 'targets.json', DEPTH / 'results.json', DEPTH / 'evaluate.py']
    files += sorted((PUBLIC / 'vector-batches').glob('*.npz'))
    files += [HERE / name for name in ('protocol.md', 'probe.py', 'verify.py', 'test_probe.py')]
    for directory in (MEM, PUBLIC, PRIOR, UNION, DEPTH):
        files.append(directory / 'artifact-hashes.json')
    checks = check_seals()
    dump('prior-seals-before.json', checks)
    dump('input-manifest.json', {'inputs': {p.relative_to(ROOT).as_posix():
         {'sha256': sha(p), 'bytes': p.stat().st_size} for p in files},
         'scope': 'offline initial exact candidate experiment; no rerank or new semantic judgments'})
    print(f'Frozen {len(files)} inputs; {sum(c["files"] for c in checks)} old files checked', flush=True)


def check_manifest():
    for relative, expected in read(HERE / 'input-manifest.json')['inputs'].items():
        path = ROOT / relative
        if path.stat().st_size != expected['bytes'] or sha(path) != expected['sha256']:
            raise ValueError('frozen input changed: ' + relative)


def main():
    check_manifest()
    cases = read(MEM / 'cases.json')
    docs = {d['id']: d for d in read(MEM / 'corpus.json')}
    targets = read(DEPTH / 'targets.json')
    oldq = {q['query_id']: q for q in read(MEM / 'queries.json')}
    vectors = {v['query_id']: v for v in read(MEM / 'query-vectors.json')}
    groups = read(MEM / 'method-groups.json')
    queries, arms = [], []
    for case in cases:
        for variant, method in METHODS.items():
            group = next(g for g in groups if g['case_id'] == case['case_id'] and g['method'] == method)
            arms.append({'case_id': case['case_id'], 'variant': variant, 'query_ids': group['query_ids']})
            for qid in group['query_ids']:
                q = dict(oldq[qid])
                q['input_variant'] = variant
                assert vectors[qid]['text_sha256'] == q['text_sha256'] == text_sha(q['text'])
                assert len(vectors[qid]['dense']) == 1024
                queries.append(q)
    assert len(queries) == len({q['query_id'] for q in queries}) == 63
    for target in targets:
        case = next(c for c in cases if c['case_id'] == target['case_id'])
        assert target['employee_sha256'] == text_sha(case['employee_statement'])
        assert target['document_sha256'] == text_sha(docs[target['id']]['text'])
    raw = {}
    for path in sorted((PUBLIC / 'vector-batches').glob('*.npz')):
        with np.load(path, allow_pickle=False) as z:
            for h, v in zip(z['hashes'], z['dense'], strict=True):
                key = str(h)
                if key in raw:
                    assert np.array_equal(raw[key], v)
                raw[key] = v
    chunks = read(PUBLIC / 'chunks.json')
    rows = {rep: [r for r in chunks if r['representation'] == rep] for rep in ('document', 'task')}
    assert len(rows['document']) == 805 and len(rows['task']) == 8068
    for rep, rr in rows.items():
        assert {r['parent_id'] for r in rr} == set(docs)
        if rep == 'document':
            assert all(r['text'] == docs[r['parent_id']]['text'] for r in rr)
    matrices = {rep: np.asarray([raw[text_sha(r['text'])] for r in rr], dtype=np.float64)
                for rep, rr in rows.items()}
    oldranks = {r['query_id']: r['ranking'] for r in read(MEM / 'all-rankings.json')}
    prior = {(r['query_id'], r['representation']): r['parents'] for r in read(PRIOR / 'all-rankings.json')}
    ranked, scores, controls, compute = [], {}, [], []
    lookup = {}
    for i, q in enumerate(queries):
        for rep in ('document', 'task'):
            tick = time.perf_counter()
            sc, parents = score_route(rows[rep], matrices[rep], vectors[q['query_id']]['dense'])
            elapsed = time.perf_counter() - tick
            assert len(parents) == 805
            key = (q['query_id'], rep)
            lookup[key] = parents
            ranked.append({'query_id': q['query_id'], 'representation': rep, 'parents': parents})
            scores[f'q{i}_{rep}'] = sc
            controls_to_check = []
            if key in prior:
                controls_to_check.append(('prior_dual_route', prior[key]))
            if q['input_variant'].startswith('B1') and rep == 'document':
                controls_to_check.append(('prior_B1_document', oldranks[q['query_id']]))
            for label, expected in controls_to_check:
                assert [r['id'] for r in parents] == [r['id'] for r in expected], key
                error = max(abs(a['score'] - b['score']) for a, b in zip(parents, expected, strict=True))
                assert error < 1e-12
                controls.append({'query_id': q['query_id'], 'representation': rep, 'control': label,
                                 'all_805_parent_ids_unchanged': True, 'max_score_error': error})
            compute.append({'query_id': q['query_id'], 'representation': rep,
                            'offline_score_and_aggregate_seconds': elapsed, 'service_latency': False})
        print(f'Scored {i+1}/63 {q["query_id"]}', flush=True)
    assert len(controls) == 83
    results, traces = [], []
    for arm in arms:
        case = next(c for c in cases if c['case_id'] == arm['case_id'])
        own = [t for t in targets if t['case_id'] == arm['case_id']]
        for target in own:
            paths = []
            for qid in arm['query_ids']:
                entry = {'query_id': qid}
                for label, rep in (('D', 'document'), ('T', 'task')):
                    parents = lookup[(qid, rep)]
                    at = next(i for i, p in enumerate(parents, 1) if p['id'] == target['id'])
                    entry[label] = {'rank': at, 'score': parents[at-1]['score']}
                paths.append(entry)
            traces.append({'case_id': arm['case_id'], 'variant': arm['variant'],
                           'id': target['id'], 'title': target['title'], 'paths': paths,
                           'minimum_N': min(p[label]['rank'] for p in paths for label in ('D', 'T')),
                           'sensitivity_excluded': target['sensitivity_excluded']})
        for n in DEPTHS:
            candidates, pools = set(), []
            for qid in arm['query_ids']:
                dr, tr = lookup[(qid, 'document')], lookup[(qid, 'task')]
                union = depth_api.candidate_union([p['id'] for p in dr], [p['id'] for p in tr], n)
                candidates.update(union)
                pools.append({'query_id': qid, 'D_ids': [p['id'] for p in dr[:n]],
                              'T_ids': [p['id'] for p in tr[:n]], 'union_ids': union})
            result = {**arm, 'depth_each_route': n, 'query_pools': pools,
                      'employee_candidate_ids': sorted(candidates), 'employee_unique_parents': len(candidates),
                      'query_parent_pair_workload': sum(len(p['union_ids']) for p in pools)}
            for label, tt in (('known', own), ('clear', [t for t in own if not t['sensitivity_excluded']])):
                ids = [t['id'] for t in tt]
                retained = [ident for ident in ids if ident in candidates]
                result[label + '_targets'] = {'known_ids': ids, 'retained_ids': retained,
                    'missing_ids': [ident for ident in ids if ident not in candidates],
                    'coverage': len(retained) / len(ids) if ids else None}
                result[label + '_facets'] = depth_api.facet_state(case['major_work_facets'], tt, candidates)
            results.append(result)
    summaries = []
    for variant in METHODS:
        for n in DEPTHS:
            rr = [r for r in results if r['variant'] == variant and r['depth_each_route'] == n]
            s = {'variant': variant, 'depth_each_route': n, 'query_count': sum(len(r['query_ids']) for r in rr),
                 'query_parent_pair_workload': sum(r['query_parent_pair_workload'] for r in rr),
                 'employee_unique_parents_total': sum(r['employee_unique_parents'] for r in rr),
                 'unassessed_cases': [r['case_id'] for r in rr if r['known_targets']['coverage'] is None]}
            for label in ('known', 'clear'):
                s[label + '_targets_total'] = sum(len(r[label + '_targets']['known_ids']) for r in rr)
                s[label + '_targets_retained'] = sum(len(r[label + '_targets']['retained_ids']) for r in rr)
                s[label + '_facets_total'] = sum(len(r[label + '_facets']['known']) for r in rr)
                s[label + '_facets_retained'] = sum(len(r[label + '_facets']['retained']) for r in rr)
            summaries.append(s)
    dump('queries.json', queries)
    dump('method-groups.json', arms)
    dump('all-rankings.json', ranked)
    np.savez_compressed(HERE / 'chunk-scores.npz', **scores)
    dump('results.json', results)
    dump('target-ranks.json', traces)
    dump('summary.json', summaries)
    dump('control-checks.json', controls)
    dump('offline-compute.json', compute)
    dump('scope.json', {'new_embedding_calls': 0, 'new_memory_calls': 0, 'new_rerank_calls': 0,
         'new_provider_calls': 0, 'external_cost_usd': 0, 'fresh_db_calls': 0,
         'fresh_service_latency_measured': False, 'new_holdout': False, 'full_corpus_recall': False})
    print(json.dumps(summaries, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'freeze':
        freeze()
    else:
        main()
