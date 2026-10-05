"""Network-disabled local model probe; exact full-corpus cosine, shared rerank pool."""
import gc
import hashlib
import importlib.metadata
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch
from FlagEmbedding import BGEM3FlagModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
PUBLIC = EXP / '2026-10-04-public-chunk-retrieval/run-01'
PRIOR = EXP / '2026-10-05-memory-public-unit-retrieval/run-01'
sys.path.insert(0, '/embedder')
from reranking import score_documents


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump(name, obj):
    with (HERE/name).open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    started = time.monotonic()
    torch.set_num_threads(4)
    def bound():
        if time.monotonic() - started > 900:
            raise TimeoutError('15 minute probe bound')
    manifest = read(HERE/'input-manifest.json')
    for rel, metadata in manifest.items():
        assert sha(EXP/rel) == metadata['sha256'], rel
    models = {str(p): {'sha256': sha(p), 'bytes': p.stat().st_size}
              for folder in ('/embedding', '/reranker') for p in sorted(Path(folder).iterdir()) if p.is_file()}
    assert models['/reranker/model.safetensors']['sha256'] == 'd9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286'
    dump('runtime.json', {'network': 'none', 'gpu': torch.cuda.get_device_name(), 'models': models,
        'packages': {n: importlib.metadata.version(n) for n in ('torch','transformers','FlagEmbedding')},
        'embedding_model': 'BAAI/bge-m3', 'embedding_revision': '5617a9f61b028005a4858fdac845db406aefb181',
        'reranker_model': 'BAAI/bge-reranker-v2-m3', 'reranker_revision': '953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e',
        'dim': 1024, 'fp16': True, 'batch_size': 1, 'max_length': 8192})
    queries, cases = read(HERE/'queries.json'), read(HERE/'cases.json')
    corpus = {d['id']: d for d in read(PRIOR/'corpus.json')}
    chunks = [c for c in read(PUBLIC/'chunks.json') if c['representation'] in ('document','task')]
    assert len(corpus) == 805
    assert sum(c['representation']=='document' for c in chunks) == 805
    assert sum(c['representation']=='task' for c in chunks) == 8068
    cached = {}
    for path in sorted((PUBLIC/'vector-batches').glob('*.npz')):
        with np.load(path, allow_pickle=False) as z:
            cached.update({str(h): v for h,v in zip(z['hashes'], z['dense'], strict=True)})
    matrices, rows = {}, {}
    for rep in ('document','task'):
        rows[rep] = [c for c in chunks if c['representation']==rep]
        matrix = np.asarray([cached[hashlib.sha256(c['text'].encode()).hexdigest()] for c in rows[rep]],dtype=np.float64)
        matrices[rep] = matrix / np.linalg.norm(matrix,axis=1,keepdims=True)
    embedder = BGEM3FlagModel('/embedding', use_fp16=True, devices='cuda')
    control = next(q for q in read(PRIOR/'queries.json') if q['query_id']=='F01-whole-1')
    old_vector = next(q['dense'] for q in read(PRIOR/'query-vectors.json') if q['query_id']==control['query_id'])
    texts = list(dict.fromkeys([control['text']] + [q['text'] for q in queries]))
    vectors = {}
    for i,text in enumerate(texts,1):
        bound()
        tokens = len(embedder.tokenizer.encode(text))
        assert 0 < tokens <= 8192
        v = np.asarray(embedder.encode([text], batch_size=1, max_length=8192, return_dense=True,
            return_sparse=False, return_colbert_vecs=False)['dense_vecs'][0],dtype=np.float64)
        assert v.shape==(1024,) and np.isfinite(v).all()
        vectors[text] = v
        print(f'embed {i}/{len(texts)}',flush=True)
    error = float(np.max(np.abs(vectors[control['text']] - np.asarray(old_vector))))
    dump('embedding-control.json', {'query_id':control['query_id'],'max_absolute_error':error,'tolerance':.001})
    assert error <= .001
    dump('query-vectors.json', [{**q,'dense':vectors[q['text']].tolist()} for q in queries])
    del embedder
    gc.collect(); torch.cuda.empty_cache()
    all_rankings, retrieval = [], {}
    for q in queries:
        v = vectors[q['text']] / np.linalg.norm(vectors[q['text']])
        ids = set()
        probe = next(c for c in cases if c['case_id']==q['case_id'])
        for rep in ('document','task'):
            scores = matrices[rep] @ v
            maxima = {}
            for chunk,score in zip(rows[rep],scores,strict=True):
                ident = chunk['parent_id']
                maxima[ident] = max(maxima.get(ident,-math.inf),float(score))
            parents = [{'id':ident,'score':value,'rank':i} for i,(ident,value) in enumerate(sorted(maxima.items(),key=lambda kv:(-kv[1],kv[0])),1)]
            ids.update(r['id'] for r in parents[:20])
            item = {'query_id':q['query_id'],'representation':rep,'parents':parents}
            if rep=='task':
                ordered = sorted(zip(rows[rep],scores,strict=True),key=lambda cs:(-float(cs[1]),cs[0]['chunk_id']))
                cr, sc, rank = next((c,s,i) for i,(c,s) in enumerate(ordered,1) if c['chunk_id']==probe['probe_chunk'])
                item['probe_chunk'] = {'chunk_id':cr['chunk_id'],'text':cr['text'],'score':float(sc),'rank':rank,'population':len(ordered)}
            all_rankings.append(item)
        retrieval[q['query_id']] = sorted(ids)
    dump('all-rankings.json',all_rankings)
    dump('candidate-pools.json',retrieval)
    tokenizer = AutoTokenizer.from_pretrained('/reranker',local_files_only=True,trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained('/reranker',local_files_only=True,
        trust_remote_code=False,torch_dtype=torch.float16,attn_implementation='sdpa').to('cuda').eval()
    def encode(text):
        return tokenizer.encode(text,add_special_tokens=False,truncation=False)
    def score(query,document):
        bound()
        tokens = tokenizer.build_inputs_with_special_tokens(query,document)
        assert len(tokens)<=8192
        inp = {'input_ids':torch.tensor([tokens],device='cuda'),
               'attention_mask':torch.ones((1,len(tokens)),device='cuda',dtype=torch.long)}
        with torch.inference_mode():
            logit = float(model(**inp,return_dict=True).logits.flatten()[0].float().item())
        assert math.isfinite(logit)
        return logit
    results, cache, total = [], {}, 0
    with (HERE/'rerank-pairs.jsonl').open('x',encoding='utf-8') as stream:
        for case in cases:
            own = [q for q in queries if q['case_id']==case['case_id']]
            pool = sorted({case['primary'],case['probe']} | {ident for q in own for ident in retrieval[q['query_id']]})
            for q in own:
                ranked=[]
                for ident in pool:
                    key=(q['text_sha256'],ident)
                    reused = key in cache
                    if not reused:
                        cache[key]=score_documents(q['text'],[corpus[ident]['text']],encode=encode,pair_score=score)[0]
                        total+=1
                    row={'query_id':q['query_id'],'id':ident,'logit':cache[key],'cache_reused':reused}
                    stream.write(json.dumps(row)+'\n');stream.flush()
                    ranked.append({'id':ident,'title':corpus[ident]['title'],'score':cache[key]})
                ranked.sort(key=lambda r:(-r['score'],r['id']))
                actual=[r for r in ranked if r['id'] in retrieval[q['query_id']]]
                results.append({'query_id':q['query_id'],'common_pool_ranking':ranked,'own_pool_ranking':actual,'selected':actual[:5]})
                print(f'rerank {q["query_id"]} common={len(pool)}, own={len(actual)}, fresh_total={total}',flush=True)
    dump('results.json',results)
    for rel, metadata in manifest.items():
        assert sha(EXP/rel) == metadata['sha256'], rel
    dump('complete.json',{'queries':len(queries),'fresh_embedding_texts':len(texts),
        'fresh_rerank_pairs':total,'paid_llm_calls':0,'external_provider_calls':0,
        'elapsed_seconds':time.monotonic()-started,'inputs_unchanged':True})


if __name__=='__main__':
    main()
