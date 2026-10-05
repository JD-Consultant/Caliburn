"""Task-reference coverage and bounded candidate filters for this experiment."""


def coverage(ids, topics):
    selected = set(ids)
    missing = [t['topic_id'] for t in topics if not any(s['id'] in selected for s in t['support'])]
    secondary = [t for t in topics if t['secondary']]
    return {'covered':len(topics)-len(missing),'total':len(topics),
            'coverage':(len(topics)-len(missing))/len(topics) if topics else None,
            'missing':missing,'secondary_covered':sum(t['topic_id'] not in missing for t in secondary),
            'secondary_total':len(secondary),'complete':bool(topics) and not missing}


def select(rows, k, threshold):
    return [r for r in rows if threshold is None or r['score'] >= threshold][:k]


def token_windows(query, passage, max_tokens, overlap=32):
    capacity = max_tokens-len(query)-4
    if capacity <= overlap:
        raise ValueError('query leaves insufficient passage capacity; truncation forbidden')
    windows = []
    start = 0
    while start < len(passage):
        windows.append(passage[start:start+capacity])
        if start+capacity >= len(passage):
            break
        start += capacity-overlap
    return windows or [[]]


def pipeline(dense, pairs, n, cosine, k, cross):
    ids = {r['id'] for r in select(dense,n,cosine)}
    available = [r for r in pairs if r['id'] in ids]
    if {r['id'] for r in available} != ids:
        raise ValueError('Missing reranker score in broad candidate pool')
    return select(sorted(available,key=lambda r:(-r['score'],r['id'])),k,cross)
