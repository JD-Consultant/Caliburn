import random
from pipeline import *

def main():
    check_manifest()
    existing={(r['case_id'],r['document_id']):r for r in read(HERE/'reused-judgments.json')}
    unique=sorted({(r['case_id'],p['id']) for r in read(HERE/'results.json') for p in r['selected']})
    missing=[pair for pair in unique if pair not in existing]
    random.Random(20261004).shuffle(missing)
    cases={c['case_id']:c for c in read(HERE/'cases.json')};docs={d['id']:d for d in read(HERE/'corpus.json')}
    jobs=[{'job_id':f'J{i:03d}','case_id':case,'document_id':doc,
           'employee':cases[case]['employee_statement'],'reference':docs[doc]['text'],
           'main_facets':cases[case]['major_work_facets'],'source_group':cases[case]['source_group'],
           'interview_context':cases[case].get('interview_context','')}
          for i,(case,doc) in enumerate(missing,1)]
    assert len(jobs)<=100
    dump('new-judge-jobs.json',jobs)
    dump('grading-pool.json',{'unique_pairs':len(unique),'reused_pairs':len(unique)-len(jobs),'new_pairs':len(jobs),
         'pairs':[{'case_id':c,'document_id':d,'reused':(c,d) in existing} for c,d in unique]})
    print(json.dumps(read(HERE/'grading-pool.json')|{'pairs':'saved'}),flush=True)

if __name__=='__main__':main()
