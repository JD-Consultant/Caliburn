import statistics
from collections import Counter
from pipeline import *

def main():
    check_manifest();cases={c['case_id']:c for c in read(HERE/'cases.json')};docs={d['id']:d for d in read(HERE/'corpus.json')}
    grades={(j['case_id'],j['document_id']):j for j in read(HERE/'reused-judgments.json')}
    for j in read(HERE/'judgments.json'):grades[(j['case_id'],j['document_id'])]=j|{'reused':False}
    # Literal evidence failures remain missing unless a separately recorded correction is provided.
    correction=HERE/'judgments-reconciled-02.json'
    if correction.exists():
        for j in read(correction):grades[(j['case_id'],j['document_id'])]=j|{'reused':False}
    result=read(HERE/'results.json');chunks=read(HERE/'chunks.json')
    lookup={(r['representation'],r['chunk_id']):r for r in chunks}
    lines=['# 公版切塊的逐份檢索結果','',
           '隔離研究。固定同員工whole原文及805父公版；只變公版粒度與父合併。模型0–3分逐份列，不加總。',
           '前三均值重排相同max初搜20父候選；既有評分疑義及新引用失敗保留，不當正式最佳方案。','',
           '| 案例 | 整份 | 任務max | 任務前三均值 | 單元max | 單元前三均值 |',
           '|---|---|---|---|---|---|']
    for case in cases:
        cells=[]
        for method in METHODS:
            row=next(r for r in result if r['case_id']==case and r['method']==method)
            cells.append('、'.join(str(grades[(case,p['id'])]['judgment']['grade']) if (case,p['id']) in grades else '未評' for p in row['selected']))
        lines.append('| '+case+' | '+' | '.join(cells)+' |')
    graded=[]
    for row in result:
        lines.extend(['',f"## {row['case_id']} {row['method']}",''])
        entries=[]
        for rank,p in enumerate(row['selected'],1):
            judgment=grades.get((row['case_id'],p['id']))
            evidence_chunks=[lookup[(row['representation'],h['chunk_id'])]|{'cosine':h['score']} for h in p['top_chunks']]
            entry=p|{'rank':rank,'title':docs[p['id']]['title'],'judgment':judgment,'matched_chunks':evidence_chunks}
            entries.append(entry)
            grade=judgment['judgment']['grade'] if judgment else '未評'
            lines.extend([f"{rank}. **{docs[p['id']]['title']}**（{p['id']}）：{grade}，合併分數 {p['score']:.6f}。",''])
            if judgment:lines.extend([judgment['judgment']['reason'],''])
            if row['representation']!='document':
                for hit in evidence_chunks:
                    lines.extend([f"命中 {hit['kind']}／單元{hit['unit_index']}／任務{hit['task_index']}，cosine {hit['cosine']:.6f}：",'','> '+hit['text'].replace('\n','\n> '),''])
        graded.append(row|{'selected':entries})
    dump('graded-results.json',graded)
    (HERE/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    # Inspect retention of known strong pairs; this is not exhaustive recall.
    known=[(c,d) for (c,d),g in grades.items() if g['judgment']['grade']==3]
    trace=[]
    for c,d in sorted(known):
        methods=[]
        for method in METHODS:
            r=next(r for r in result if r['case_id']==c and r['method']==method)
            pos=next((i for i,p in enumerate(r['selected'],1) if p['id']==d),None)
            methods.append({'method':method,'rank':pos,'in_top20':d in r['candidate_parents']})
        trace.append({'case_id':c,'document_id':d,'title':docs[d]['title'],'methods':methods})
    dump('strong-reference-trace.json',trace)
    usage=[json.loads(s) for s in (HERE/'judge-usage.jsonl').read_text(encoding='utf-8').splitlines()] if (HERE/'judge-usage.jsonl').exists() else []
    dump('analysis-summary.json',{'groups':len(result),'positions':sum(len(r['selected']) for r in result),
          'unique_pairs':len({(r['case_id'],p['id']) for r in result for p in r['selected']}),
          'missing_positions':sum((r['case_id'],p['id']) not in grades for r in result for p in r['selected']),
          'new_response_count':len(usage),'new_estimated_usd':str(sum(__import__('decimal').Decimal(u['accounted_usd']) for u in usage)),
          'counts':read(HERE/'chunk-summary.json'),'embedding':read(HERE/'embedding-complete.json')})
    print('\n'.join(lines[:16]),flush=True)

if __name__=='__main__':main()
