import hashlib, importlib.util, json, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
EXP=HERE.parents[1]
CROSS=EXP/'2026-10-04-query-chunk-cross-retrieval/run-01'
PUBLIC=EXP/'2026-10-04-public-chunk-retrieval/run-01'
F=EXP/'2026-10-04-representative-occupation-top5/run-01'
H=EXP/'2026-10-04-a-interview-occupation-retrieval/run-01'
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def text_sha(t): return hashlib.sha256(t.encode('utf-8')).hexdigest()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name,value):
 p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8',newline='\n') as f: json.dump(value,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def append(name,value):
 with (HERE/name).open('a',encoding='utf-8') as f:f.write(json.dumps(value,ensure_ascii=False,default=str)+'\n')
def load(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def check_manifest(name='input-manifest.json'):
 for p,v in read(HERE/name)['inputs'].items():
  if sha(ROOT/p)!=v['sha256']:raise ValueError('frozen input changed: '+p)
validate_judgment=load('layer_prior_validation',H/'pipeline.py').validate_judgment
merge_pools=load('layer_prior_fusion',CROSS/'fusion.py').merge_pools
