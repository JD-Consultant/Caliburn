"""Real Qdrant parent grouping, independently checked against every chunk cosine."""
import time
import statistics
import uuid
import numpy as np
from qdrant_client import QdrantClient,models
from pipeline import *
from chunks import aggregate

def load_vectors():
    result={}
    for p in sorted((HERE/'vector-batches').glob('*.npz')):
        z=np.load(p,allow_pickle=False)
        for h,v in zip(z['hashes'],z['dense'],strict=True):result[str(h)]=v
    assert len(result)==read(HERE/'embedding-complete.json')['unique_texts']
    return result

def native_rows(groups,lookup):
    rows=[]
    for group in groups:
        for p in group.hits:
            r=lookup[int(p.id)]
            assert p.payload['parent_id']==r['parent_id']==group.id
            rows.append({'parent_id':r['parent_id'],'chunk_id':r['chunk_id'],'score':p.score})
    return rows

def main():
    check_manifest();chunks=read(HERE/'chunks.json');vectors=load_vectors()
    queries=read(HERE/'query-vectors.json');db=QdrantClient(url='http://127.0.0.1:6335',timeout=120,trust_env=False)
    names={rep:'ocs_chunk_'+rep+'_'+uuid.uuid4().hex for rep in ('document','task','unit')}
    dump('collections.json',names);poolrows={};matrices={};build=[]
    for rep,name in names.items():
        rows=[r for r in chunks if r['representation']==rep];poolrows[rep]=rows
        matrices[rep]=np.asarray([vectors[text_sha(r['text'])] for r in rows],dtype=np.float64)
        matrices[rep]/=np.linalg.norm(matrices[rep],axis=1,keepdims=True)
        started=time.perf_counter()
        db.create_collection(name,vectors_config={'dense':models.VectorParams(size=1024,distance=models.Distance.COSINE)},
                             optimizers_config=models.OptimizersConfigDiff(indexing_threshold=1))
        db.create_payload_index(name,'parent_id',models.PayloadSchemaType.KEYWORD,wait=True)
        for offset in range(0,len(rows),64):
            points=[models.PointStruct(id=i,vector={'dense':matrices[rep][i].tolist()},
                     payload={'parent_id':rows[i]['parent_id'],'chunk_id':rows[i]['chunk_id'],'kind':rows[i]['kind']})
                    for i in range(offset,min(offset+64,len(rows)))]
            db.upsert(name,points,wait=True)
        info=db.get_collection(name)
        assert info.points_count==len(rows)
        build.append({'representation':rep,'points':len(rows),'seconds':time.perf_counter()-started,
                      'collection':name,'configuration':info.model_dump(mode='json')})
        print(f'indexed {rep}: {len(rows)} points',flush=True)
    dump('index-build.json',build)
    results=[];checks=[];ranks=[]
    for q in queries:
        qv=np.asarray(q['dense'],dtype=np.float64);qv/=np.linalg.norm(qv)
        for rep,name in names.items():
            rows=poolrows[rep];scores=matrices[rep]@qv
            hits=[{'parent_id':r['parent_id'],'chunk_id':r['chunk_id'],'score':float(scores[i])} for i,r in enumerate(rows)]
            offline=aggregate(hits,'max',candidate_limit=805)
            ranks.append({'case_id':q['query_id'],'representation':rep,'chunk_scores':hits,'parents':offline})
            tick=time.perf_counter()
            groups=db.query_points_groups(name,query=qv.tolist(),using='dense',group_by='parent_id',group_size=3,
                                          limit=20,with_payload=True,search_params=models.SearchParams(exact=True)).groups
            seconds=time.perf_counter()-tick;native=native_rows(groups,rows)
            actual=aggregate(native,'max')
            expected=offline[:20]
            assert [r['id'] for r in actual]==[r['id'] for r in expected],(q['query_id'],rep)
            max_error=0
            for a,e in zip(actual,expected,strict=True):
                assert len(a['top_chunks'])==len(e['top_chunks'])
                # Tied chunk vectors may have different internal IDs; score ordering is the contract.
                for ah,eh in zip(a['top_chunks'],e['top_chunks'],strict=True):
                    max_error=max(max_error,abs(ah['score']-eh['score']))
            assert max_error<1e-6,max_error
            checks.append({'case_id':q['query_id'],'representation':rep,'exact':True,'seconds':seconds,
                           'groups':20,'max_error':max_error,'returned':actual})
            for method,(mrep,agg) in METHODS.items():
                if rep!=mrep:continue
                ranked=aggregate(hits,agg)
                selected=ranked[:5]
                # Parent ordering also independently agrees after native top3 reordering.
                native_rank=aggregate(native,agg)
                assert [r['id'] for r in selected]==[r['id'] for r in native_rank[:5]]
                results.append({'case_id':q['query_id'],'method':method,'representation':rep,'aggregation':agg,
                                'candidate_parents':[r['id'] for r in expected],
                                'selected':selected})
        print('verified '+q['query_id'],flush=True)
    dump('all-rankings.json',ranks);dump('database-checks.json',checks);dump('results.json',results)
    # Warm all collections and code before timed trials.
    trials=[]
    for q in queries:
        for repeat in (1,2,3):
            for method,(rep,agg) in METHODS.items():
                tick=time.perf_counter()
                groups=db.query_points_groups(names[rep],query=q['dense'],using='dense',group_by='parent_id',group_size=3,
                                              limit=20,with_payload=True,search_params=models.SearchParams(exact=True)).groups
                db_seconds=time.perf_counter()-tick;at=time.perf_counter()
                selected=aggregate(native_rows(groups,poolrows[rep]),agg)[:5]
                merge_seconds=time.perf_counter()-at;total=time.perf_counter()-tick
                expected=next(r for r in results if r['case_id']==q['query_id'] and r['method']==method)
                assert [r['id'] for r in selected]==[r['id'] for r in expected['selected']]
                trials.append({'case_id':q['query_id'],'method':method,'repeat':repeat,'db_seconds':db_seconds,
                               'merge_seconds':merge_seconds,'seconds':total,'selected':selected,'cached_query_embedding':True})
    dump('benchmark.json',trials)
    dump('timing-summary.json',[{'case_id':q['query_id'],'method':method,
            'median_seconds':statistics.median(r['seconds'] for r in trials if r['case_id']==q['query_id'] and r['method']==method)}
            for q in queries for method in METHODS])
    db.close();print(f'{len(results)} result groups, {len(trials)} warm trials',flush=True)

if __name__=='__main__':main()
