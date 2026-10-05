"""Development only: reuse frozen vectors/scores and list actual missing pairs."""
import time
from common import *

def main():
    corpus = documents()
    vectors = doc_vectors(corpus)
    cases = read(HERE/'development-cases.json')
    cache = {r['text_sha256']:r for r in lines(OLD/'passage-pool/passage-cache.jsonl')}
    old_prepared = read(OLD/'passage-pool/prepared.json')
    old_queries = {q['case_id']:q for q in old_prepared['queries']}
    assert read(OLD/'passage-pool/gpu-runtime.json')['model_revision']=='953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e'
    old_corpus = {d['id']:d for d in old_prepared['corpus']}
    assert all(d['text']==old_corpus[d['id']]['text'] for d in corpus)
    queries = []
    for c in cases:
        assert c['employee_messages']==old_queries[c['case_id']]['passages']
        pools,global_pool = rank(corpus,vectors,c['employee_messages'],cache)
        assert [r['id'] for r in global_pool]==[r['id'] for r in old_queries[c['case_id']]['ranking']]
        queries.append({'case_id':c['case_id'],'passages':c['employee_messages'],'pools':pools,'global_pool':global_pool})
    borrowed = {}
    for record in lines(OLD/'passage-pool/rerank-pairs.jsonl'):
        q = old_queries[record['case_id']]
        for d in record['pairs']:
            for p in d['passages']:
                text = q['passages'][p['passage']-1]
                doc = old_corpus[d['id']]
                key = pair_key(text,doc)
                origin = {'file':'../2026-10-04-retrieve-rerank/passage-pool/rerank-pairs.jsonl',
                          'case_id':record['case_id'],'passage':p['passage'],'document_id':d['id']}
                if key in borrowed:
                    assert borrowed[key]['logit']==p['logit']
                    borrowed[key]['origins'].append(origin)
                else:
                    borrowed[key] = {'query_sha256':text_sha(text),'document_sha256':text_sha(doc['text']),
                       'document_id':d['id'],'logit':p['logit'],'query_tokens':p['query_tokens'],
                       'document_tokens':d['document_tokens'],'windows':p['windows'],'origins':[origin],
                       'model_sha256':MODEL_SHA,'cache_reused':True}
    needed = jobs(queries,corpus,borrowed,configs())
    dump('prepared-development.json',{'corpus':corpus,'queries':queries})
    dump_lines('borrowed-pairs.jsonl',borrowed.values())
    dump('development-jobs.json',needed)
    names = ['protocol.md','protocol-amendment-01.md','common.py','selection.py','prepare.py','gpu_worker.py','analyze.py',
             'development-cases.json','prepared-development.json','borrowed-pairs.jsonl','development-jobs.json',
             'case-manifest.json','case-amendment-01.json','holdout-cases-2026-10-04-reviewed.json']
    dump('execution-development.json',{'created_utc':time.time(),'before_new_scores':True,
            'sources':{n:sha(HERE/n) for n in names},'model_sha256':MODEL_SHA,
            'borrowed_source_sha256':sha(OLD/'passage-pool/rerank-pairs.jsonl'),
            'passage_cache_sha256':sha(OLD/'passage-pool/passage-cache.jsonl'),'document_cache_sha256':sha(CACHE)})
    print(json.dumps({'development_cases':len(queries),'borrowed_unique_pairs':len(borrowed),
                      'missing_unique_pairs':sum(len(r['documents']) for r in needed)},indent=2))

if __name__=='__main__':
    main()
