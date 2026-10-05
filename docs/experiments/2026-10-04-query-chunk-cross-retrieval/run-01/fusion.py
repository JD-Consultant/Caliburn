"""Per-employee parent fusion; local chunk multiplicity never becomes a vote."""
def merge_pools(pools,query_ids,constant=2):
    if len(pools)!=len(query_ids) or not pools or constant<=0:raise ValueError('invalid pools')
    for pool in pools:
        if len({row['id'] for row in pool})!=len(pool):raise ValueError('duplicate parent in query')
    if len(pools)==1:return [dict(row) for row in pools[0]]
    values={}
    for query,pool in zip(query_ids,pools,strict=True):
        for rank,row in enumerate(pool):
            contribution=1/(constant+rank)
            item=values.setdefault(row['id'],{'id':row['id'],'fusion_score':0,'contributions':[]})
            item['fusion_score']+=contribution
            item['contributions'].append({'query_id':query,'zero_based_rank':rank,'contribution':contribution})
    return sorted(values.values(),key=lambda row:(-row['fusion_score'],row['id']))
