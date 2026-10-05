"""Network-disabled pinned cross-encoder; quality shared, timings fresh."""
import time,math,torch
from transformers import AutoTokenizer,AutoModelForSequenceClassification
from common import *
def main():
 check_manifest();assert sha(Path('/model/model.safetensors'))==MODEL_SHA
 torch.set_num_threads(4);started=time.monotonic();tokenizer=AutoTokenizer.from_pretrained('/model',local_files_only=True,trust_remote_code=False)
 tick=time.perf_counter();model=AutoModelForSequenceClassification.from_pretrained('/model',local_files_only=True,trust_remote_code=False,dtype=torch.float16,attn_implementation='sdpa').to('cuda').eval();torch.cuda.synchronize()
 dump('gpu-runtime.json',{'load_seconds':time.perf_counter()-tick,'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,'model_sha256':MODEL_SHA,'revision':'953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e','attention':model.config._attn_implementation,'max_pair_tokens':8192,'overlap':64,'batch_size':1,'network':'none'})
 queries={q['query_id']:q for q in read(HERE/'queries.json')};corpus={d['id']:d for d in read(HERE/'corpus.json')}
 def score(qid,ident):
  if time.monotonic()-started>3600:raise TimeoutError('bounded GPU run')
  at=time.perf_counter();qt=queries[qid]['text'];dt=corpus[ident]['text'];q=tokenizer.encode(qt,add_special_tokens=False,truncation=False);d=tokenizer.encode(dt,add_special_tokens=False,truncation=False);tok=time.perf_counter()-at;windows=[]
  for w in token_windows(q,d,8192,overlap=64):
   ids=tokenizer.build_inputs_with_special_tokens(q,w);assert len(ids)<=8192
   inp={'input_ids':torch.tensor([ids],device='cuda'),'attention_mask':torch.ones((1,len(ids)),device='cuda',dtype=torch.long)};torch.cuda.synchronize();tick=time.perf_counter()
   with torch.inference_mode():logit=float(model(**inp,return_dict=True).logits.flatten()[0].float().item())
   torch.cuda.synchronize();assert math.isfinite(logit);windows.append({'pair_tokens':len(ids),'document_tokens':len(w),'logit':logit,'forward_seconds':time.perf_counter()-tick})
  return {'query_id':qid,'id':ident,'query_sha256':text_sha(qt),'document_sha256':text_sha(dt),'logit':max(w['logit'] for w in windows),'windows':windows,'query_tokens':len(q),'document_tokens':len(d),'tokenize_seconds':tok,'score_seconds':time.perf_counter()-at,'cache_reused':False}
 def write(f,row):f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
 values={};pairs=read(HERE/'rerank-pair-inputs.json')
 with (HERE/'rerank-pairs.jsonl').open('x',encoding='utf-8') as out:
  for i,p in enumerate(pairs,1):
   row=score(p['query_id'],p['document_id']);write(out,row);values[(row['query_id'],row['id'])]=row
   if i%20==0:print(f'quality {i}/{len(pairs)} pairs',flush=True)
 dump('rerank-quality-complete.json',{'pairs':len(values),'elapsed_seconds':time.monotonic()-started})
 results=[];base=read(HERE/'results.json')
 for r in base:
  pools=[]
  for qid,pool in zip(r['query_ids'],r['query_pools'],strict=True):
   ranked=[{'id':p['id'],'score':values[(qid,p['id'])]['logit']} for p in pool];pools.append(sorted(ranked,key=lambda p:(-p['score'],p['id'])))
  merged=merge_pools(pools,r['query_ids']);results.append({**r,'method':r['method']+'-R','query_pools':pools,'merged_ranking':merged,'selected':merged[:5]})
 dump('rerank-results.json',results);print('rerank results ready',flush=True)
 # Controller requests each timed task after fresh DB retrieval. No cached score timing.
 with (HERE/'rerank-benchmark-pairs.jsonl').open('x',encoding='utf-8') as out:
  for index in range(144):
   request=HERE/'benchmark-requests'/f'{index:03}.json'
   while not request.exists():
    if time.monotonic()-started>3600:raise TimeoutError('benchmark handoff deadline')
    time.sleep(.02)
   req=read(request);at=time.perf_counter();lp=[]
   for qid,pool in zip(req['query_ids'],req['pools'],strict=True):
    ranked=[]
    for p in pool:
     row=score(qid,p['id']);write(out,{'task_id':req['task_id'],**row});ranked.append({'id':p['id'],'score':row['logit']})
    lp.append(sorted(ranked,key=lambda p:(-p['score'],p['id'])))
   merged=merge_pools(lp,req['query_ids']);answer={'task_id':req['task_id'],'gpu_seconds':time.perf_counter()-at,'selected_ids':[p['id'] for p in merged[:5]],'query_pools':lp}
   d=HERE/'benchmark-responses';d.mkdir(exist_ok=True);temp=d/f'{index:03}.tmp';temp.write_text(json.dumps(answer),encoding='utf-8');temp.rename(d/f'{index:03}.json')
   if (index+1)%12==0:print(f'fresh benchmark {index+1}/144',flush=True)
 dump('gpu-complete.json',{'quality_pairs':len(values),'fresh_benchmark_tasks':144,'elapsed_seconds':time.monotonic()-started})
if __name__=='__main__':main()
