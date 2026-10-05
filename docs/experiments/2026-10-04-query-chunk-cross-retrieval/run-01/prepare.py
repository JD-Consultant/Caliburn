from pipeline import *

def main():
    queries=[];vectors=[];paths=[]
    for base in (F,H):
        qs=[q for q in read(base/'queries.json') if q['variant'] in ('whole','segments')]
        vs={v['query_id']:v for v in read(base/'query-vectors.json')}
        for q in qs:
            v=vs[q['query_id']];assert q['text_sha256']==v['text_sha256']==text_sha(q['text'])
            queries.append(q|{'prior_query_file':str((base/'queries.json').relative_to(ROOT)).replace('\\','/')})
            vectors.append(v|{'cache_reused':True,'prior_vector_file':str((base/'query-vectors.json').relative_to(ROOT)).replace('\\','/')})
        paths.extend([base/'queries.json',base/'query-vectors.json'])
    assert len(queries)==len(vectors)==30 and sum(q['variant']=='segments' for q in queries)==22
    cases=read(PUBLIC/'cases.json');docs=read(PUBLIC/'corpus.json')
    bycase={c['case_id']:c for c in cases};bydoc={d['id']:d for d in docs}
    grades=[]
    for file in ('reused-judgments.json','judgments.json','judgments-reconciled-02.json'):
        for row in read(PUBLIC/file):
            assert row['employee_sha256']==text_sha(bycase[row['case_id']]['employee_statement'])
            assert row['document_sha256']==text_sha(bydoc[row['document_id']]['text'])
            validate_judgment(row['judgment'],bycase[row['case_id']]['employee_statement'],bydoc[row['document_id']]['text'])
            grades.append(row|{'reused':True,'prior_judgment_file':str((PUBLIC/file).relative_to(ROOT)).replace('\\','/')})
        paths.append(PUBLIC/file)
    assert len(grades)==len({(j['case_id'],j['document_id']) for j in grades})==117
    for name,data in [('queries.json',queries),('query-vectors.json',vectors),('cases.json',cases),('corpus.json',docs),
                      ('reused-judgments.json',grades),('collections.json',read(PUBLIC/'collections.json'))]:dump(name,data)
    paths += [p for p in HERE.iterdir() if p.is_file() and p.name!='progress.md' and p.suffix!='.log']
    paths += [PUBLIC/name for name in ('artifact-hashes.json','chunks.json','vector-map.json','embedding-batches.jsonl',
                  'cases.json','corpus.json','collections.json','results.json')]
    paths += [PUBLIC/'vector-batches'/r['path'].split('/')[-1] for r in [json.loads(s) for s in (PUBLIC/'embedding-batches.jsonl').read_text(encoding='utf-8').splitlines()]]
    paths += [F/'results.json',H/'results.json',F/'judge-prompt-02.txt',H/'judge-prompt.txt',H/'judge-schema.json',
              PUBLIC/'chunks.py',H/'pipeline.py',ROOT/'docs/plans/2026-10-04-query-chunk-cross-retrieval.md']
    dump('input-manifest.json',{'inputs':{str(p.relative_to(ROOT)).replace('\\','/'):{'sha256':sha(p)} for p in paths}})
    dump('execution-manifest.json',{'max_cost_usd':'1.00','max_calls':100,'input_manifest_sha256':sha(HERE/'input-manifest.json')})
    print('30 reused queries, 8 fixed cases, 117 reusable grades, existing D/T/U collections',flush=True)

if __name__=='__main__':main()
