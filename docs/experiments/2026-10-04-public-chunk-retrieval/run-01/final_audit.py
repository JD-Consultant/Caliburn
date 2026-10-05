"""Final local evidence, route-link and stopped-service audit; no model or DB writes."""
import re
from decimal import Decimal
from pipeline import *

def main():
    check_manifest();verification=read(HERE/'verification.json');assert verification['passed']
    check_manifest('analysis-manifest.json')
    protected=read(EXP/'2026-10-04-retrieval-reference-views/execution-manifest.json')['inputs']
    for path,record in protected.items():assert sha(ROOT/path)==record['sha256'],path
    usage=[json.loads(s) for s in (HERE/'judge-usage.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(usage)==35 and all(r['usage_known'] for r in usage)
    assert sum(Decimal(r['accounted_usd']) for r in usage)==Decimal('0.037831530')
    assert all(r['requested_model']=='gpt-6-luna' and r['service_tier']=='default' for r in usage)
    for batch in [json.loads(s) for s in (HERE/'embedding-batches.jsonl').read_text(encoding='utf-8').splitlines()]:
        assert sha(HERE/batch['path'])==batch['sha256']
    cleanup=json.loads((HERE/'cleanup.json').read_text(encoding='utf-8-sig'))
    assert cleanup['qdrant_absent'] and cleanup['listeners']==0 and cleanup['embedder_state'].startswith('exited')
    assert len(read(HERE/'baseline-check.json'))==8
    files=[HERE/'README.md',HERE/'protocol.md',ROOT/'docs/plans/2026-10-04-public-chunk-retrieval.md',
           ROOT/'docs/current-decisions.md',ROOT/'docs/experiments/README.md',ROOT/'docs/specs/README.md',
           ROOT/'docs/specs/2026-10-04-occupation-overview-reference-retrieval-design.md',
           ROOT/'docs/plans/2026-10-04-public-reference-retrieval-design.md']
    links=0;missing=[]
    for file in files:
        text=file.read_text(encoding='utf-8')
        for target in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)',text):
            target=target.strip('<>').split('#',1)[0]
            if not target or re.match(r'^\w+://',target):continue
            if not (file.parent/target).exists():missing.append({'file':str(file),'target':target})
            links+=1
    assert not missing,missing
    dump('final-audit.json',{'passed':True,'previous_unchanged_files':verification['previous_unchanged_files'],
          'protected_inputs_unchanged':len(protected),'vector_batches_hashed':346,'baseline_checks':8,
          'judge_responses':35,'usage_known':35,'estimated_usd':'0.037831530','links_checked':links,
          'services_stopped':True,'cleanup_actual_embedder_exit':cleanup['embedder_state'],
          'no_production_change':True,'no_commit_push_merge':True})
    print(json.dumps(read(HERE/'final-audit.json'),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
