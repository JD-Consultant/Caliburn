import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
EXP=HERE.parents[1]
PUBLIC=EXP/'2026-10-04-public-chunk-retrieval/run-01'
F=EXP/'2026-10-04-representative-occupation-top5/run-01'
H=EXP/'2026-10-04-a-interview-occupation-retrieval/run-01'
LOCAL={'Dmax':('document','max'),'Tmax':('task','max'),'Tmean3':('task','mean3'),
       'Umax':('unit','max'),'Umean3':('unit','mean3')}
METHODS={prefix+'-'+name:(variant,rep,agg) for prefix,variant in [('W','whole'),('S','segments')]
         for name,(rep,agg) in LOCAL.items()}

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as s:
        while b:=s.read(8*1024*1024):h.update(b)
    return h.hexdigest()
def text_sha(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def dump(name,value):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as s:json.dump(value,s,ensure_ascii=False,indent=2);s.write('\n')
def check_manifest(name='input-manifest.json'):
    for path,value in read(HERE/name)['inputs'].items():
        if sha(ROOT/path)!=value['sha256']:raise ValueError('frozen input changed: '+path)
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
validate_judgment=load(H/'pipeline.py','cross_prior_validation').validate_judgment
