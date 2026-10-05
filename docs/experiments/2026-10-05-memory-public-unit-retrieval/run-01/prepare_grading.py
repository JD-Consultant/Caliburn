from common import *
def main():
 check_manifest();cases={c['case_id']:c for c in read(HERE/'cases.json')};docs={d['id']:d for d in read(HERE/'corpus.json')};prior={(j['case_id'],j['document_id']):j for j in read(HERE/'reused-judgments.json')};seen=set();used=[];jobs=[]
 for r in read(HERE/'results.json')+read(HERE/'rerank-results.json'):
  for p in r['selected']:
   key=(r['case_id'],p['id'])
   if key in seen:continue
   seen.add(key);c=cases[key[0]];d=docs[key[1]]
   if key in prior:
    j=prior[key];assert j['employee_sha256']==text_sha(c['employee_statement']) and j['document_sha256']==text_sha(d['text']);validate_judgment(j['judgment'],c['employee_statement'],d['text']);used.append(j)
   else:
    job={'job_id':f'new-{len(jobs)+1:03}','case_id':key[0],'document_id':key[1],'employee':c['employee_statement'],'main_facets':c['major_work_facets'],'reference':d['text'],'source_group':c['source_group']}
    if c['source_group']=='a_interview':job['interview_context']=c['interview_context']
    jobs.append(job)
 dump('used-prior-judgments.json',used);dump('new-judge-jobs.json',jobs);print(f'{len(seen)} unique pairs: {len(used)} reused, {len(jobs)} new')
if __name__=='__main__':main()

