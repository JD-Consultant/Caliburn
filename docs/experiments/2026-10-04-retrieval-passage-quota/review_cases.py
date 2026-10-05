"""Apply source-review amendments before any new rankings; keep initial inputs."""
import json
import hashlib
from pathlib import Path
from datetime import datetime, UTC

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases = json.loads((HERE/'holdout-cases.json').read_text(encoding='utf-8'))
    indexed = {c['case_id']:c for c in cases}
    topic = indexed['H01']['topics'][0]
    topic['work'] = '點單與送飲品風味說明'
    topic['employee_message_indices'] = [1,2]
    topic['employee_quote'] = '\n'.join(indexed['H01']['employee_messages'][:2])
    topic['support'][0]['indicators'] = [p for p in topic['support'][0]['indicators'] if p['code'] in ('P1.1.2','P1.1.3')]
    topic = indexed['H01']['topics'][4]
    topic['work'] = '吧檯器具清消復位與清潔紀錄'
    topic['support'][0]['indicators'] = [p for p in topic['support'][0]['indicators'] if p['code']!='P3.2.3']
    topic = indexed['H02']['topics'][4]
    topic['support'][0]['scope'] = 'Only database backup, recovery exercise and backup record in P3.1.5; performance tuning and optimization are explicitly outside employee authority.'
    topic = indexed['H03']['topics'][4]
    old = topic['support'][0]
    doc = json.loads((ROOT/old['source']).read_text(encoding='utf-8'))
    for task_code,codes in [('T1.1',['P1.1.2','P1.1.4']),('T1.2',['P1.2.1','P1.2.2'])]:
        task = next(t for unit in doc['ocs_content']['ocu_units'] for t in unit['tasks'] if any(c['code']==task_code for c in t['task_codes']))
        indicators = {p['code']:p for b in task['competency_blocks'] for p in b['indicators']}
        topic['support'].append({'id':old['id'],'source':old['source'],'source_sha256':old['source_sha256'],
                                'task_code':task_code,'task_name':task['task_codes'],'indicators':[indicators[c] for c in codes],
                                'scope':'Only supplier information/quote comparison and approved order described; no inferred negotiation, contracting or lowest-risk supplier evaluation.'})
    topic = indexed['H04']['topics'][3]
    topic['support'][0]['indicators'] = [p for p in topic['support'][0]['indicators'] if p['code']!='P3.2.3']
    effective = HERE/'holdout-cases-2026-10-04-reviewed.json'
    with effective.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
    record = {'frozen_utc':datetime.now(UTC).isoformat(),'before_new_embeddings_or_rankings':True,
              'scope':'Source annotation correction only; employee_messages and support document IDs unchanged; initial files retained.',
              'effective_holdout_cases':effective.name,'effective_sha256':sha(effective),
              'initial_manifest_sha256':sha(HERE/'case-manifest.json'),'script_sha256':sha(Path(__file__)),
              'amendments':['H01 service quote joins passages1/2; remove unconfirmed recommendation P1.1.1',
                            'H01 cleanup excludes unconfirmed periodic equipment checking/maintenance P3.2.3',
                            'H03 procurement adds exact T1.1/T1.2 support, excludes unmentioned negotiation/contracting',
                            'H02 database P3.1.5 only backup/recovery, excludes tuning; H04 excludes unstated environmental P3.2.3']}
    with (HERE/'case-amendment-01.json').open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print('Source amendments frozen; all16 employee passages and22 topics retained; no rankings generated')


if __name__=='__main__':
    main()
