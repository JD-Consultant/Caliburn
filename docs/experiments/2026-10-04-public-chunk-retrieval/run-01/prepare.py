from collections import Counter
from pipeline import *
from chunks import build_chunks

def main():
    old=read(F/'corpus.json'); originals=read(FIRST/'corpus.json')
    assert len(old)==len(originals)==805
    sources={d['id']:d for d in originals}
    chunks=[]; excluded=[]
    for d in old:
        source=sources[d['id']];p=ROOT/source['source'];assert sha(p)==source['source_sha256']
        j=read(p)
        chunks.append({'representation':'document','chunk_id':d['id']+':document','parent_id':d['id'],
                       'kind':'document','text':d['text'],'unit_index':None,'task_index':None,'task_codes':[],
                       'source':source['source'],'source_sha256':source['source_sha256']})
        for rep in ('task','unit'):
            rows=build_chunks(j,rep)
            union=set(line for r in rows for line in r['text'].splitlines())
            assert set(d['text'].splitlines())<=union,d['id']
            for r in rows:chunks.append({**r,'representation':rep,'source':source['source'],'source_sha256':source['source_sha256']})
            if not rows:excluded.append({'id':d['id'],'representation':rep,'reason':'empty text'})
    # IDs are representation-scoped; overview appears once in each representation.
    assert len({(r['representation'],r['chunk_id']) for r in chunks})==len(chunks)
    cases=read(F.parent/'cases-v1.json')['cases']+read(H/'cases.json')
    queries=[];vectors=[]
    for base,group in ((F,'needs'),(H,'a_interview')):
        qs={q['case_id']:q for q in read(base/'queries.json') if q['variant']=='whole'}
        vs={v['query_id']:v for v in read(base/'query-vectors.json')}
        for case in cases:
            if case['case_id'] not in qs:continue
            q=qs[case['case_id']];v=vs[q['query_id']]
            assert text_sha(q['text'])==v['text_sha256']
            queries.append({'query_id':case['case_id'],'case_id':case['case_id'],'group':group,
                            'text':q['text'],'text_sha256':text_sha(q['text']),
                            'prior_query_id':q['query_id'],'prior_query_source':str((base/'queries.json').relative_to(ROOT)).replace('\\','/')})
            vectors.append({**v,'query_id':case['case_id'],'cache_reused':True,
                            'prior_vector_source':str((base/'query-vectors.json').relative_to(ROOT)).replace('\\','/')})
            case['source_group']=group
    assert len(cases)==len(queries)==len(vectors)==8
    judgments=[]
    bycase={c['case_id']:c for c in cases};bydoc={d['id']:d for d in old}
    for base in (F,H):
        for r in read(base/'judgments-02.json'):
            assert r['employee_sha256']==text_sha(bycase[r['case_id']]['employee_statement'])
            assert r['document_sha256']==text_sha(bydoc[r['document_id']]['text'])
            validate_judgment(r['judgment'],bycase[r['case_id']]['employee_statement'],bydoc[r['document_id']]['text'])
            judgments.append({**r,'reused':True,'prior_judgment_file':str((base/'judgments-02.json').relative_to(ROOT)).replace('\\','/')})
    assert len(judgments)==82
    for name,data in [('corpus.json',old),('chunks.json',chunks),('cases.json',cases),('queries.json',queries),
                      ('query-vectors.json',vectors),('reused-judgments.json',judgments),('excluded.json',excluded)]:dump(name,data)
    dump('chunk-summary.json',{'parents':805,'counts':dict(Counter(r['representation'] for r in chunks)),
                             'kinds':dict(Counter(r['representation']+':'+r['kind'] for r in chunks)),
                             'unique_texts':len({text_sha(r['text']) for r in chunks}),
                             'all_document_lines_preserved':True,'source_files_verified':805})
    paths=[p for p in HERE.iterdir() if p.is_file() and p.name!='progress.md' and p.suffix!='.log']
    paths += [ROOT/'docs/plans/2026-10-04-public-chunk-retrieval.md',CACHE,FIRST/'corpus.json',
              F.parent/'cases-v1.json',H/'cases.json',F/'queries.json',H/'queries.json',F/'query-vectors.json',H/'query-vectors.json',
              F/'judgments-02.json',H/'judgments-02.json',F/'judge-prompt-02.txt',H/'judge-prompt.txt',H/'judge-schema.json',
              H/'embedding-runtime.json',FIRST/'evaluation.py',H/'pipeline.py']
    paths += [ROOT/s['source'] for s in sources.values()]
    dump('input-manifest.json',{'max_cost_usd':'1.00','max_calls':100,
         'inputs':{str(p.relative_to(ROOT)).replace('\\','/'):{'sha256':sha(p)} for p in paths}})
    print(json.dumps(read(HERE/'chunk-summary.json'),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
