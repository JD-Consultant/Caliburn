"""Actual pinned cross-encoder pair scores and bounded warm timing on one GPU."""
import hashlib
import json
import math
import time
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from evaluate import token_windows

HERE = Path('/experiment')
started = time.monotonic()
prepared = json.loads((HERE/'prepared.json').read_text(encoding='utf-8'))
metadata = json.loads((HERE/'model.json').read_text(encoding='utf-8'))
execution = json.loads((HERE/'execution-manifest.json').read_text(encoding='utf-8'))
for name,expected_sha in execution['sources'].items():
    assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == expected_sha, name
model_path = metadata['path']
tokenizer = AutoTokenizer.from_pretrained(model_path,local_files_only=True,trust_remote_code=False)
torch.set_num_threads(4)
load_started = time.perf_counter()
model = AutoModelForSequenceClassification.from_pretrained(model_path,local_files_only=True,
        trust_remote_code=False,dtype=torch.float16,attn_implementation='sdpa').to('cuda').eval()
torch.cuda.synchronize()
assert model.config.max_position_embeddings == 8194
assert torch.cuda.is_available()
device = torch.cuda.get_device_properties(0)
runtime = {'load_seconds':time.perf_counter()-load_started,'gpu':device.name,
           'gpu_bytes':device.total_memory,'dtype':str(next(model.parameters()).dtype),
           'attention':model.config._attn_implementation,'batch_size':1,'max_pair_tokens':8192,
           'prepared_sha256':hashlib.sha256((HERE/'prepared.json').read_bytes()).hexdigest(),
           'worker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'model_revision':metadata['revision'],'torch_version':torch.__version__,
           'execution_manifest_sha256':hashlib.sha256((HERE/'execution-manifest.json').read_bytes()).hexdigest()}
(HERE/'gpu-runtime.json').write_text(json.dumps(runtime,indent=2),encoding='utf-8')
corpus = {r['id']:r for r in prepared['corpus']}
prep_started = time.perf_counter()
doc_tokens = {k:tokenizer.encode(r['text'],add_special_tokens=False,truncation=False) for k,r in corpus.items()}
runtime['document_tokenize_seconds'] = time.perf_counter()-prep_started
query_tokens = {}
query_tokenize = []
for q in prepared['queries']:
    prep_started = time.perf_counter()
    query_tokens[(q['case_id'],q['arm'])] = tokenizer.encode(q['text'],add_special_tokens=False,truncation=False)
    query_tokenize.append({'case_id':q['case_id'],'arm':q['arm'],
                           'seconds':time.perf_counter()-prep_started})
runtime['query_tokenize'] = query_tokenize
runtime['protocol_amendment_sha256'] = hashlib.sha256((HERE/'protocol-amendment-01.md').read_bytes()).hexdigest()
(HERE/'gpu-runtime.json').write_text(json.dumps(runtime,indent=2),encoding='utf-8')


def score(q, doc_id):
    if time.monotonic()-started > 2700:
        raise TimeoutError('45 minute inference bound reached')
    query = query_tokens[(q['case_id'],q['arm'])]
    passage = doc_tokens[doc_id]
    windows = token_windows(query,passage,8192,overlap=64)
    output = []
    begin = time.perf_counter()
    for window in windows:
        ids = tokenizer.build_inputs_with_special_tokens(query,window)
        assert len(ids) <= 8192 and len(ids) == len(query)+len(window)+4
        inputs = {'input_ids':torch.tensor([ids],device='cuda'),
                  'attention_mask':torch.ones((1,len(ids)),device='cuda',dtype=torch.long)}
        torch.cuda.synchronize()
        tick = time.perf_counter()
        with torch.inference_mode():
            logit = float(model(**inputs,return_dict=True).logits.flatten()[0].float().item())
        torch.cuda.synchronize()
        output.append({'pair_tokens':len(ids),'passage_tokens':len(window),'logit':logit,
                       'forward_seconds':time.perf_counter()-tick})
    logit = max(w['logit'] for w in output)
    assert math.isfinite(logit)
    return {'id':doc_id,'logit':logit,'score':1/(1+math.exp(-logit)),
            'query_tokens':len(query),'document_tokens':len(passage),'windows':output,
            'pair_seconds':time.perf_counter()-begin}


# A real non-recorded warm-up; no result used for candidate selection.
score(prepared['queries'][0],prepared['queries'][0]['ranking'][0]['id'])
with (HERE/'rerank-pairs.jsonl').open('x',encoding='utf-8') as stream:
    for q in prepared['queries']:
        pool = q['ranking'][:200]
        begin = time.perf_counter()
        rows = []
        for index,r in enumerate(pool):
            result = score(q,r['id'])
            result['dense_score'] = r['score']
            result['dense_rank'] = index+1
            rows.append(result)
        record = {'case_id':q['case_id'],'arm':q['arm'],'candidate_count':len(rows),
                  'total_seconds':time.perf_counter()-begin,'pairs':rows}
        stream.write(json.dumps(record,ensure_ascii=False)+'\n')
        stream.flush()
        print(f"scores {q['case_id']} {q['arm']}: {len(rows)} docs, {record['total_seconds']:.2f}s",flush=True)

# Actual prefix reruns, not cumulative cached pair-time estimates; two warm samples.
bench = [q for q in prepared['queries'] if (q['case_id'],q['arm']) in [('E01','raw_employee'),('E04','B2')]]
with (HERE/'timings.jsonl').open('x',encoding='utf-8') as stream:
    for q in bench:
        for repeat in (1,2):
            for n in (20,50,100,200,805):
                begin = time.perf_counter()
                pair_times = []
                for r in q['ranking'][:n]:
                    pair_times.append(score(q,r['id'])['pair_seconds'])
                record = {'case_id':q['case_id'],'arm':q['arm'],'repeat':repeat,'n':n,
                          'rerank_seconds':time.perf_counter()-begin,'pair_seconds':pair_times}
                stream.write(json.dumps(record)+'\n')
                stream.flush()
                print(f"timing {q['case_id']} {q['arm']} repeat={repeat} N={n}: {record['rerank_seconds']:.2f}s",flush=True)
(HERE/'gpu-complete.json').write_text(json.dumps({'queries':len(prepared['queries']),
    'quality_pairs':len(prepared['queries'])*200,'timing_queries':len(bench)*2*5,
    'elapsed_seconds':time.monotonic()-started,'finished_utc':time.time()}),encoding='utf-8')
