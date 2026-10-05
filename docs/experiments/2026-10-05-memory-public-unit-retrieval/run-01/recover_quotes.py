"""Six explicit literal citation corrections, preserving every model grade."""
import copy
from common import *
REPAIRS={
 'new-011':('reference_quote','依活動計畫書,進行活動前置確認,並說明活動參與者報到、接待流程、活動進行流程與安全須知。','依活動計劃書,進行活動前置確認,並說明活動參與者報到、接待流程、活動進行流程與安全須知。'),
 'new-012':('reference_quote','統計銷售日報表、月報表或會計報表，以作為商品資料庫分析與預測。','統計銷售日報表、月報表或會計報表,以作為商品資料庫分析與預測。'),
 'new-017':('employee_quote','我會寫處理訂單的 API、權限檢查和商業規則','我也會寫處理訂單的 API、權限檢查和商業規則'),
 'new-031':('reference_quote','依據昇降設備安裝工序,選用適切安裝設備進行安裝作業。','依照昇降設備安裝工序,選用適切安裝設備進行安裝作業。'),
 'new-043':('reference_quote','針對供應商品質異常狀況,開立報告要求供應商提出改善對策，必要時協助供應商完成改善對策。','針對供應商品質異常狀況,開立報告要求供應商提出改善對策,必要時協助供應商完成改善對策。'),
 'new-044':('reference_quote','定期評鑑及監控關鍵原物料供應商製程能力及產品品質，確保供應商具有產出符合採購合約要求之能力。','定期評鑑及監控關鍵原物料供應商製程能力及產品品質,確保供應商具有產出符合採購合約要求之能力。'),
}
def main():
 check_manifest();check_manifest('recovery-code-manifest.json');jobs={j['job_id']:j for j in read(HERE/'new-judge-jobs.json')};valid=read(HERE/'judgments.json');records=[]
 assert {f['job_id'] for f in read(HERE/'grading-summary.json')['failures']}==set(REPAIRS)
 for jid,(field,before,after) in REPAIRS.items():
  job=jobs[jid];response=read(HERE/'judge-trials'/f'formal-01-{jid}-response.json');raw=json.loads(''.join(c['text'] for o in response['output'] if o['type']=='message' for c in o['content'] if c['type']=='output_text'));fixed=copy.deepcopy(raw);changed=0;source=job['employee' if field=='employee_quote' else 'reference']
  assert source.count(after)==1 and before not in source
  for e in fixed['evidence']:
   if e[field]==before:e[field]=after;changed+=1
  assert changed==1
  for key in raw:
   if key!='evidence':assert raw[key]==fixed[key]
  validate_judgment(fixed,job['employee'],job['reference']);assert all(f in job['main_facets'] for f in fixed['main_work'])
  records.append({'job_id':jid,'field':field,'before':before,'after':after,'source_offset':source.index(after),'source_unique_literal_match':True,'grade_unchanged':raw['grade'],'all_non_evidence_fields_unchanged':True,'type':'manual exact source transcription; punctuation or small wording; no new model call'})
  valid.append({'job_id':jid,'phase':'formal-01','case_id':job['case_id'],'document_id':job['document_id'],'judgment':fixed,'employee_sha256':text_sha(job['employee']),'document_sha256':text_sha(job['reference']),'quote_recovered':True,'raw_response_file':f'judge-trials/formal-01-{jid}-response.json'})
 assert len(valid)==45 and len({j['job_id'] for j in valid})==45
 dump('quote-recoveries.json',records);dump('judgments-final.json',sorted(valid,key=lambda j:j['job_id']));dump('grading-recovery-summary.json',{'responses':45,'initial_literal_valid':39,'initial_literal_failures':6,'explicit_source_transcription_repairs':6,'grades_changed':0,'new_model_calls_for_repair':0,'final_literal_valid':45,'semantic_relevance_truth_verified':False})
 print('39 initial valid + 6 explicit citation repairs; 45 valid; no grade or reasoning changes')
if __name__=='__main__':main()
