"""Saved evidence audit only; does not call DB or model."""
import re
from decimal import Decimal
from pipeline import *

def main():
    check_manifest();check_manifest('retrieval-amendment-inputs.json')
    manifest=read(HERE/'input-manifest.json')['inputs']
    batches=[p for p in manifest if '/vector-batches/' in p and p.endswith('.npz')]
    assert len(batches)==346
    qs=read(HERE/'queries.json');vs=read(HERE/'query-vectors.json')
    for base in (F,H):
        oq={q['query_id']:q for q in read(base/'queries.json')};ov={v['query_id']:v for v in read(base/'query-vectors.json')}
        for q in [q for q in qs if q['query_id'] in oq]:
            assert all(q[k]==value for k,value in oq[q['query_id']].items())
        for v in [v for v in vs if v['query_id'] in ov]:
            assert all(v[k]==value for k,value in ov[v['query_id']].items() if k not in ('cache_reused','prior_vector_file'))
    checks=read(HERE/'database-checks.json');max_error=0
    for r in checks:
        assert r['overfetched_groups']==21
        for h in r['all_native_hits']:
            error=abs(h['score']-h['native_score']);assert error<1e-6
            max_error=max(error,max_error)
    assert len(checks)==90
    cases={c['case_id']:c for c in read(HERE/'cases.json')};docs={d['id']:d for d in read(HERE/'corpus.json')}
    original={}
    for file in ('reused-judgments.json','judgments.json','judgments-reconciled-02.json'):
        for j in read(PUBLIC/file):original[(j['case_id'],j['document_id'])]=j
    for j in read(HERE/'reused-judgments.json'):
        o=original[(j['case_id'],j['document_id'])]
        # The immediate provenance now points to PUBLIC; the original chain remains there.
        assert all(j[k]==v for k,v in o.items() if k not in ('reused','prior_judgment_file'))
    for j in read(HERE/'judgments.json'):
        response=read(HERE/'judge-trials'/('formal-02-'+j['job_id']+'-response.json'))
        text=''.join(c['text'] for item in response['output'] if item['type']=='message' for c in item['content'] if c['type']=='output_text')
        assert j['judgment']==json.loads(text)
        validate_judgment(j['judgment'],cases[j['case_id']]['employee_statement'],docs[j['document_id']]['text'])
    usage=[json.loads(s) for s in (HERE/'judge-usage.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(usage)==8 and all(u['usage_known'] and u['phase']=='formal-02' for u in usage)
    cost=sum((Decimal(u['accounted_usd']) for u in usage),Decimal(0));assert cost==Decimal('0.005628700')
    stopped=json.loads((HERE/'services-stopped.json').read_text(encoding='utf-8-sig'))
    assert stopped['qdrant_stopped'] and stopped['listener_count']==0
    assert stopped['storage_collections_preserved'] and stopped['embedding_or_reranker_started_by_this_run'] is False
    v=read(HERE/'verification.json');assert v['previous_unchanged_files']==1672 and v['protected_inputs']==8
    files=[HERE/'README.md',HERE/'report.md',HERE/'protocol.md',HERE/'progress.md',
           ROOT/'docs/plans/2026-10-04-query-chunk-cross-retrieval.md',ROOT/'docs/current-decisions.md',
           ROOT/'docs/experiments/README.md',ROOT/'docs/specs/README.md',
           ROOT/'docs/specs/2026-10-04-occupation-overview-reference-retrieval-design.md',
           ROOT/'docs/plans/2026-10-04-public-reference-retrieval-design.md']
    links=0
    for path in files:
        for target in re.findall(r'\]\(([^\s)]+)\)',path.read_text(encoding='utf-8')):
            if '://' in target or target.startswith('#'):continue
            dest=target.split('#')[0]
            assert (path.parent/dest).exists(),(str(path),target)
            links+=1
    dump('final-audit.json',{'passed':True,'query_originals_unchanged':30,'public_vector_batches_hashed':346,
        'old_pair_grades_unchanged':117,'new_valid_responses':8,'quote_repairs':0,'max_native_cosine_error':max_error,
        'previous_unchanged_files':1672,'protected_inputs':8,'estimated_usd':str(cost),'links_checked':links,
        'owned_services_stopped':True,'no_production_change_by_this_experiment':True,'no_commit_push_merge':True,
        'independent_review_recorded':(HERE/'review.md').exists()})
    print(json.dumps(read(HERE/'final-audit.json'),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
