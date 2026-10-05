"""Actual local DB HTTP + file handoff + fresh tokenization + GPU + merge time."""
import time
from qdrant_client import QdrantClient,models
from common import *

def make_plan():
    selected = read(HERE/'selection-development.json')['chosen']
    requests = []
    for case in ('E01','M04'):
        for s in selected.values():
            if s and s['method'].endswith('rerank'):
                for repeat in (1,2):
                    requests.append({'request_id':f'{case}-{s["method"]}-{repeat}','case_id':case,'repeat':repeat,
                                     'config':{k:s[k] for k in ('method','n','k')}})
    for repeat in (1,2):
        requests.append({'request_id':f'E01-full-{repeat}','case_id':'E01','repeat':repeat,
                         'config':{'method':'full_rerank','n':805,'k':805}})
    for folder in ('benchmark-requests','benchmark-responses'):
        (HERE/folder).mkdir(exist_ok=False)
    dump('benchmark-plan.json',{'selection_sha256':sha(HERE/'selection-development.json'),'requests':requests,
                              'selected_case_ids':['E01','M04'],'repeats':2,'quality_cases_not_used_for_tuning':True})

def run():
    plan = read(HERE/'benchmark-plan.json')
    assert sha(HERE/'selection-development.json')==plan['selection_sha256']
    prepared = read(HERE/'prepared-development.json')
    by_case = {q['case_id']:q for q in prepared['queries']}
    vectors = {r['text_sha256']:r['dense'] for r in lines(OLD/'passage-pool/passage-cache.jsonl')}
    corpus = prepared['corpus']
    selected = read(HERE/'selection-development.json')['chosen']
    tasks = list(plan['requests'])
    for case in ('E01','M04'):
        for s in selected.values():
            if s and s['method'].endswith('dense'):
                for repeat in (1,2):
                    tasks.append({'request_id':f'{case}-{s["method"]}-{repeat}','case_id':case,'repeat':repeat,
                                  'config':{k:s[k] for k in ('method','n','k')}})
    db = QdrantClient(url='http://127.0.0.1:6335',timeout=60,trust_env=False)
    with (HERE/'benchmark-results.jsonl').open('x',encoding='utf-8') as stream:
        try:
            for task in tasks:
                config = task['config']; q = by_case[task['case_id']]
                start = time.perf_counter(); searches = []
                if config['method']=='full_rerank':
                    candidate = q
                    wanted = {(i,d['id']) for i in range(1,len(q['passages'])+1) for d in corpus}
                else:
                    pools = []
                    for i,text in enumerate(q['passages'],1):
                        tick = time.perf_counter()
                        points = db.query_points(COLLECTION,query=vectors[text_sha(text)],using='dense',limit=config['n'],
                           with_payload=True,search_params=models.SearchParams(exact=True)).points
                        elapsed = time.perf_counter()-tick
                        rows = [{'id':p.payload['ocs_code'],'point_id':str(p.id),'score':p.score} for p in points]
                        assert [r['id'] for r in rows]==[r['id'] for r in q['pools'][i-1][:config['n']]]
                        assert max(abs(a['score']-b['score']) for a,b in zip(rows,q['pools'][i-1]))<1e-6
                        searches.append({'passage':i,'seconds':elapsed,'limit':config['n'],'returned':rows,'exact':True})
                        pools.append(rows)
                    maximum = {}
                    for pool in pools:
                        for r in pool:
                            maximum[r['id']] = max(maximum.get(r['id'],-float('inf')),r['score'])
                    candidate = {**q,'pools':pools,'global_pool':sorted(({'id':k,'score':v} for k,v in maximum.items()),key=lambda r:(-r['score'],r['id']))}
                    wanted = required(candidate,config)
                result = None; pair_scores = {}; handoff = 0
                if wanted:
                    request = {**task,'pairs':[{'passage':i,'id':d} for i,d in sorted(wanted)]}
                    tick = time.perf_counter()
                    temporary = HERE/'benchmark-requests'/f'{task["request_id"]}.tmp'
                    temporary.write_text(json.dumps(request),encoding='utf-8'); temporary.rename(temporary.with_suffix('.json'))
                    response = HERE/'benchmark-responses'/f'{task["request_id"]}.json'
                    while not response.exists():
                        if time.perf_counter()-tick>600:
                            raise TimeoutError('bounded benchmark worker response')
                        time.sleep(.02)
                    result = read(response); handoff = time.perf_counter()-tick
                    assert {(r['passage'],r['id']) for r in result['pairs']}==wanted
                    pair_scores = {(r['passage'],r['id']):r['logit'] for r in result['pairs']}
                tick = time.perf_counter()
                output = global_selection(candidate['pools'],pair_scores,805,805,True) if config['method']=='full_rerank' else select(candidate,pair_scores,config)
                merge = time.perf_counter()-tick
                total = time.perf_counter()-start
                row = {**task,'total_seconds':total,'database_seconds':sum(s['seconds'] for s in searches),
                       'handoff_seconds':handoff,'tokenize_seconds':result['tokenize_seconds'] if result else 0,
                       'worker_seconds':result['worker_seconds'] if result else 0,
                       'file_transport_overhead_seconds':max(0,handoff-result['worker_seconds']) if result else 0,
                       'merge_seconds':merge,'pairs':len(wanted),'selected_ids':[r['id'] for r in output],
                       'database_searches':searches,'scope':'cached query embeddings; DB HTTP + file handoff + fresh tokenize + GPU + merge; full805 excludes unnecessary DB'}
                stream.write(json.dumps(row,ensure_ascii=False)+'\n'); stream.flush()
                print(f"{task['request_id']} {total:.3f}s, {len(wanted)} pairs, {len(output)} docs",flush=True)
        finally:
            db.close()

if __name__=='__main__':
    make_plan() if sys.argv[1]=='plan' else run()
