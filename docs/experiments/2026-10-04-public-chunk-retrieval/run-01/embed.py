"""Hash-identical old vectors, then bounded batches of new public chunk vectors."""
import time
import numpy as np
import httpx
from pipeline import *

def main():
    check_manifest();rows=read(HERE/'chunks.json');texts={text_sha(r['text']):r['text'] for r in rows}
    cached={}
    with CACHE.open(encoding='utf-8') as s:
        for line in s:
            r=json.loads(line)
            if r['text_sha256'] in texts:cached[r['text_sha256']]=(r['embedding']['dense'],r.get('tokens'))
    output=HERE/'vector-batches';output.mkdir(exist_ok=True)
    mapping={};records=[];started=time.perf_counter()
    with httpx.Client(base_url='http://127.0.0.1:8082',timeout=300,trust_env=False) as client:
        runtime=client.get('/runtime').raise_for_status().json()
        assert runtime==read(H/'embedding-runtime.json');dump('embedding-runtime.json',runtime)
        # No new embedding for old document or exact duplicate chunk text.
        items=sorted(texts)
        for bi,start in enumerate(range(0,len(items),32)):
            hashes=items[start:start+32];batch=[];fresh=[h for h in hashes if h not in cached]
            tokenmap={};generated={};elapsed=0;token_elapsed=0
            if fresh:
                tick=time.perf_counter()
                tokens=client.post('/token-lengths',json={'texts':[texts[h] for h in fresh]}).raise_for_status().json()['lengths']
                token_elapsed=time.perf_counter()-tick
                assert all(0<t<=8192 for t in tokens),(bi,max(tokens))
                tokenmap=dict(zip(fresh,tokens,strict=True));tick=time.perf_counter()
                embeds=client.post('/embed',json={'texts':[texts[h] for h in fresh]}).raise_for_status().json()['embeddings']
                elapsed=time.perf_counter()-tick
                generated=dict(zip(fresh,[r['dense'] for r in embeds],strict=True))
            for ri,h in enumerate(hashes):
                raw=cached[h][0] if h in cached else generated[h]
                v=np.asarray(raw,dtype=np.float64);assert v.shape==(1024,) and np.isfinite(v).all()
                v/=np.linalg.norm(v);batch.append(v.astype(np.float32))
                mapping[h]={'batch':bi,'row':ri,'cache_reused':h in cached,'tokens':cached[h][1] if h in cached else tokenmap[h]}
            p=output/f'{bi:04d}.npz'
            if p.exists():raise ValueError('batch already exists')
            np.savez_compressed(p,hashes=np.asarray(hashes),dense=np.asarray(batch))
            record={'batch':bi,'texts':len(hashes),'fresh':len(fresh),'cached':len(hashes)-len(fresh),
                    'embed_seconds':elapsed,'token_seconds':token_elapsed,'path':str(p.relative_to(HERE)).replace('\\','/'),'sha256':sha(p)}
            records.append(record)
            with (HERE/'embedding-batches.jsonl').open('a',encoding='utf-8') as s:s.write(json.dumps(record)+'\n')
            if bi%20==0:print(f'embedding {start+len(hashes)}/{len(items)} unique texts',flush=True)
    dump('vector-map.json',mapping)
    dump('embedding-complete.json',{'unique_texts':len(mapping),'fresh':sum(r['fresh'] for r in records),
                                  'cached':sum(r['cached'] for r in records),'batches':len(records),
                                  'embed_seconds':sum(r['embed_seconds'] for r in records),'elapsed_seconds':time.perf_counter()-started,
                                  'fresh_token_max':max(r['tokens'] for r in mapping.values() if not r['cache_reused'])})
    print(json.dumps(read(HERE/'embedding-complete.json')),flush=True)

if __name__=='__main__':main()
