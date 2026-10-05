"""Local public weights; content-addressed missing pairs and bounded file benchmarks."""
import math
import time
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from common import *
from evaluate import token_windows

phase = sys.argv[1]
start = time.monotonic()
execution_path = HERE/(sys.argv[2] if len(sys.argv)>2 else f'execution-{phase}.json')
execution = read(execution_path)
for name,digest in execution['sources'].items():
    assert sha(HERE/name)==digest,name
assert sha(Path('/model/model.safetensors'))==MODEL_SHA
torch.set_num_threads(4)
tokenizer = AutoTokenizer.from_pretrained('/model',local_files_only=True,trust_remote_code=False)
tick = time.perf_counter()
model = AutoModelForSequenceClassification.from_pretrained('/model',local_files_only=True,trust_remote_code=False,
        dtype=torch.float16,attn_implementation='sdpa').to('cuda').eval()
torch.cuda.synchronize()
runtime = {'load_seconds':time.perf_counter()-tick,'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,
           'attention':model.config._attn_implementation,'batch_size':1,'max_pair_tokens':8192,'overlap':64,
           'model_sha256':MODEL_SHA,'model_revision':'953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e',
           'execution_sha256':sha(execution_path)}
dump(f'gpu-runtime-{phase}.json',runtime)
corpus = {d['id']:d for d in read(HERE/f'prepared-{phase}.json')['corpus']}

def score(query,document):
    if time.monotonic()-start>2700:
        raise TimeoutError('45 minute worker bound')
    windows = []
    tick = time.perf_counter()
    for window in token_windows(query,document,8192,overlap=64):
        ids = tokenizer.build_inputs_with_special_tokens(query,window)
        assert len(ids)<=8192
        inputs = {'input_ids':torch.tensor([ids],device='cuda'),
                  'attention_mask':torch.ones((1,len(ids)),device='cuda',dtype=torch.long)}
        torch.cuda.synchronize(); forward = time.perf_counter()
        with torch.inference_mode():
            logit = float(model(**inputs,return_dict=True).logits.flatten()[0].float().item())
        torch.cuda.synchronize()
        windows.append({'pair_tokens':len(ids),'document_tokens':len(window),'logit':logit,'forward_seconds':time.perf_counter()-forward})
    value = max(w['logit'] for w in windows)
    assert math.isfinite(value)
    return {'logit':value,'windows':windows,'query_tokens':len(query),'document_tokens':len(document),'score_seconds':time.perf_counter()-tick}

jobs = read(HERE/f'{phase}-jobs.json')
count = 0
with (HERE/f'supplemental-{phase}-pairs.jsonl').open('x',encoding='utf-8') as stream:
    for job in jobs:
        assert text_sha(job['query'])==job['query_sha256']
        query = tokenizer.encode(job['query'],add_special_tokens=False,truncation=False)
        for ident,digest in job['documents'].items():
            text = corpus[ident]['text']; assert text_sha(text)==digest
            doc = tokenizer.encode(text,add_special_tokens=False,truncation=False)
            record = {**score(query,doc),'query_sha256':job['query_sha256'],'document_sha256':digest,
                      'document_id':ident,'model_sha256':MODEL_SHA,'cache_reused':False}
            stream.write(json.dumps(record)+'\n'); stream.flush(); count+=1
        print(f"{phase}: {count} supplemented pairs",flush=True)
dump(f'gpu-complete-{phase}.json',{'pairs':count,'elapsed_seconds':time.monotonic()-start,'finished_utc':time.time()})
if phase=='development':
    sys.exit(0)

# Resident, network-disabled worker handles only pre-frozen development benchmark plan.
plan = read(HERE/'benchmark-plan.json')
dev = read(HERE/'prepared-development.json')
by_case = {q['case_id']:q for q in dev['queries']}
for expected in plan['requests']:
    path = HERE/'benchmark-requests'/f"{expected['request_id']}.json"
    while not path.exists():
        if time.monotonic()-start>2700:
            raise TimeoutError('benchmark handoff bound')
        time.sleep(.02)
    tick = time.perf_counter()
    request = read(path)
    assert request['config']==expected['config'] and request['case_id']==expected['case_id']
    q = by_case[request['case_id']]
    wanted = required(q,request['config']) if request['config']['method']!='full_rerank' else {(i,d) for i in range(1,len(q['passages'])+1) for d in corpus}
    assert {(r['passage'],r['id']) for r in request['pairs']}==wanted
    begin = time.perf_counter()
    query_tokens = [tokenizer.encode(t,add_special_tokens=False,truncation=False) for t in q['passages']]
    doc_tokens = {ident:tokenizer.encode(corpus[ident]['text'],add_special_tokens=False,truncation=False) for _,ident in wanted}
    tokenize_seconds = time.perf_counter()-begin
    values = []
    for p,ident in sorted(wanted):
        values.append({'passage':p,'id':ident,**score(query_tokens[p-1],doc_tokens[ident])})
    result = {'request_id':expected['request_id'],'pairs':values,'tokenize_seconds':tokenize_seconds,
              'worker_seconds':time.perf_counter()-tick}
    temporary = HERE/'benchmark-responses'/f"{expected['request_id']}.tmp"
    temporary.write_text(json.dumps(result),encoding='utf-8')
    temporary.rename(temporary.with_suffix('.json'))
    print(f"benchmark {expected['request_id']}: {result['worker_seconds']:.2f}s",flush=True)
dump('gpu-benchmark-complete.json',{'requests':len(plan['requests']),'elapsed_seconds':time.monotonic()-start})
