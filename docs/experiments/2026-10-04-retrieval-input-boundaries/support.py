"""Use sealed experimental selection/model contracts without production imports."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUOTA = HERE.parent/'2026-10-04-retrieval-passage-quota'
sys.path.insert(0,str(QUOTA))
import common as prior
from selection import per_passage
from audit import expected_selection,check_native
from inputs import sentence_pieces

read,lines,sha,text_sha = prior.read,prior.lines,prior.sha,prior.text_sha
MODEL_SHA,COLLECTION = prior.MODEL_SHA,prior.COLLECTION
VARIANTS = ('original_messages','joined_employee','sentence_pieces')
CONFIGS = ({'method':'quota_dense','n':20,'k':5},{'method':'quota_rerank','n':20,'k':5})

def dump(name,value):
    with (HERE/name).open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def dump_lines(name,values):
    with (HERE/name).open('x',encoding='utf-8') as stream:
        for value in values:
            stream.write(json.dumps(value,ensure_ascii=False)+'\n')

def load_scores():
    pairs = prior.load_pairs('holdout')
    for r in lines(HERE/'supplemental-pairs.jsonl'):
        key = r['query_sha256']+':'+r['document_sha256']
        assert key not in pairs
        pairs[key] = r
    return pairs

def make_inputs(cases):
    queries = []
    for c in cases:
        messages = c['employee_messages']
        variants = {'original_messages':[{'text':t,'message':i,'start':0,'end':len(t)} for i,t in enumerate(messages,1)],
                    'joined_employee':[{'text':'\n\n'.join(messages),'message_indices':list(range(1,len(messages)+1))}],
                    'sentence_pieces':sentence_pieces(messages)}
        for variant,pieces in variants.items():
            assert pieces and all(p['text'] for p in pieces)
            queries.append({'case_id':c['case_id'],'variant':variant,'passages':[p['text'] for p in pieces],'origins':pieces})
    return queries
