"""Pinned offline GPU cross-encoder; all quality/benchmark pairs are fresh."""
import time
import math
import sys
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from pipeline import *

sys.path.insert(0,str(OLD))
from evaluate import token_windows

started = time.monotonic()
check_manifest()
check_manifest('gpu-input-manifest.json')
assert sha(Path('/model/model.safetensors')) == MODEL_SHA
torch.set_num_threads(4)
tokenizer = AutoTokenizer.from_pretrained('/model',local_files_only=True,trust_remote_code=False)
tick = time.perf_counter()
model = AutoModelForSequenceClassification.from_pretrained('/model',local_files_only=True,trust_remote_code=False,
       dtype=torch.float16,attn_implementation='sdpa').to('cuda').eval()
torch.cuda.synchronize()
dump('gpu-runtime.json',{'load_seconds':time.perf_counter()-tick,'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,
                       'model_sha256':MODEL_SHA,'revision':'953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e',
                       'attention':model.config._attn_implementation,'max_pair_tokens':8192,'overlap':64,'batch_size':1})
queries = {q['query_id']:q for q in read(HERE / 'queries.json')}
corpus = {d['id']:d for d in read(HERE / 'corpus.json')}
ranks = {r['query_id']:r['ranked'] for r in read(HERE / 'dense-rankings.json')}


def score(query_id, ident):
    if time.monotonic()-started > 1800:
        raise TimeoutError('bounded GPU run')
    tick = time.perf_counter()
    query_text, doc_text = queries[query_id]['text'], corpus[ident]['text']
    query = tokenizer.encode(query_text,add_special_tokens=False,truncation=False)
    doc = tokenizer.encode(doc_text,add_special_tokens=False,truncation=False)
    tokenize = time.perf_counter()-tick
    windows = []
    for window in token_windows(query,doc,8192,overlap=64):
        ids = tokenizer.build_inputs_with_special_tokens(query,window)
        assert len(ids) <= 8192
        inputs = {'input_ids':torch.tensor([ids],device='cuda'),
                  'attention_mask':torch.ones((1,len(ids)),device='cuda',dtype=torch.long)}
        torch.cuda.synchronize(); forward = time.perf_counter()
        with torch.inference_mode():
            logit = float(model(**inputs,return_dict=True).logits.flatten()[0].float().item())
        torch.cuda.synchronize()
        assert math.isfinite(logit)
        windows.append({'pair_tokens':len(ids),'document_tokens':len(window),'logit':logit,'forward_seconds':time.perf_counter()-forward})
    return {'query_id':query_id,'id':ident,'query_sha256':text_sha(query_text),'document_sha256':text_sha(doc_text),
            'logit':max(w['logit'] for w in windows),'windows':windows,'query_tokens':len(query),'document_tokens':len(doc),
            'tokenize_seconds':tokenize,'score_seconds':time.perf_counter()-tick,'cache_reused':False}


with (HERE / 'pairs.jsonl').open('x',encoding='utf-8') as stream:
    count = 0
    for query_id in queries:
        for row in ranks[query_id][:20]:
            stream.write(json.dumps(score(query_id,row['id']))+'\n'); stream.flush(); count+=1
        print(f'quality {query_id}: {count} pairs',flush=True)
dump('quality-complete.json',{'pairs':count,'elapsed_seconds':time.monotonic()-started})

for case in [c['case_id'] for c in read(HERE / 'cases.json')]:
    for repeat in (1,2,3):
        for method in ('I02','R02','R04'):
            task_id = f'{case}-{method}-{repeat}'
            path = HERE / 'benchmark-requests' / (task_id+'.json')
            while not path.exists():
                if time.monotonic()-started > 1800:
                    raise TimeoutError('bounded benchmark handoff')
                time.sleep(.02)
            begin = time.perf_counter(); request = read(path)
            assert request['task_id'] == task_id and request['fresh_gpu_required'] is True
            rows = []
            for query_id,pool in zip(request['query_ids'],request['pools'],strict=True):
                assert [r['id'] for r in pool] == [r['id'] for r in ranks[query_id][:20]]
                rows.extend(score(query_id,row['id']) for row in pool)
            response = {'task_id':task_id,'worker_seconds':time.perf_counter()-begin,'pairs':rows}
            directory = HERE / 'benchmark-responses'; directory.mkdir(exist_ok=True)
            temp = directory / (task_id+'.tmp'); temp.write_text(json.dumps(response),encoding='utf-8')
            temp.rename(temp.with_suffix('.json'))
            print(f'GPU benchmark {task_id}: {response["worker_seconds"]:.3f}s',flush=True)
dump('gpu-complete.json',{'quality_pairs':count,'benchmark_requests':27,'elapsed_seconds':time.monotonic()-started})
