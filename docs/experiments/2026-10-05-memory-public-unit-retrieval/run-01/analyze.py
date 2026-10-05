"""Per-document grades and timings; no relevance-grade totals or accuracy claim."""
import statistics
from decimal import Decimal
from common import *
def main():
 check_manifest();check_manifest('analysis-code-manifest.json')
 cases=read(HERE/'cases.json');docs={d['id']:d for d in read(HERE/'corpus.json')};grades={(j['case_id'],j['document_id']):j for j in read(HERE/'used-prior-judgments.json')+read(HERE/'judgments.json')};results=read(HERE/'results.json')+read(HERE/'rerank-results.json')
 graded=[];lines=['# B2／原話 × 公版粒度與rerank逐案結果','','2026-10-05；固定八案，十二方法，各全域去重留五。0–3為模型代表性判讀，逐份列出，不加總／平均。這批案例已用過，不是新holdout。','','O原話整段，B2逐理解；D整份、T任務max（含獨立概述）、M同query的D/T等權RRF後20父。-R為完整D正文rerank後再跨query合併。單query不再次融合。','']
 for case in cases:
  cid=case['case_id'];lines+=['## '+cid,'',case['employee_statement'],'','| 方法 | 名次 | 公版名稱 | ID | 分級 | 主要面向 |','|---|---:|---|---|---:|---|']
  for r in [r for r in results if r['case_id']==cid]:
   row=dict(r);selected=[]
   for rank,p in enumerate(r['selected'],1):
    j=grades[(cid,p['id'])];validate_judgment(j['judgment'],case['employee_statement'],docs[p['id']]['text']);d=docs[p['id']];name=d.get('name') or d.get('title') or d.get('occupation_name') or p['id'];g=j['judgment'];selected.append({**p,'name':name,'rank':rank,'judgment':g,'reused_judgment':j.get('reused',False),'prior_judgment_file':j.get('prior_judgment_file')});lines.append(f"| {r['method']} | {rank} | {name} | {p['id']} | {g['grade'] if g['grade'] is not None else '未判定'} | {'、'.join(g['main_work'])} |")
   row['selected']=selected;graded.append(row)
  for r in [r for r in graded if r['case_id']==cid]:
   lines+=['','### '+r['method'],'']
   for p in r['selected']:
    g=p['judgment'];lines+=[f"{p['rank']}. **{p['name']}（{g['grade']}）**：{g['reason']}"]
    for e in g['evidence']:lines+=[f"   - 員工：{e['employee_quote']}",f"   - 公版：{e['reference_quote']}"]
    if g['limitations']:lines+=['   - 限制：'+'；'.join(g['limitations'])]
 dump('graded-results.json',graded)
 with (HERE/'report.md').open('x',encoding='utf-8',newline='\n') as out:out.write('\n'.join(lines)+'\n')
 trials=read(HERE/'benchmark.json')+read(HERE/'rerank-benchmark.json');timings=[]
 for c in cases:
  for method in list(METHODS)+[m+'-R' for m in METHODS]:
   rows=[r for r in trials if r['case_id']==c['case_id'] and r['method']==method];assert len(rows)==3
   timings.append({'case_id':c['case_id'],'method':method,'trials':3,'median_seconds':statistics.median(r['seconds'] for r in rows),'median_db_seconds':statistics.median(r['db_seconds'] for r in rows),'median_cosine_and_sort_seconds':statistics.median(r['cosine_and_sort_seconds'] for r in rows),'median_gpu_seconds':statistics.median(r.get('gpu_seconds',0) for r in rows),'queries':rows[0]['queries'],'routes_per_query':rows[0]['routes_per_query'],'cached_query_embedding':True,'includes_fresh_rerank':method.endswith('-R')})
 dump('timing-summary.json',timings)
 usage=[json.loads(s) for s in (HERE/'judge-usage.jsonl').read_text(encoding='utf-8').splitlines()];cost=sum((Decimal(r['accounted_usd']) for r in usage),Decimal(0));dump('cost-summary.json',{'response_calls':len(usage),'estimated_or_reserved_usd':str(cost),'all_usage_known':all(r['usage_known'] for r in usage),'is_provider_invoice':False,'new_embeddings':0,'new_memory_calls':0,'local_rerank_provider_calls':0})
 summary=[]
 for c in cases:
  for r in [r for r in graded if r['case_id']==c['case_id']]:
   summary.append({'case_id':c['case_id'],'method':r['method'],'grades':[p['judgment']['grade'] for p in r['selected']],'strong_representatives':[{'id':p['id'],'name':p['name'],'rank':p['rank'],'main_work':p['judgment']['main_work']} for p in r['selected'] if p['judgment']['grade']==3]})
 dump('representatives.json',summary)
 print(f'{len(graded)} graded groups; {len(grades)} pairs; cost US${cost}')
if __name__=='__main__':main()
