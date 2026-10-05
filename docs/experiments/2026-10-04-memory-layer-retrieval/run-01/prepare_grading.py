from common import *
def main():
 cases={c['case_id']:c for c in read(HERE/'cases.json')};docs={d['id']:d for d in read(HERE/'corpus.json')}
 prior={(j['case_id'],j['document_id']):j for j in read(HERE/'reused-judgments.json')};new=[];seen=set();used=[]
 for r in read(HERE/'results.json'):
  for p in r['selected']:
   pair=(r['case_id'],p['id'])
   if pair in seen:continue
   seen.add(pair);c=cases[pair[0]];d=docs[pair[1]]
   if pair in prior:
    j=prior[pair];assert j['employee_sha256']==text_sha(c['employee_statement']) and j['document_sha256']==text_sha(d['text'])
    validate_judgment(j['judgment'],c['employee_statement'],d['text']);used.append(j)
   else:
    job={'job_id':'new-'+str(len(new)+1).zfill(3),'case_id':pair[0],'document_id':pair[1],'employee':c['employee_statement'],'main_facets':c['major_work_facets'],'reference':d['text'],'source_group':c['source_group']}
    if c['source_group']=='a_interview':job['interview_context']=c['interview_context']
    new.append(job)
 dump('used-prior-judgments.json',used);dump('new-judge-jobs.json',new)
 print(str(len(seen))+' unique pairs, '+str(len(used))+' reused, '+str(len(new))+' new')
if __name__=='__main__':main()
