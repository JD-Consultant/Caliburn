"""Independent cosine, parent aggregation and RRF reconstruction; no provider."""
from collections import defaultdict
import numpy as np
from pipeline import *

def main():
    check_manifest()
    chunks=read(PUBLIC/'chunks.json');queries=read(HERE/'queries.json');qv=read(HERE/'query-vectors.json')
    vectors={}
    for p in sorted((PUBLIC/'vector-batches').glob('*.npz')):
        z=np.load(p,allow_pickle=False)
        for h,v in zip(z['hashes'],z['dense'],strict=True):vectors[str(h)]=v
    assert len(vectors)==11064 and len(queries)==len(qv)==30
    for q,v in zip(queries,qv,strict=True):assert q['query_id']==v['query_id'] and text_sha(q['text'])==v['text_sha256']
    results=read(HERE/'results.json');checks=read(HERE/'database-checks.json');bench=read(HERE/'benchmark.json')
    assert len(results)==80 and len(checks)==90 and len(bench)==240 and len(read(HERE/'control-checks.json'))==48
    pools={};cosines=0
    for rep in ('document','task','unit'):
        rows=[r for r in chunks if r['representation']==rep]
        assert len({r['parent_id'] for r in rows})==805
        mat=np.asarray([vectors[text_sha(r['text'])] for r in rows],dtype=np.float64)
        mat/=np.linalg.norm(mat,axis=1,keepdims=True)
        for v in qv:
            query=np.asarray(v['dense'],dtype=np.float64);query/=np.linalg.norm(query)
            scores=mat@query;groups=defaultdict(list);cosines+=len(scores)
            for r,score in zip(rows,scores,strict=True):groups[r['parent_id']].append((float(score),r['chunk_id']))
            tops={parent:sorted(hits,key=lambda x:(-x[0],x[1]))[:3] for parent,hits in groups.items()}
            candidates=sorted(tops,key=lambda p:(-tops[p][0][0],p))[:20]
            for agg in ('max','mean3') if rep!='document' else ('max',):
                scores={p:(tops[p][0][0] if agg=='max' else sum(h[0] for h in tops[p])/len(tops[p])) for p in candidates}
                pools[(v['query_id'],rep,agg)]=sorted(candidates,key=lambda p:(-scores[p],p))
    for r in results:
        variant,rep,agg=METHODS[r['method']]
        qs=[q for q in queries if q['case_id']==r['case_id'] and q['variant']==variant]
        lists=[pools[(q['query_id'],rep,agg)] for q in qs]
        assert len(qs)==len(r['query_pools'])
        for a,b in zip(lists,r['query_pools'],strict=True):assert a==[p['id'] for p in b]
        if len(lists)==1:ranked=lists[0]
        else:
            fused=defaultdict(float)
            for items in lists:
                for rank,parent in enumerate(items):fused[parent]+=1/(2+rank)
            ranked=sorted(fused,key=lambda p:(-fused[p],p))
            for p in r['merged_ranking']:assert abs(p['fusion_score']-fused[p['id']])<1e-12
        assert ranked==[p['id'] for p in r['merged_ranking']]
        assert ranked[:5]==[p['id'] for p in r['selected']] and len(set(ranked[:5]))==5
    actual={(r['case_id'],r['method']):r for r in results}
    for t in bench:
        assert t['cached_query_embeddings'] is True
        assert t['selected_ids']==[p['id'] for p in actual[(t['case_id'],t['method'])]['selected']]
        assert t['queries']==len(actual[(t['case_id'],t['method'])]['query_ids'])
    for key in actual:assert len([t for t in bench if (t['case_id'],t['method'])==key])==3
    docs={d['id']:d for d in read(HERE/'corpus.json')};cases={c['case_id']:c for c in read(HERE/'cases.json')}
    valid=set()
    for row in read(HERE/'graded-results.json'):
        for r in row['selected']:
            assert r['judgment'] is not None
            j=r['judgment'];c=cases[row['case_id']]
            validate_judgment(j['judgment'],c['employee_statement'],docs[r['id']]['text'])
            assert j['employee_sha256']==text_sha(c['employee_statement']) and j['document_sha256']==text_sha(docs[r['id']]['text'])
            valid.add((row['case_id'],r['id']))
    previous=[]
    paths=[EXP/name/'artifact-hashes.json' for name in ('2026-10-04-occupation-retrieval','2026-10-04-occupation-retrieval-generalization',
         '2026-10-04-retrieve-rerank','2026-10-04-retrieval-passage-quota','2026-10-04-retrieval-input-boundaries','2026-10-04-retrieval-reference-views')]
    paths += [F/'artifact-hashes.json',H/'artifact-hashes.json',PUBLIC/'artifact-hashes.json']
    for p in paths:
        sealed=read(p);entries=sealed['files'] if 'files' in sealed else sealed
        for name,item in entries.items():assert sha(p.parent/name)==(item if isinstance(item,str) else item['sha256']),name
        previous.append({'manifest':str(p.relative_to(ROOT)).replace('\\','/'),'files':len(entries)})
    protected=read(EXP/'2026-10-04-retrieval-reference-views/execution-manifest.json')['inputs']
    for name,item in protected.items():assert sha(ROOT/name)==item['sha256'],name
    dump('verification.json',{'passed':True,'queries':30,'parents':805,'cosines_recomputed':cosines,'native_checks':90,
        'unchanged_controls':48,'result_groups':80,'positions':400,'warm_trials':240,'valid_unique_pairs':len(valid),
        'previous_manifests':previous,'previous_unchanged_files':sum(r['files'] for r in previous),'protected_inputs':len(protected),
        'meaning':'mechanisms and literal evidence only; semantic grading and global recall not certified'})
    print(json.dumps(read(HERE/'verification.json'),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
