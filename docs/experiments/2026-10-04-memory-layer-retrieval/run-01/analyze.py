import statistics
from common import *
def main():
 cases={c['case_id']:c for c in read(HERE/'cases.json')};docs={d['id']:d for d in read(HERE/'corpus.json')}
 new=read(HERE/'judgments.json') if (HERE/'judgments.json').exists() else []
 grades={(j['case_id'],j['document_id']):j for j in read(HERE/'used-prior-judgments.json')+new}
 results=read(HERE/'results.json');graded=[];report=['# 原話與 B1 B2 六組前五結果','', '固定原話評分；0–3 逐份列出，不平均或相加。B1／B2 為現行 parent 發布的實際合成 Memory。','']
 for cid,c in cases.items():
  report += ['## '+cid+' '+c.get('label',c.get('discussion_label','')),'',c['employee_statement'],'',f'完整 Memory：snapshots/{cid}.json。','']
  for r in [v for v in results if v['case_id']==cid]:
   selected=[]
   report += ['### '+r['method'],'']
   for rank,p in enumerate(r['selected'],1):
    j=grades[(cid,p['id'])];d=docs[p['id']]
    validate_judgment(j['judgment'],c['employee_statement'],d['text'])
    grade=j['judgment'];selected.append(p|{'rank':rank,'title':d['title'],'judgment':grade,'judgment_reused':j in read(HERE/'used-prior-judgments.json')})
    report.append(str(rank)+'. **'+str(grade['grade'])+'** '+d['title']+'（'+p['id']+'）：'+grade['reason'])
   report.append('');graded.append(r|{'selected':selected})
 dump('graded-results.json',graded)
 with (HERE/'report.md').open('x',encoding='utf-8') as f:f.write('\n'.join(report)+'\n')
 timing=[]
 for r in graded:
  samples=[t for t in read(HERE/'benchmark.json') if t['case_id']==r['case_id'] and t['method']==r['method']]
  timing.append({'case_id':r['case_id'],'method':r['method'],'query_count':len(r['query_ids']),'median_seconds':statistics.median(t['seconds'] for t in samples),'median_db_seconds':statistics.median(t['db_seconds'] for t in samples)})
 dump('timing-summary.json',timing)
 captures=[json.loads(v) for v in (HERE/'memory-captures.jsonl').read_text(encoding='utf-8').splitlines()]
 summary=[]
 for cid in cases:
  snap=read(HERE/'snapshots'/f'{cid}.json')
  summary.append({'case_id':cid,'layers':{layer:{'objects':len([o for o in snap['objects'] if o['layer']==layer]),'body_chars':sum(len(o['content']['body']) for o in snap['objects'] if o['layer']==layer)} for layer in ('work_situation','work_understanding')},'capture':next(c for c in captures if c['case_id']==cid)})
 dump('memory-summary.json',summary)
 usage=[]
 for name in ('memory-usage.jsonl','judge-usage.jsonl'):
  if (HERE/name).exists():usage += [json.loads(v) for v in (HERE/name).read_text(encoding='utf-8').splitlines()]
 from decimal import Decimal
 dump('cost-summary.json',{'estimated_or_reserved_usd':str(sum((Decimal(v['accounted_usd']) for v in usage),Decimal(0))),'response_calls':len(usage),'all_usage_known':all(v['usage_known'] for v in usage),'is_provider_invoice':False})
 print('48 graded groups saved, per-source scores and timings retained')
if __name__=='__main__':main()
