"""Per-reference grades and query contributions; never sum semantic grades."""
from decimal import Decimal
from pipeline import *

def main():
    check_manifest()
    cases={c['case_id']:c for c in read(HERE/'cases.json')}
    docs={d['id']:d for d in read(HERE/'corpus.json')}
    grades={(j['case_id'],j['document_id']):j for j in read(HERE/'reused-judgments.json')}
    for file in ('judgments.json','judgments-reconciled.json'):
        if (HERE/file).exists():
            for j in read(HERE/file):
                assert (j['case_id'],j['document_id']) not in grades
                grades[(j['case_id'],j['document_id'])]=j|{'reused':False}
    results=read(HERE/'results.json')
    lines=['# 員工分段 × 公版切塊：逐份代表性評分','',
           '固定八案、805父公版、既有30查詢向量。W為整段；S為既有工作主題分段各查20父，再RRF k2留最高五份。',
           '每列依檢索排名列0–3，沒有相加；只有模型評分，既有分級疑義仍未校準。','',
           '| 案例 | 方法 | 依排名逐份分數 |','|---|---|---|']
    for r in results:
        values=[str(grades[(r['case_id'],p['id'])]['judgment']['grade']) if (r['case_id'],p['id']) in grades else '未評' for p in r['selected']]
        lines.append('| '+r['case_id']+' | '+r['method']+' | '+'、'.join(values)+' |')
    graded=[]
    for r in results:
        lines.extend(['',f"## {r['case_id']} {r['method']}",'',f"查詢 {len(r['query_ids'])} 段；候選聯集 {r['union_parents']} 份，最後去重留五份。",''])
        entries=[]
        for rank,p in enumerate(r['selected'],1):
            j=grades.get((r['case_id'],p['id']))
            entry=p|{'rank':rank,'title':docs[p['id']]['title'],'judgment':j}
            entries.append(entry)
            grade=j['judgment']['grade'] if j else '未評'
            score=p.get('fusion_score',p.get('score'))
            lines.extend([f"{rank}. **{entry['title']}**（{p['id']}）：{grade}，{'RRF' if 'fusion_score' in p else 'cosine'} {score:.6f}。",''])
            if j:lines.extend([j['judgment']['reason'],''])
            if 'contributions' in p:
                lines.extend(['各段貢獻：'+'；'.join(f"{c['query_id']} 第{c['zero_based_rank']+1}名" for c in p['contributions'])+'。',''])
        graded.append(r|{'selected':entries})
    dump('graded-results.json',graded)
    with (HERE/'report.md').open('x',encoding='utf-8',newline='\n') as s:s.write('\n'.join(lines)+'\n')
    trace=[]
    for (case,doc),g in sorted(grades.items()):
        if g['judgment']['grade']!=3:continue
        methods=[]
        for r in [r for r in results if r['case_id']==case]:
            evidence=[]
            for query,pool in zip(r['query_ids'],r['query_pools'],strict=True):
                hit=next(((i,p) for i,p in enumerate(pool,1) if p['id']==doc),None)
                evidence.append({'query_id':query,'rank':hit[0] if hit else None,'top_chunks':hit[1]['top_chunks'] if hit else []})
            methods.append({'method':r['method'],'top5_rank':next((i for i,p in enumerate(r['selected'],1) if p['id']==doc),None),
                            'merged_rank':next((i for i,p in enumerate(r['merged_ranking'],1) if p['id']==doc),None),'query_evidence':evidence})
        trace.append({'case_id':case,'document_id':doc,'title':docs[doc]['title'],'methods':methods})
    dump('strong-reference-trace.json',trace)
    usage=[json.loads(s) for s in (HERE/'judge-usage.jsonl').read_text(encoding='utf-8').splitlines()] if (HERE/'judge-usage.jsonl').exists() else []
    summary={'groups':len(results),'positions':sum(len(r['selected']) for r in results),
             'unique_pairs':len({(r['case_id'],p['id']) for r in results for p in r['selected']}),
             'missing_positions':sum((r['case_id'],p['id']) not in grades for r in results for p in r['selected']),
             'new_response_count':len(usage),'new_accounted_usd':str(sum((Decimal(u['accounted_usd']) for u in usage),Decimal(0))),
             'new_embedding_calls':0,'strong_pairs':len(trace),'grading':'single model; no expert truth or exhaustive recall'}
    dump('analysis-summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
