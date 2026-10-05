"""Network-disabled public reranker, explicit content-key jobs and benchmark tasks."""
import math
import time
import torch
from transformers import AutoModelForSequenceClassification,AutoTokenizer
from support import *
from evaluate import token_windows

started = time.monotonic()
execution = read(HERE/'execution.json')
for name,digest in execution['sources'].items():
    assert sha(HERE/name)==digest,name
for name,digest in execution['prior_sources'].items():
    assert sha(QUOTA/name)==digest,name
assert sha(Path('/model/model.safetensors'))==MODEL_SHA
torch.set_num_threads(4)
tokenizer = AutoTokenizer.from_pretrained('/model',local_files_only=True,trust_remote_code=False)
tick = time.perf_counter()
model = AutoModelForSequenceClassification.from_pretrained('/model',local_files_only=True,trust_remote_code=False,
            dtype=torch.float16,attn_implementation='sdpa').to('cuda').eval()
torch.cuda.synchronize()
dump('gpu-runtime.json',{'load_seconds':time.perf_counter()-tick,'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,
    'model_revision':'953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e','model_sha256':MODEL_SHA,'attention':model.config._attn_implementation,
    'batch_size':1,'max_pair_tokens':8192,'overlap':64,'execution_sha256':sha(HERE/'execution.json')})
prepared = read(HERE/'prepared.json'); corpus = {d['id']:d for d in prepared['corpus']}

def score(query,doc):
    if time.monotonic()-started>2700:
        raise TimeoutError('45 minute worker bound')
    tick = time.perf_counter(); windows = []
    for window in token_windows(query,doc,8192,overlap=64):
        ids = tokenizer.build_inputs_with_special_tokens(query,window); assert len(ids)<=8192
        inputs = {'input_ids':torch.tensor([ids],device='cuda'),
                  'attention_mask':torch.ones((1,len(ids)),device='cuda',dtype=torch.long)}
        torch.cuda.synchronize(); forward = time.perf_counter()
        with torch.inference_mode():
            logit = float(model(**inputs,return_dict=True).logits.flatten()[0].float().item())
        torch.cuda.synchronize()
        windows.append({'pair_tokens':len(ids),'document_tokens':len(window),'logit':logit,'forward_seconds':time.perf_counter()-forward})
    value = max(w['logit'] for w in windows); assert math.isfinite(value)
    return {'logit':value,'windows':windows,'query_tokens':len(query),'document_tokens':len(doc),'score_seconds':time.perf_counter()-tick}

count = 0
with (HERE/'supplemental-pairs.jsonl').open('x',encoding='utf-8') as stream:
    for job in read(HERE/'jobs.json'):
        assert text_sha(job['query'])==job['query_sha256']
        query = tokenizer.encode(job['query'],add_special_tokens=False,truncation=False)
        for ident,digest in job['documents'].items():
            assert text_sha(corpus[ident]['text'])==digest
            doc = tokenizer.encode(corpus[ident]['text'],add_special_tokens=False,truncation=False)
            record = {**score(query,doc),'query_sha256':job['query_sha256'],'document_sha256':digest,
                      'document_id':ident,'model_sha256':MODEL_SHA,'cache_reused':False}
            stream.write(json.dumps(record)+'\n'); stream.flush(); count+=1
        print(f'{count} pairs supplemented',flush=True)
dump('gpu-quality-complete.json',{'pairs':count,'elapsed_seconds':time.monotonic()-started,'finished_utc':time.time()})
queries = {(q['case_id'],q['variant']):q for q in prepared['queries']}
for task in read(HERE/'benchmark-plan.json')['requests']:
    path = HERE/'benchmark-requests'/f'{task["request_id"]}.json'
    while not path.exists():
        if time.monotonic()-started>2700:
            raise TimeoutError('bounded benchmark handoff')
        time.sleep(.02)
    begin = time.perf_counter(); request = read(path)
    assert all(request[k]==task[k] for k in ('request_id','case_id','variant','repeat','config'))
    q = queries[(task['case_id'],task['variant'])]
    wanted = {(p,d['id']) for p,pool in enumerate(q['pools'],1) for d in pool[:20]}
    assert {(r['passage'],r['id']) for r in request['pairs']}==wanted
    tick = time.perf_counter()
    query_tokens = [tokenizer.encode(t,add_special_tokens=False,truncation=False) for t in q['passages']]
    docs = {ident:tokenizer.encode(corpus[ident]['text'],add_special_tokens=False,truncation=False) for _,ident in wanted}
    tokenize_seconds = time.perf_counter()-tick
    results = [{'passage':p,'id':ident,**score(query_tokens[p-1],docs[ident])} for p,ident in sorted(wanted)]
    response = {'request_id':task['request_id'],'tokenize_seconds':tokenize_seconds,'worker_seconds':time.perf_counter()-begin,'pairs':results}
    temp = HERE/'benchmark-responses'/f'{task["request_id"]}.tmp'
    temp.write_text(json.dumps(response),encoding='utf-8'); temp.rename(temp.with_suffix('.json'))
    print(f"benchmark {task['request_id']}: {response['worker_seconds']:.3f}s",flush=True)
dump('gpu-complete.json',{'quality_pairs':count,'bench_requests':len(read(HERE/'benchmark-plan.json')['requests']),
                        'elapsed_seconds':time.monotonic()-started,'finished_utc':time.time()})
