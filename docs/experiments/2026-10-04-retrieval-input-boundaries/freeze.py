"""Freeze only observed labels and lossless representations before new ranking."""
import time
from support import *

cases = read(QUOTA/'development-cases.json')+read(QUOTA/'holdout-cases-2026-10-04-reviewed.json')
assert len(cases)==22 and sum(len(c['topics']) for c in cases)==86
dump('cases.json',cases)
queries = make_inputs(cases)
dump('inputs.json',queries)
dump('input-manifest.json',{'created_utc':time.time(),'before_new_embeddings_or_rankings':True,
    'scope':'All observed synthetic cases; lossless boundary probe; no new holdout or JD semantic alignment labels',
    'source_hashes':{n:sha(QUOTA/n) for n in ('development-cases.json','holdout-cases-2026-10-04-reviewed.json','artifact-hashes.json')},
    'files':{n:sha(HERE/n) for n in ('protocol.md','cases.json','inputs.json','inputs.py','support.py','freeze.py')},
    'queries_by_variant':{v:sum(len(q['passages']) for q in queries if q['variant']==v) for v in VARIANTS},
    'configs':CONFIGS})
print(json.dumps(read(HERE/'input-manifest.json')['queries_by_variant'],indent=2))
