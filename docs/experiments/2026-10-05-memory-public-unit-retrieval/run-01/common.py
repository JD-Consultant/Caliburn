"""Isolated research, using prior aggregation and validation mechanisms."""
import hashlib,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
EXP=HERE.parents[1]
MEM=EXP/'2026-10-04-memory-layer-retrieval/run-01'
PUBLIC=EXP/'2026-10-04-public-chunk-retrieval/run-01'
CROSS=EXP/'2026-10-04-query-chunk-cross-retrieval/run-01'
F=EXP/'2026-10-04-representative-occupation-top5/run-01'
H=EXP/'2026-10-04-a-interview-occupation-retrieval/run-01'
OLD=EXP/'2026-10-04-retrieve-rerank'
MODEL_SHA='d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def text_sha(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name,v):
 p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def load(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def check_manifest(name='input-manifest.json'):
 for p,v in read(HERE/name)['inputs'].items():
  if sha(ROOT/p)!=v['sha256']:raise ValueError('frozen input changed: '+p)
merge_pools=load('unit_fusion',CROSS/'fusion.py').merge_pools
aggregate=load('unit_chunks',PUBLIC/'chunks.py').aggregate
validate_judgment=load('unit_validation',H/'pipeline.py').validate_judgment
token_windows=load('unit_windows',OLD/'evaluate.py').token_windows
METHODS={f'{v}-{r}':(v,r) for v in ('O','B2') for r in ('D','T','M')}
def method_queries(case,variant,queries):
 return [q for q in queries if q['case_id']==case and q['input_variant']==variant]

