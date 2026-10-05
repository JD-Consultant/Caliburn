"""Independent reconstruction from saved sources/vectors; no provider calls."""
from collections import defaultdict
import numpy as np
from pipeline import *

def main():
    check_manifest();chunks=read(HERE/'chunks.json');queries=read(HERE/'queries.json');qv=read(HERE/'query-vectors.json')
    vectors={}
    for p in sorted((HERE/'vector-batches').glob('*.npz')):
        z=np.load(p,allow_pickle=False)
        for h,v in zip(z['hashes'],z['dense'],strict=True):vectors[str(h)]=v
    assert len(vectors)==11064
    assert len(queries)==len(qv)==8
    for q,v in zip(queries,qv,strict=True):assert q['query_id']==v['query_id'] and text_sha(q['text'])==v['text_sha256']
    results=read(HERE/'results.json');checks=read(HERE/'database-checks.json');bench=read(HERE/'benchmark.json')
    assert len(results)==40 and len(checks)==24 and len(bench)==120
    actual={(r['case_id'],r['method']):r for r in results}
    for rep in ('document','task','unit'):
        selected=[r for r in chunks if r['representation']==rep]
        assert len({r['parent_id'] for r in selected})==805
        mat=np.asarray([vectors[text_sha(r['text'])] for r in selected],dtype=np.float64)
        mat/=np.linalg.norm(mat,axis=1,keepdims=True)
        for v in qv:
            query=np.asarray(v['dense'],dtype=np.float64);query/=np.linalg.norm(query)
            scores=mat@query;groups=defaultdict(list)
            for r,score in zip(selected,scores,strict=True):groups[r['parent_id']].append((float(score),r['chunk_id']))
            tops={parent:sorted(hits,key=lambda x:(-x[0],x[1]))[:3] for parent,hits in groups.items()}
            pool=sorted(tops,key=lambda parent:(-tops[parent][0][0],parent))[:20]
            for method,(representation,agg) in METHODS.items():
                if representation!=rep:continue
                parent_score={p:(tops[p][0][0] if agg=='max' else sum(h[0] for h in tops[p])/len(tops[p])) for p in pool}
                rank=sorted(pool,key=lambda p:(-parent_score[p],p))[:5]
                a=actual[(v['query_id'],method)]
                assert a['candidate_parents']==pool
                assert [r['id'] for r in a['selected']]==rank
                assert len(set(rank))==5
                for r in a['selected']:assert abs(r['score']-parent_score[r['id']])<1e-12
    for t in bench:
        assert t['cached_query_embedding'] is True
        assert [r['id'] for r in t['selected']]==[r['id'] for r in actual[(t['case_id'],t['method'])]['selected']]
    for case in [q['case_id'] for q in queries]:
        for m in METHODS:assert len([t for t in bench if t['case_id']==case and t['method']==m])==3
    docs={d['id']:d for d in read(HERE/'corpus.json')};cases={c['case_id']:c for c in read(HERE/'cases.json')}
    valid=[]
    for row in read(HERE/'graded-results.json'):
        for r in row['selected']:
            if r['judgment'] is None:continue
            j=r['judgment'];c=cases[row['case_id']]
            validate_judgment(j['judgment'],c['employee_statement'],docs[r['id']]['text'])
            assert j['employee_sha256']==text_sha(c['employee_statement'])
            assert j['document_sha256']==text_sha(docs[r['id']]['text'])
            valid.append((row['case_id'],r['id']))
    previous=[];errors=[]
    paths=[EXP/name/'artifact-hashes.json' for name in ('2026-10-04-occupation-retrieval','2026-10-04-occupation-retrieval-generalization',
         '2026-10-04-retrieve-rerank','2026-10-04-retrieval-passage-quota','2026-10-04-retrieval-input-boundaries','2026-10-04-retrieval-reference-views')]
    paths += [F/'artifact-hashes.json',H/'artifact-hashes.json']
    for p in paths:
        count=0
        sealed=read(p)
        entries=sealed['files'] if 'files' in sealed else sealed
        for name,item in entries.items():
            target=p.parent/name
            expected=item if isinstance(item,str) else item['sha256']
            if not target.is_file() or sha(target)!=expected:errors.append(str(target))
            count+=1
        previous.append({'manifest':str(p.relative_to(ROOT)).replace('\\','/'),'files':count})
    assert not errors,errors
    dump('verification.json',{'passed':True,'queries':8,'parents':805,'representations':3,'native_checks':24,
        'result_groups':40,'positions':200,'warm_trials':120,'valid_unique_pairs':len(set(valid)),
        'previous_manifests':previous,'previous_unchanged_files':sum(r['files'] for r in previous),
        'meaning':'mechanisms and literal evidence only; semantic grading and global recall not certified'})
    print(json.dumps(read(HERE/'verification.json'),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
