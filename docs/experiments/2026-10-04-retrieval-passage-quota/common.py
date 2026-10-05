"""Frozen research inputs and content-addressed pair records; no product wiring."""
import hashlib
import itertools
import json
import statistics
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OLD = HERE.parent/'2026-10-04-retrieve-rerank'
CACHE = HERE.parent/'2026-10-04-occupation-retrieval-generalization/cache/20f95996a7ef4d574c29bed8625e84277aee1a73b8d097f5b45b5320ddb27bd8.jsonl'
MODEL_SHA = 'd9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286'
COLLECTION = 'ocs_eval_9401166158b64229ad96f9286d4f1b09'
sys.path.insert(0,str(OLD))
from evaluate import coverage
from selection import global_selection, per_passage

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def lines(path):
    with Path(path).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(8*1024*1024):
            h.update(block)
    return h.hexdigest()

def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()

def dump(name,value):
    with (HERE/name).open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def dump_lines(name,rows):
    with (HERE/name).open('x',encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row,ensure_ascii=False)+'\n')

def documents():
    return read(OLD/'prepared.json')['corpus']

def doc_vectors(corpus):
    wanted = {text_sha(r['text']) for r in corpus}
    cached = {r['text_sha256']:r for r in lines(CACHE) if r['text_sha256'] in wanted}
    values = np.asarray([cached[text_sha(r['text'])]['embedding']['dense'] for r in corpus],dtype=np.float64)
    return values/np.linalg.norm(values,axis=1,keepdims=True)

def rank(corpus,vectors,passages,cache):
    pools = []
    for text in passages:
        vector = np.asarray(cache[text_sha(text)]['dense'],dtype=np.float64)
        vector /= np.linalg.norm(vector)
        scores = vectors@vector
        order = sorted(range(len(corpus)),key=lambda i:(-float(scores[i]),corpus[i]['id']))
        pools.append([{'id':corpus[i]['id'],'score':float(scores[i])} for i in order])
    maximum = {}
    for pool in pools:
        for r in pool:
            maximum[r['id']] = max(maximum.get(r['id'],-float('inf')),r['score'])
    global_pool = sorted(({'id':k,'score':v} for k,v in maximum.items()),key=lambda r:(-r['score'],r['id']))
    return pools,global_pool

def configs():
    return [{'method':method,'n':n,'k':k} for method in ('global_dense','global_rerank','quota_dense','quota_rerank')
            for n,k in itertools.product((20,50,100,200) if method.startswith('global') else (20,50,100),
                                         (5,10,20,50) if method.startswith('global') else (3,5,10,20))]

def required(q,config):
    if not config['method'].endswith('rerank'):
        return set()
    if config['method'].startswith('global'):
        return {(i,r['id']) for i in range(1,len(q['passages'])+1) for r in q['global_pool'][:config['n']]}
    return {(i,r['id']) for i,pool in enumerate(q['pools'],1) for r in pool[:config['n']]}

def pair_key(text,doc):
    return text_sha(text)+':'+text_sha(doc['text'])

def score_map(q,corpus,pairs):
    return {(i,d['id']):pairs[pair_key(t,d)]['logit'] for i,t in enumerate(q['passages'],1)
            for d in corpus if pair_key(t,d) in pairs}

def select(q,scores,config):
    function = global_selection if config['method'].startswith('global') else per_passage
    return function(q['pools'],scores,config['n'],config['k'],config['method'].endswith('rerank'))

def metric(q,case,corpus,selected,config):
    ids = [r['id'] for r in selected]
    by_id = {r['id']:r for r in corpus}
    relevant = {k for k,v in case['grades'].items() if v>=2}
    return {**config,'case_id':q['case_id'],**coverage(ids,case['topics']),
            'returned':len(ids),'characters':sum(len(by_id[k]['text']) for k in ids),
            'pair_comparisons':len(required(q,config)),
            'labeled_relevant_recall':len(relevant&set(ids))/len(relevant) if relevant else None,
            'known_conflicting_retained':[k for k in case['hard_negatives'] if k in ids],
            'selected':selected}

def aggregate(rows):
    positives = [r for r in rows if r['total']]
    return {'cases':len(rows),'positive_cases':len(positives),'complete_cases':sum(r['complete'] for r in positives),
            'covered':sum(r['covered'] for r in rows),'total':sum(r['total'] for r in rows),
            'secondary_covered':sum(r['secondary_covered'] for r in rows),
            'secondary_total':sum(r['secondary_total'] for r in rows),
            'mean_characters':statistics.mean(r['characters'] for r in rows),
            'mean_documents':statistics.mean(r['returned'] for r in rows),
            'mean_pair_comparisons':statistics.mean(r['pair_comparisons'] for r in rows)}

def load_pairs(phase):
    result = {}
    paths = [HERE/'borrowed-pairs.jsonl',HERE/'supplemental-development-pairs.jsonl']
    if phase=='holdout':
        paths.append(HERE/'supplemental-holdout-pairs.jsonl')
    for path in paths:
        for r in lines(path):
            key = r['query_sha256']+':'+r['document_sha256']
            assert key not in result, 'duplicate score provenance'
            result[key] = r
    return result

def jobs(queries,corpus,pairs,configurations):
    by_id = {r['id']:r for r in corpus}
    pending = {}
    for q in queries:
        needed = set().union(*(required(q,c) for c in configurations))
        for index,ident in sorted(needed):
            text,doc = q['passages'][index-1],by_id[ident]
            if pair_key(text,doc) in pairs:
                continue
            record = pending.setdefault(text_sha(text),{'query':text,'query_sha256':text_sha(text),'documents':{}})
            record['documents'][ident] = text_sha(doc['text'])
    return list(pending.values())
