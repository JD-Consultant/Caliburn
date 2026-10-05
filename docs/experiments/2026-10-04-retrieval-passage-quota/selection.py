"""Return one employee's deduplicated references while retaining passage origins."""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent/'2026-10-04-retrieve-rerank'))
from evaluate import pipeline


def global_selection(pools,scores,n,k,rerank):
    dense = {}
    for pool in pools:
        for row in pool:
            dense[row['id']] = max(dense.get(row['id'],-float('inf')),row['score'])
    ranking = sorted(({'id':ident,'score':score} for ident,score in dense.items()),key=lambda r:(-r['score'],r['id']))
    selected = ranking[:n]
    if rerank:
        pairs = []
        for row in selected:
            keys = [(i,row['id']) for i in range(1,len(pools)+1)]
            if any(key not in scores for key in keys):
                raise ValueError('Missing required global pair score')
            pairs.append({'id':row['id'],'score':max(scores[key] for key in keys)})
        selected = pipeline(ranking,pairs,n,None,k,None)
    else:
        selected = selected[:k]
    return [{'id':row['id'],'matches':[{'passage':i,'logit':scores.get((i,row['id']))}
             for i in range(1,len(pools)+1)]} for row in selected]


def per_passage(pools,scores,n,k,rerank):
    retained = {}
    for passage,pool in enumerate(pools,1):
        candidates = []
        for dense_rank,row in enumerate(pool[:n],1):
            pair_key = (passage,row['id'])
            if rerank and pair_key not in scores:
                raise ValueError(f'Missing required per-passage pair score: {pair_key}')
            value = scores[pair_key] if rerank else row['score']
            candidates.append({'id':row['id'],'value':value,'dense_rank':dense_rank,'cosine':row['score']})
        candidates.sort(key=lambda r:(-r['value'],r['id']))
        for position,row in enumerate(candidates[:k],1):
            record = retained.setdefault(row['id'],{'id':row['id'],'matches':[]})
            record['matches'].append({'passage':passage,'dense_rank':row['dense_rank'],'cosine':row['cosine'],
                                      'rerank_rank':position if rerank else None,
                                      'logit':row['value'] if rerank else None})
    # Sorting affects presentation only: no second global quota discards passages.
    value_field = 'logit' if rerank else 'cosine'
    return sorted(retained.values(),key=lambda r:(-max(m[value_field] for m in r['matches']),r['id']))
