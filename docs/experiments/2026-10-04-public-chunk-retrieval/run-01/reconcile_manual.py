"""Three inspected source omissions, recorded separately without grade changes."""
from pipeline import *

def main():
    jobs={j['job_id']:j for j in read(HERE/'new-judge-jobs.json')}
    corrections={
      'J014':('employee_quote','我會寫處理訂單的 API、權限檢查和商業規則','我也會寫處理訂單的 API、權限檢查和商業規則','也'),
      'J034':('employee_quote','我會寫處理訂單的 API、權限檢查和商業規則','我也會寫處理訂單的 API、權限檢查和商業規則','也'),
      'J016':('reference_quote','判別熱銷/滯銷電器商品,並視庫存量進(退)貨。','判別熱銷/滯銷電器商品,並視庫存量進行進(退)貨。','進行')}
    rows=read(HERE/'judgments-reconciled.json');log=[]
    usage={r['job_id']:r for r in [json.loads(s) for s in (HERE/'judge-usage.jsonl').read_text(encoding='utf-8').splitlines()]}
    for jobid,(field,before,after,omission) in corrections.items():
        j=jobs[jobid];source=j['employee'] if field=='employee_quote' else j['reference']
        assert source.count(after)==1 and after.replace(omission,'',1)==before
        response=read(HERE/'judge-trials'/('formal-'+jobid+'-response.json'))
        text=''.join(c['text'] for i in response['output'] if i['type']=='message' for c in i['content'] if c['type']=='output_text')
        original=json.loads(text);value=json.loads(text)
        matches=[i for i,e in enumerate(value['evidence']) if e[field]==before]
        assert len(matches)==1
        value['evidence'][matches[0]][field]=after
        validate_judgment(value,j['employee'],j['reference'])
        assert value['grade']==original['grade'] and value['reason']==original['reason']
        rows.append({'job_id':jobid,'phase':'formal','case_id':j['case_id'],'document_id':j['document_id'],
                    'judgment':value,'employee_sha256':text_sha(j['employee']),'document_sha256':text_sha(j['reference']),
                    'seconds':usage[jobid]['seconds'],'quote_reconciled':True})
        log.append({'job_id':jobid,'case_id':j['case_id'],'document_id':j['document_id'],'field':field,'index':matches[0],
                    'before':before,'after':after,'restored_omission':omission,'grade_unchanged':True,'source_occurrences':1})
    dump('judgments-reconciled-02.json',rows)
    dump('grading-reconciliation-02.json',{'automatic_spacing_comma_restorations':3,'manual_omission_restorations':3,
         'manual_changes':log,'unresolved':[],'new_model_calls':0,'raw_responses_failures_and29_judgments_preserved':True})
    print('3 explicit omissions restored, total6 quote-reconciled; grades unchanged',flush=True)

if __name__=='__main__':main()
