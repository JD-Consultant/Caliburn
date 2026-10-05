"""Cross-encoder MAX across the original work passages of one employee."""
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

HERE = Path('/experiment/passage-pool')
sys.path.insert(0,str(HERE.parent))
from evaluate import token_windows


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(8*1024*1024):
            h.update(block)
    return h.hexdigest()


start = time.monotonic()
execution = json.loads((HERE/'execution-manifest.json').read_text())
for name,digest in execution['sources'].items():
    assert sha(HERE/name) == digest,name
assert sha(HERE.parent/'cases-v4.json') == execution['cases_sha256']
assert sha(Path('/model/model.safetensors')) == execution['model_sha256']
prepared = json.loads((HERE/'prepared.json').read_text(encoding='utf-8'))
torch.set_num_threads(4)
tokenizer = AutoTokenizer.from_pretrained('/model',local_files_only=True,trust_remote_code=False)
tick = time.perf_counter()
model = AutoModelForSequenceClassification.from_pretrained('/model',local_files_only=True,
        trust_remote_code=False,dtype=torch.float16,attn_implementation='sdpa').to('cuda').eval()
torch.cuda.synchronize()
runtime = {'load_seconds':time.perf_counter()-tick,'gpu':torch.cuda.get_device_name(),
           'attention':model.config._attn_implementation,'batch_size':1,'max_pair_tokens':8192,
           'execution_manifest_sha256':sha(HERE/'execution-manifest.json'),
           'model_revision':'953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e'}
tick = time.perf_counter()
docs = {r['id']:tokenizer.encode(r['text'],add_special_tokens=False,truncation=False) for r in prepared['corpus']}
runtime['document_tokenize_seconds'] = time.perf_counter()-tick
queries = {}
tick = time.perf_counter()
for q in prepared['queries']:
    queries[q['case_id']] = [tokenizer.encode(t,add_special_tokens=False,truncation=False) for t in q['passages']]
runtime['query_tokenize_seconds'] = time.perf_counter()-tick
(HERE/'gpu-runtime.json').write_text(json.dumps(runtime,indent=2),encoding='utf-8')


def score(q,doc_id):
    if time.monotonic()-start > 2700:
        raise TimeoutError('45 minute model inference bound')
    begin = time.perf_counter()
    passages = []
    for index,query in enumerate(queries[q['case_id']],1):
        windows = []
        for window in token_windows(query,docs[doc_id],8192,overlap=64):
            ids = tokenizer.build_inputs_with_special_tokens(query,window)
            assert len(ids) <= 8192
            inputs = {'input_ids':torch.tensor([ids],device='cuda'),
                      'attention_mask':torch.ones((1,len(ids)),device='cuda',dtype=torch.long)}
            torch.cuda.synchronize(); tick = time.perf_counter()
            with torch.inference_mode():
                logit = float(model(**inputs,return_dict=True).logits.flatten()[0].float().item())
            torch.cuda.synchronize()
            windows.append({'pair_tokens':len(ids),'document_tokens':len(window),'logit':logit,
                            'forward_seconds':time.perf_counter()-tick})
        passages.append({'passage':index,'query_tokens':len(query),'windows':windows,
                         'logit':max(w['logit'] for w in windows)})
    logit = max(p['logit'] for p in passages)
    assert math.isfinite(logit)
    return {'id':doc_id,'logit':logit,'score':1/(1+math.exp(-logit)),'passages':passages,
            'document_tokens':len(docs[doc_id]),'pair_seconds':time.perf_counter()-begin}


score(prepared['queries'][0],prepared['queries'][0]['ranking'][0]['id'])
with (HERE/'rerank-pairs.jsonl').open('x',encoding='utf-8') as stream:
    for q in prepared['queries']:
        tick = time.perf_counter(); rows = []
        for index,r in enumerate(q['ranking'][:200],1):
            value = score(q,r['id']); value.update(dense_score=r['score'],dense_rank=index); rows.append(value)
        stream.write(json.dumps({'case_id':q['case_id'],'arm':q['arm'],'total_seconds':time.perf_counter()-tick,
                                 'pairs':rows},ensure_ascii=False)+'\n'); stream.flush()
        print(f"passage scores {q['case_id']}: 200 docs, {time.perf_counter()-tick:.2f}s",flush=True)
q = next(q for q in prepared['queries'] if q['case_id']=='E01')
with (HERE/'timings.jsonl').open('x',encoding='utf-8') as stream:
    for repeat in (1,2):
        for n in (20,50,100,200,805):
            tick = time.perf_counter()
            seconds = [score(q,r['id'])['pair_seconds'] for r in q['ranking'][:n]]
            value = {'case_id':q['case_id'],'arm':q['arm'],'repeat':repeat,'n':n,
                     'rerank_seconds':time.perf_counter()-tick,'pair_seconds':seconds}
            stream.write(json.dumps(value)+'\n'); stream.flush()
            print(f"passage timing {repeat} N={n}: {value['rerank_seconds']:.2f}s",flush=True)
(HERE/'gpu-complete.json').write_text(json.dumps({'employees':18,'candidate_documents':3600,
    'passage_document_pairs':sum(len(q['passages'])*200 for q in prepared['queries']),
    'elapsed_seconds':time.monotonic()-start,'finished_utc':time.time()}),encoding='utf-8')
