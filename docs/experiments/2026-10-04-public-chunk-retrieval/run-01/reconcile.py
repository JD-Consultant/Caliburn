"""Optional exact-source quote restoration only; raw grades/responses stay untouched."""
from pipeline import *

def normalized(value):
    chars=[];positions=[]
    for i,c in enumerate(value):
        if c.isspace():continue
        chars.append('，' if c==',' else c);positions.append(i)
    return ''.join(chars),positions

def restore(quote,source):
    a,_=normalized(quote);b,positions=normalized(source)
    if not a:return None
    start=b.find(a)
    if start<0 or b.find(a,start+1)>=0:return None
    return source[positions[start]:positions[start+len(a)-1]+1]

def main():
    jobs={j['job_id']:j for j in read(HERE/'new-judge-jobs.json')}
    valid={r['job_id'] for r in read(HERE/'judgments.json')}
    fixed=[];log=[];unresolved=[]
    usage={r['job_id']:r for r in [json.loads(s) for s in (HERE/'judge-usage.jsonl').read_text(encoding='utf-8').splitlines()]}
    for jobid,job in jobs.items():
        if jobid in valid:continue
        path=HERE/'judge-trials'/('formal-'+jobid+'-response.json')
        if not path.exists():unresolved.append({'job_id':jobid,'reason':'no completed response'});continue
        response=read(path)
        if response['status']!='completed':unresolved.append({'job_id':jobid,'reason':'not completed'});continue
        text=''.join(c['text'] for item in response['output'] if item['type']=='message' for c in item['content'] if c['type']=='output_text')
        judgment=json.loads(text);edits=[]
        for i,evidence in enumerate(judgment['evidence']):
            for field,source in (('employee_quote',job['employee']),('reference_quote',job['reference'])):
                before=evidence[field]
                if before in source:continue
                after=restore(before,source)
                if after is not None:
                    evidence[field]=after;edits.append({'index':i,'field':field,'before':before,'after':after})
        try:
            validate_judgment(judgment,job['employee'],job['reference'])
            assert all(f in job['main_facets'] for f in judgment['main_work'])
        except (ValueError,AssertionError) as error:
            unresolved.append({'job_id':jobid,'reason':str(error)});continue
        if not edits:unresolved.append({'job_id':jobid,'reason':'not a literal-spacing/comma problem'});continue
        fixed.append({'job_id':jobid,'phase':'formal','case_id':job['case_id'],'document_id':job['document_id'],
                      'judgment':judgment,'employee_sha256':text_sha(job['employee']),'document_sha256':text_sha(job['reference']),
                      'seconds':usage[jobid]['seconds'],'quote_reconciled':True})
        log.append({'job_id':jobid,'case_id':job['case_id'],'document_id':job['document_id'],
                    'grade_unchanged':True,'edits':edits,'rule':'unique exact source substring after whitespace removal / comma equivalence'})
    dump('judgments-reconciled.json',fixed)
    dump('grading-reconciliation.json',{'reconciled':len(fixed),'changes':log,'unresolved':unresolved,
                                      'no_model_rerun':True,'raw_judgments_and_failures_unchanged':True})
    print(json.dumps(read(HERE/'grading-reconciliation.json'),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
