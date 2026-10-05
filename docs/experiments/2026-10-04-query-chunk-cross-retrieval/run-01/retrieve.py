"""Cross frozen query granularity with frozen public granularity; real DB reads only."""
import sys
import time
import statistics
import numpy as np
from qdrant_client import QdrantClient,models
from pipeline import *
from fusion import merge_pools

sys.path.insert(0,str(PUBLIC))
from chunks import aggregate

def vectors():
    values={}
    for p in sorted((PUBLIC/'vector-batches').glob('*.npz')):
        z=np.load(p,allow_pickle=False)
        for h,v in zip(z['hashes'],z['dense'],strict=True):values[str(h)]=v
    assert len(values)==11064
    return values

def from_groups(groups,rows):
    hits=[]
    for g in groups:
        for p in g.hits:
            r=rows[int(p.id)]
            assert r['parent_id']==g.id==p.payload['parent_id'] and r['chunk_id']==p.payload['chunk_id']
            hits.append({'parent_id':r['parent_id'],'chunk_id':r['chunk_id'],'score':p.score})
    return hits

def selections(cases,queries,pools):
    result=[]
    for case in cases:
        for method,(variant,rep,agg) in METHODS.items():
            qs=[q for q in queries if q['case_id']==case['case_id'] and q['variant']==variant]
            local=[pools[(q['query_id'],rep,agg)] for q in qs]
            merged=merge_pools(local,[q['query_id'] for q in qs])
            result.append({'case_id':case['case_id'],'method':method,'variant':variant,'representation':rep,'aggregation':agg,
                           'query_ids':[q['query_id'] for q in qs],'query_pools':local,'merged_ranking':merged,
                           'union_parents':len({r['id'] for p in local for r in p}),'selected':merged[:5]})
    return result

def main():
    check_manifest();qs=read(HERE/'queries.json');qvectors={v['query_id']:v for v in read(HERE/'query-vectors.json')}
    cases=read(HERE/'cases.json');chunks=read(PUBLIC/'chunks.json');names=read(HERE/'collections.json');vs=vectors()
    rows={rep:[r for r in chunks if r['representation']==rep] for rep in names}
    mats={rep:np.asarray([vs[text_sha(r['text'])] for r in rr],dtype=np.float64) for rep,rr in rows.items()}
    for m in mats.values():m/=np.linalg.norm(m,axis=1,keepdims=True)
    db=QdrantClient(url='http://127.0.0.1:6335',timeout=120,trust_env=False)
    configs=[]
    for rep,name in names.items():
        info=db.get_collection(name);assert info.points_count==len(rows[rep])
        assert info.config.params.vectors['dense'].size==1024
        configs.append({'representation':rep,'name':name,'points':info.points_count,'configuration':info.model_dump(mode='json')})
    dump('database-reuse.json',configs)
    pools={};rankings=[];checks=[]
    for q in qs:
        v=np.asarray(qvectors[q['query_id']]['dense'],dtype=np.float64);v/=np.linalg.norm(v)
        for rep,name in names.items():
            scores=mats[rep]@v
            hits=[{'parent_id':r['parent_id'],'chunk_id':r['chunk_id'],'score':float(scores[i])} for i,r in enumerate(rows[rep])]
            allparents=aggregate(hits,'max',candidate_limit=805)
            start=time.perf_counter()
            groups=db.query_points_groups(name,query=v.tolist(),using='dense',group_by='parent_id',group_size=3,limit=20,
                                          with_payload=True,search_params=models.SearchParams(exact=True)).groups
            elapsed=time.perf_counter()-start;native=from_groups(groups,rows[rep]);actual=aggregate(native,'max')
            assert [p['id'] for p in actual]==[p['id'] for p in allparents[:20]],(q['query_id'],rep)
            error=0
            for a,e in zip(actual,allparents[:20],strict=True):
                assert len(a['top_chunks'])==len(e['top_chunks'])
                for x,y in zip(a['top_chunks'],e['top_chunks'],strict=True):error=max(error,abs(x['score']-y['score']))
            assert error<1e-6
            checks.append({'query_id':q['query_id'],'representation':rep,'seconds':elapsed,'max_error':error,'returned':actual})
            rankings.append({'query_id':q['query_id'],'representation':rep,'chunk_scores':hits,'parents':allparents})
            for agg in ('max','mean3') if rep!='document' else ('max',):
                pools[(q['query_id'],rep,agg)]=aggregate(hits,agg)
                assert [p['id'] for p in aggregate(native,agg)]==[p['id'] for p in pools[(q['query_id'],rep,agg)]]
        print('verified '+q['query_id'],flush=True)
    result=selections(cases,qs,pools)
    prior=read(PUBLIC/'results.json');controls=[]
    for r in result:
        if r['variant']=='whole':
            method={'Dmax':'D-max','Tmax':'T-max','Tmean3':'T-mean3','Umax':'U-max','Umean3':'U-mean3'}[r['method'][2:]]
            p=next(p for p in prior if p['case_id']==r['case_id'] and p['method']==method)
        elif r['method']=='S-Dmax':
            base=F if r['case_id'].startswith('F') else H
            p=next(p for p in read(base/'results.json') if p['case_id']==r['case_id'] and p['method']=='R03')
        else:continue
        assert [p['id'] for p in p['selected']]==[p['id'] for p in r['selected']],r['method']
        controls.append({'case_id':r['case_id'],'method':r['method'],'same_prior_top5':True})
    dump('all-rankings.json',rankings);dump('database-checks.json',checks);dump('results.json',result);dump('control-checks.json',controls)
    trials=[]
    for case in cases:
        for repeat in (1,2,3):
            for method,(variant,rep,agg) in METHODS.items():
                selected_qs=[q for q in qs if q['case_id']==case['case_id'] and q['variant']==variant]
                local=[];db_seconds=0;at=time.perf_counter()
                for q in selected_qs:
                    tick=time.perf_counter()
                    groups=db.query_points_groups(names[rep],query=qvectors[q['query_id']]['dense'],using='dense',
                              group_by='parent_id',group_size=3,limit=20,with_payload=True,search_params=models.SearchParams(exact=True)).groups
                    db_seconds+=time.perf_counter()-tick;local.append(aggregate(from_groups(groups,rows[rep]),agg))
                ranked=merge_pools(local,[q['query_id'] for q in selected_qs]);elapsed=time.perf_counter()-at
                expected=next(r for r in result if r['case_id']==case['case_id'] and r['method']==method)
                assert [r['id'] for r in ranked[:5]]==[r['id'] for r in expected['selected']]
                trials.append({'case_id':case['case_id'],'method':method,'repeat':repeat,'seconds':elapsed,'db_seconds':db_seconds,
                               'queries':len(selected_qs),'selected_ids':[r['id'] for r in ranked[:5]],'cached_query_embeddings':True})
    dump('benchmark.json',trials)
    dump('timing-summary.json',[{'case_id':c['case_id'],'method':m,
         'median_seconds':statistics.median(t['seconds'] for t in trials if t['case_id']==c['case_id'] and t['method']==m)} for c in cases for m in METHODS])
    db.close();print(f'90 native checks, {len(controls)} unchanged controls, {len(result)} groups, {len(trials)} warm trials',flush=True)

if __name__=='__main__':main()
