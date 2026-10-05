"""Export actual formal source bindings from this run's dedicated PostgreSQL."""
import sys, subprocess
from common import *
sys.path.insert(0,str(ROOT/'apps/api/src'))
import psycopg
def main():
 check_manifest();isolation=read(HERE/'database-isolation.json')
 assert isolation['container']=='caliburn-rag-memory-pg-20261004' and isolation['port']==55442 and isolation['database']=='caliburn_rag_memory_test'
 info=json.loads(subprocess.check_output(['docker','inspect',isolation['container']],text=True))[0]
 env=dict(v.split('=',1) for v in info['Config']['Env'] if '=' in v)
 captures=[json.loads(v) for v in (HERE/'memory-captures.jsonl').read_text(encoding='utf-8').splitlines()]
 data=[]
 with psycopg.connect(host='127.0.0.1',port=55442,dbname=isolation['database'],user=env['POSTGRES_USER'],password=env['POSTGRES_PASSWORD'],options='-c search_path='+isolation['schema']) as connection:
  for cap in captures:
   snapshot=read(HERE/'snapshots'/f"{cap['case_id']}.json")
   rows=connection.execute('SELECT f.source_id,f.interview_sequence,t.speaker,t.interview_text FROM formal_interviews f JOIN interview_texts t ON f.job_file_id=t.job_file_id AND f.source_id=t.source_id WHERE f.job_file_id=%s AND f.interview_sequence<=%s ORDER BY f.interview_sequence',(cap['job_file_id'],snapshot['snapshot']['covered_through_sequence'])).fetchall()
   bindings=[{'source_id':str(r[0]),'interview_sequence':r[1],'speaker':r[2],'text':r[3]} for r in rows]
   originals=read(HERE/'replay-messages.json')[cap['case_id']]
   assert [{'interview_sequence':r['interview_sequence'],'speaker':r['speaker'],'text':r['text']} for r in bindings]==originals[:snapshot['snapshot']['covered_through_sequence']]
   ids={b['source_id'] for b in bindings};situations={o['object_id']:o for o in snapshot['objects'] if o['layer']=='work_situation'}
   for o in snapshot['objects']:
    assert set(o['interview_references']).issubset(ids)
    for ref in o['work_situation_references']:
     assert ref['object_id'] in situations and ref['revision_id']==situations[ref['object_id']]['revision_id']
   data.append({'case_id':cap['case_id'],'snapshot_id':snapshot['snapshot']['snapshot_id'],'covered_through_sequence':snapshot['snapshot']['covered_through_sequence'],'bindings':bindings,'all_reference_scopes_valid':True})
 dump('source-bindings.json',data);print('formal source text and fixed reference scopes verified for '+str(len(data))+' cases')
if __name__=='__main__':main()
