"""Read-only final checks, then save this run's audit and artifact seal."""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import re
from pipeline import HERE, PARENT, ROOT, check_manifest, dump, read, sha


def main():
    check_manifest('analysis-manifest.json')
    draft = read(PARENT / 'draft-input-manifest-v1.json')['inputs']
    for path, metadata in draft.items():
        assert sha(ROOT / path) == metadata['sha256'], path
    protected = read(PARENT.parent / '2026-10-04-retrieval-reference-views/execution-manifest.json')['inputs']
    for path, metadata in protected.items():
        assert sha(ROOT / path) == metadata['sha256'], path
    previous = 0
    for name in ('occupation-retrieval', 'occupation-retrieval-generalization', 'retrieve-rerank',
                 'retrieval-passage-quota', 'retrieval-input-boundaries', 'retrieval-reference-views'):
        directory = PARENT.parent / ('2026-10-04-' + name)
        seal = read(directory / 'artifact-hashes.json')
        for path, metadata in seal.get('files', seal).items():
            expected = metadata if isinstance(metadata, str) else metadata['sha256']
            assert sha(directory / path) == expected, str(directory / path)
            previous += 1
    usage = [read_line for line in (HERE / 'judge-usage.jsonl').read_text(encoding='utf-8').splitlines()
             if (read_line := __import__('json').loads(line))]
    assert len(usage) == 63 and all(row['usage_known'] for row in usage)
    assert Counter(row['phase'] for row in usage) == {'calibrate': 7, 'calibrate-02': 7, 'grade': 49}
    cost = sum(Decimal(row['estimated_usd']) for row in usage)
    assert cost == Decimal('0.035030905') and cost < Decimal('1')
    trace = read(HERE / 'known-strong-reference-stage-trace.json')
    for path, expected in trace['inputs'].items():
        assert sha(HERE / path) == expected
    results = {(row['case_id'], row['method']): row for row in read(HERE / 'results.json')}
    dense = {row['query_id']: row['ranked'] for row in read(HERE / 'dense-rankings.json')}
    def rank(rows, ident):
        return next((i for i, row in enumerate(rows, 1) if row['id'] == ident), None)
    known = {(row['case_id'], item['document_id'])
             for row in read(HERE / 'graded-results.json') for item in row['selected'] if item['grade'] == 3}
    assert {(row['case_id'], row['document_id']) for row in trace['references']} == known
    for row in trace['references']:
        for method in row['methods']:
            source = results[(row['case_id'], method['method'])]
            ident = row['document_id']
            assert method['merged_rank_1_based'] == rank(source['merged_ranking'], ident)
            assert method['final_k5_rank_1_based'] == rank(source['selected'], ident)
            for query, pool in zip(method['queries'], source['query_rankings']):
                dense_rank = rank(dense[query['query_id']], ident)
                assert query['full_dense_rank_1_based'] == dense_rank
                assert query['initial_n20_included'] == (dense_rank <= 20)
                assert query['pool_rank_after_method_order_1_based'] == rank(pool, ident)
    cleanup = read(HERE / 'cleanup.json')
    assert cleanup['stopped_own_qdrant'] and cleanup['remaining_listeners'] == 0
    containers = [__import__('json').loads(line) for line in
                  (HERE / 'container-states.jsonl').read_text(encoding='utf-8-sig').splitlines()]
    assert len(containers) == 3 and all(not row['state']['Running'] for row in containers)
    documents = [HERE / name for name in ('README.md', 'review.md', 'stage-trace.md', 'progress.md')]
    documents += [ROOT / name for name in ('docs/current-decisions.md', 'docs/specs/README.md',
        'docs/experiments/README.md', 'docs/specs/2026-10-04-occupation-overview-reference-retrieval-design.md',
        'docs/plans/2026-10-04-public-reference-retrieval-design.md',
        'docs/plans/2026-10-04-representative-occupation-top5.md',
        'docs/research/retrieval/2026-10-04-retrieval-relevance-judgment-methods.md')]
    links = 0
    for document in documents:
        text = document.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', text):
            if re.match(r'\w+://', target) or target.startswith('#'):
                continue
            assert (document.parent / target.split('#')[0]).exists(), (document, target)
            links += 1
    dump('final-audit.json', {
        'created_utc': datetime.now(timezone.utc).isoformat(), 'passed': True,
        'frozen_draft_inputs_unchanged': len(draft), 'protected_inputs_unchanged': len(protected),
        'prior_sealed_artifacts_unchanged': previous, 'model_responses': len(usage),
        'estimated_usage_usd': str(cost), 'known_strong_pairs_traced': len(known),
        'checked_documents': len(documents), 'local_links_exist': links,
        'own_services_stopped': True, 'independent_review': 'review.md',
        'semantic_limitations': ['same-anchor regression is not independent calibration',
                                 'F04 facet granularity', 'F04 cross-object 1/2 boundary'],
        'scope': 'source integrity, usage, trace, documentation and cleanup only; not semantic correctness',
    })
    files = {}
    for path in sorted(HERE.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.name == 'artifact-hashes.json':
            continue
        files[path.relative_to(HERE).as_posix()] = {'sha256': sha(path), 'bytes': path.stat().st_size}
    dump('artifact-hashes.json', {'created_utc': datetime.now(timezone.utc).isoformat(), 'files': files,
          'scope': 'run-01 artifacts; original employee/rubric snapshot bound by draft and execution manifests'})
    print(f'Final audit passed: {previous} prior files unchanged; {links} links; {len(files)} run files sealed.')


if __name__ == '__main__':
    main()
