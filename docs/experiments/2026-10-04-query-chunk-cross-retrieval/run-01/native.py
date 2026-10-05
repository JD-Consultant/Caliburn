"""Preserve native scores; canonicalize only with independently verified cosines."""
def canonical_hits(groups,rows,scores):
    result=[]
    for group in groups:
        for point in group.hits:
            index=int(point.id);row=rows[index];score=float(scores[index])
            assert row['parent_id']==group.id==point.payload['parent_id']
            assert row['chunk_id']==point.payload['chunk_id']
            if abs(score-point.score)>=1e-6:raise ValueError('native cosine differs materially')
            result.append({'parent_id':row['parent_id'],'chunk_id':row['chunk_id'],'score':score,'native_score':point.score})
    return result
