"""Actual cached-vector DB HTTP + fresh tokenize/GPU + file handoff + merge."""
import statistics
import time
from qdrant_client import QdrantClient,models
from support import *

def make_plan():
    requests = [{'request_id':f'{case}-{variant}-{repeat}','case_id':case,'variant':variant,'repeat':repeat,
                 'config':CONFIGS[1]} for case in ('E01','M04') for variant in VARIANTS for repeat in (1,2)]
    for folder in ('benchmark-requests','benchmark-responses'):
        (HERE/folder).mkdir(exist_ok=False)
    dump('benchmark-plan.json',{'input_manifest_sha256':sha(HERE/'input-manifest.json'),'requests':requests,
          'scope':'Warm cached embeddings, actual DB/tokenization/GPU/file handoff/merge; no parameter selection'})

def run():
    plan = read(HERE/'benchmark-plan.json')
    assert sha(HERE/'input-manifest.json')==plan['input_manifest_sha256']
    prepared = read(HERE/'prepared.json'); corpus = prepared['corpus']
    queries = {(q['case_id'],q['variant']):q for q in prepared['queries']}
    vectors = {r['text_sha256']:r['dense'] for r in lines(HERE/'all-passage-cache.jsonl')}
    tasks = list(plan['requests'])
    tasks += [{**t,'request_id':t['request_id']+'-dense','config':CONFIGS[0]} for t in plan['requests']]
    db = QdrantClient(url='http://127.0.0.1:6335',timeout=60,trust_env=False)
    with (HERE/'benchmark-results.jsonl').open('x',encoding='utf-8') as stream:
        try:
            for task in tasks:
                q = queries[(task['case_id'],task['variant'])]; start = time.perf_counter()
                pools,searches = [],[]
                for index,text in enumerate(q['passages'],1):
                    tick = time.perf_counter()
                    points = db.query_points(COLLECTION,query=vectors[text_sha(text)],using='dense',limit=20,
                      with_payload=True,search_params=models.SearchParams(exact=True)).points
                    elapsed = time.perf_counter()-tick
                    returned = [{'id':p.payload['ocs_code'],'point_id':str(p.id),'score':p.score} for p in points]
                    search = {'passage':index,'limit':20,'exact':True,'seconds':elapsed,'returned':returned}
                    check_native(q,search)
                    searches.append(search); pools.append(returned)
                response = None; scores = {}; handoff = 0
                if task['config']['method']=='quota_rerank':
                    wanted = {(p,r['id']) for p,pool in enumerate(pools,1) for r in pool}
                    tick = time.perf_counter()
                    temp = HERE/'benchmark-requests'/f'{task["request_id"]}.tmp'
                    temp.write_text(json.dumps({**task,'pairs':[{'passage':p,'id':ident} for p,ident in sorted(wanted)]}),encoding='utf-8')
                    temp.rename(temp.with_suffix('.json'))
                    path = HERE/'benchmark-responses'/f'{task["request_id"]}.json'
                    while not path.exists():
                        if time.perf_counter()-tick>600:
                            raise TimeoutError('bounded benchmark response')
                        time.sleep(.02)
                    response = read(path); handoff = time.perf_counter()-tick
                    assert response['request_id']==task['request_id']
                    assert {(r['passage'],r['id']) for r in response['pairs']}==wanted
                    scores = {(r['passage'],r['id']):r['logit'] for r in response['pairs']}
                tick = time.perf_counter()
                selected = per_passage(pools,scores,20,5,response is not None)
                merge = time.perf_counter()-tick; total = time.perf_counter()-start
                record = {**task,'total_seconds':total,'database_seconds':sum(s['seconds'] for s in searches),
                    'handoff_seconds':handoff,'worker_seconds':response['worker_seconds'] if response else 0,
                    'tokenize_seconds':response['tokenize_seconds'] if response else 0,
                    'file_transport_overhead_seconds':max(0,handoff-response['worker_seconds']) if response else 0,
                    'merge_seconds':merge,'query_count':len(q['passages']),'pair_comparisons':len(scores),
                    'database_searches':searches,'selected_ids':[r['id'] for r in selected],
                    'characters':sum(len(d['text']) for d in corpus if d['id'] in {r['id'] for r in selected})}
                stream.write(json.dumps(record)+'\n'); stream.flush()
                print(f"{task['request_id']} {total:.3f}s {len(scores)} pairs {len(selected)} docs",flush=True)
        finally:
            db.close()
    rows = lines(HERE/'benchmark-results.jsonl')
    groups = []
    for case in ('E01','M04'):
        for variant in VARIANTS:
            for config in CONFIGS:
                chosen = [r for r in rows if r['case_id']==case and r['variant']==variant and r['config']==config]
                assert len(chosen)==2
                groups.append({'case_id':case,'variant':variant,'config':config,
                    'samples_seconds':[r['total_seconds'] for r in chosen],
                    'median_total_seconds':statistics.median(r['total_seconds'] for r in chosen),
                    'median_database_seconds':statistics.median(r['database_seconds'] for r in chosen),
                    'median_worker_seconds':statistics.median(r['worker_seconds'] for r in chosen),
                    'median_tokenize_seconds':statistics.median(r['tokenize_seconds'] for r in chosen),
                    'median_file_transport_overhead_seconds':statistics.median(r['file_transport_overhead_seconds'] for r in chosen),
                    'query_counts':[r['query_count'] for r in chosen],'pair_counts':[r['pair_comparisons'] for r in chosen],
                    'returned_counts':[len(r['selected_ids']) for r in chosen]})
    dump('timing-summary.json',groups)

if __name__=='__main__':
    make_plan() if sys.argv[1]=='plan' else run()
