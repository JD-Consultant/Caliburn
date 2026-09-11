"""Actual managed process crash/reopen; parent only observes, never stops children."""
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import pytest
from test_jd_postgres import jd,prepared
from analysis_agent.jd_contract import revision_ref,manual_operation_id

WORKER=Path(__file__).with_name('jd_lifecycle_process_worker.py')

def run_worker(key,request):
    process=subprocess.Popen([sys.executable,str(WORKER)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,text=True,encoding='utf-8',env={**os.environ,'Q019_LIFECYCLE_INSTALLATION':key},
        creationflags=subprocess.CREATE_NO_WINDOW,close_fds=True)
    stdout,stderr=process.communicate(json.dumps(request)+'\n',timeout=25)
    code=process.returncode
    rows=[json.loads(line) for line in stdout.splitlines() if line.startswith('{')]
    print(json.dumps({'mode':request['mode'],'exit':code,'events':rows,'stderr':stderr},ensure_ascii=False))
    # Release only the observer's handle after actual process exit. No terminate/kill.
    del process
    gc.collect()
    return code,rows,stderr

@pytest.mark.parametrize('mode',['native','after_native','before_commit','after_commit','before_head_lock'])
def test_managed_app_crash_recovers_original_manual_without_candidate_or_replay(jd,mode):
    intent=prepared(jd)
    before=jd.store.current(intent.scope)
    key=str(uuid4())
    installation='task5-app-'+uuid4().hex
    body={'request_key':key,'base_revision_ref':revision_ref(intent.scope,intent.base_id),'value':intent.value}
    code,rows,stderr=run_worker(installation,{'mode':mode,'document':intent.scope.document_id,'key':key,'body':body})
    assert code==73,(rows,stderr)
    assert rows[0]['bootstrap']['prior_group_stopped']
    assert rows[-1]['counts']=={'native':1,'provider':0}
    code,reopened,stderr=run_worker(installation,{'mode':'recover','document':intent.scope.document_id,'key':key})
    assert code==0,(reopened,stderr)
    result=reopened[-1]
    assert result['counts']=={'native':0,'provider':0}
    assert result['pending'] is None and not result['next'] and result['messages']==0 and result['runs']==0
    assert result['recovery']['status']=='available' and not result['recovery']['write_blocked']
    terminal=jd.store.receipt(intent.scope,manual_operation_id(intent.scope,key))
    assert terminal.status==('committed' if mode=='after_commit' else 'save_failed')
    assert jd.store.current(intent.scope).id==(terminal.result_id if mode=='after_commit' else before.id)


def test_whole_app_crash_covers_committed_a_and_outstanding_selection_b(jd):
    intent=prepared(jd)
    sibling=prepared(jd)
    assert jd.manual_save(sibling).status=='committed'
    sibling_before=jd.store.current(sibling.scope)
    key=str(uuid4());installation='task5-two-'+uuid4().hex
    body={'request_key':key,'base_revision_ref':revision_ref(intent.scope,intent.base_id),'value':intent.value}
    code,rows,error=run_worker(installation,{'mode':'two_documents','document':intent.scope.document_id,
        'key':key,'body':body,'sibling':sibling.scope.document_id})
    assert code==73,(rows,error)
    assert rows[-1]['counts']=={'native':2,'provider':0} and rows[-1]['sibling_owner']
    code,reopened,error=run_worker(installation,{'mode':'recover','document':intent.scope.document_id,'key':key})
    assert code==0,(reopened,error)
    assert reopened[-1]['recovery']['result']==rows[-1]['original']
    assert reopened[-1]['counts']=={'native':0,'provider':0}
    assert jd.store.current(sibling.scope)==sibling_before
    code,b,error=run_worker(installation,{'mode':'recover','document':sibling.scope.document_id,'key':str(uuid4())})
    assert code==0 and b[-1]['recovery']['status']=='no_pending' and not b[-1]['recovery']['write_blocked']
    assert b[-1]['counts']=={'native':0,'provider':0}


@pytest.mark.parametrize('mode',['create_before_commit','create_after_commit'])
def test_create_transaction_crash_reenters_same_request_once_without_fake_owner(jd,mode):
    from sqlalchemy import select,func
    from analysis_agent.jd_store import revision,head
    installation='task5-create-'+uuid4().hex;key=str(uuid4())
    code,rows,error=run_worker(installation,{'mode':mode,'key':key})
    assert code==73,(rows,error)
    first=jd.catalog.created_by_request(key,'NL13 exact create')
    assert bool(first)==(mode=='create_after_commit')
    code,reopened,error=run_worker(installation,{'mode':'create_retry','key':key})
    assert code==0,(reopened,error)
    document=reopened[-1]['created']
    assert not reopened[-1]['runs']
    assert reopened[-1]['counts']=={'native':0 if first else 1,'provider':0}
    assert not first or document==first['id']
    with jd.store.engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(head).where(head.c.document_id==document)).scalar_one()==1
        assert connection.execute(select(func.count()).select_from(revision).where(revision.c.document_id==document)).scalar_one()==1
