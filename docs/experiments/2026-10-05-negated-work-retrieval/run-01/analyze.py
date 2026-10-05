"""Summarize paired changes without using retrieval scores as applicability labels."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))


def dump(name, obj):
    with (HERE/name).open('x',encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    completion = read('complete.json')
    assert completion['inputs_unchanged']
    cases = read('cases.json')
    queries = read('queries.json')
    vectors = {q['query_id']:q['dense'] for q in read('query-vectors.json')}
    rankings = {(r['query_id'],r['representation']):r for r in read('all-rankings.json')}
    results = {r['query_id']:r for r in read('results.json')}
    candidates = read('candidate-pools.json')
    assert len(queries)==len(results)==len(vectors)==24
    rows=[]
    for q in queries:
        assert hashlib.sha256(q['text'].encode()).hexdigest()==q['text_sha256']
        c=next(c for c in cases if c['case_id']==q['case_id'])
        result=results[q['query_id']]
        pool=result['common_pool_ranking']
        assert pool==sorted(pool,key=lambda r:(-r['score'],r['id']))
        assert all(math.isfinite(r['score']) for r in pool)
        assert result['own_pool_ranking']==[r for r in pool if r['id'] in candidates[q['query_id']]]
        assert result['selected']==result['own_pool_ranking'][:5]
        target=next((i,r) for i,r in enumerate(pool,1) if r['id']==c['probe'])
        own_rank=next((i for i,r in enumerate(result['own_pool_ranking'],1) if r['id']==c['probe']),None)
        row={'case_id':c['case_id'],'variant':q['variant'],'query_id':q['query_id'],
             'probe_id':c['probe'],'primary_id':c['primary'],
             'rerank_logit':target[1]['score'],'common_rerank_rank':target[0],
             'common_pool_count':len(pool),'own_pool_count':len(result['own_pool_ranking']),
             'own_rerank_rank':own_rank,'probe_in_top5':any(r['id']==c['probe'] for r in result['selected']),
             'primary_in_top5':any(r['id']==c['primary'] for r in result['selected'])}
        for rep in ('document','task'):
            ranking=rankings[(q['query_id'],rep)]
            assert len(ranking['parents'])==805
            assert len({r['id'] for r in ranking['parents']})==805
            probe=next(r for r in ranking['parents'] if r['id']==c['probe'])
            row[rep+'_cosine']=probe['score']
            row[rep+'_parent_rank']=probe['rank']
            if rep=='task':
                row['probe_chunk']=ranking['probe_chunk']
        rows.append(row)
    comparisons=[]
    for case in cases:
        own={r['variant']:r for r in rows if r['case_id']==case['case_id']}
        base=own['base']
        for variant in ('question_only','no_short','no_explicit','yes_short','uncertain','no_repeated3'):
            r=own[variant]
            comparisons.append({'case_id':case['case_id'],'variant':variant,
                'delta_vs_base':{key:r[key]-base[key] for key in ('document_cosine','task_cosine','rerank_logit')},
                'delta_vs_question':{key:r[key]-own['question_only'][key] for key in ('document_cosine','task_cosine','rerank_logit')},
                'delta_vs_yes':{key:r[key]-own['yes_short'][key] for key in ('document_cosine','task_cosine','rerank_logit')},
                'probe_chunk_delta_vs_base':r['probe_chunk']['score']-base['probe_chunk']['score']})
        assert vectors[case['case_id']+'-base']==vectors[case['case_id']+'-confirmed_projection']
        assert results[case['case_id']+'-base']['selected']==results[case['case_id']+'-confirmed_projection']['selected']
        memberships=[{r['id'] for r in results[q['query_id']]['common_pool_ranking']}
                     for q in queries if q['case_id']==case['case_id']]
        assert all(m==memberships[0] for m in memberships)
    counts={}
    for variant in ('question_only','no_short','no_explicit','yes_short','uncertain','no_repeated3'):
        comp=[c for c in comparisons if c['variant']==variant]
        vals=[r for r in rows if r['variant']==variant]
        counts[variant]={'cases':len(vals),'higher_vs_base':{
            key:sum(c['delta_vs_base'][key]>0 for c in comp) for key in ('document_cosine','task_cosine','rerank_logit')},
            'probe_chunk_higher_vs_base':sum(c['probe_chunk_delta_vs_base']>0 for c in comp),
            'probe_in_top5':sum(r['probe_in_top5'] for r in vals),
            'primary_in_top5':sum(r['primary_in_top5'] for r in vals)}
    dump('summary.json',{'rows':rows,'comparisons':comparisons,'counts':counts,
        'warning':'Three synthetic contrasts, no human corpus relevance grading or consultant repeat-question test.'})
    dump('verification.json',{'queries':24,'parent_rankings':48,'parents_per_route':805,
        'fixed_common_pool_per_case':True,'projection_equal_to_base':True,'own_pool_top5_checked':True,
        'full_source_hashes_checked_before_after':True})
    print(json.dumps(counts,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
