from datetime import datetime, timezone
from pipeline import *
from projection import project_turns, query_from_units, span

SOURCE = ROOT / 'docs/experiments/product-validation/data/instruction-experiments-2026-10-01/runs'
CONFIG = [
    {'case_id':'H01', 'file':'q3-course_admin-1.json', 'label':'課程行政',
     'questions':[5,11,12], 'major':['成人進修課程的報名、課前安排與異動通知、出席紀錄等行政作業'],
     'groups':[('報名與資料核對',[1,2,7,8,9,10]),('課前安排及通知',[3,4,11]),('出席紀錄及統計',[4,5,6,12])]},
    {'case_id':'H02', 'file':'q3-warehouse-1.json', 'label':'倉庫作業',
     'questions':[3,6,8,10,11,12], 'major':['貨品收貨上架、揀貨、盤點與退貨處理等倉儲現場作業'],
     'groups':[('收貨與上架',[1,2,3,4]),('揀貨補貨及搬運',[5,6,11,12]),('盤點',[7,8]),('退貨作業及分工',[2,5,9,10])]},
    {'case_id':'H03', 'file':'long-procurement-1.json', 'label':'採購供應協調',
     'questions':[4,11,15,18,19,20,21,23,24,27,28,29,30,31,32,33,34,36,37,39,41,42,43,44,45],
     'major':['原物料與包材的請購下單、交期與異常協調、供應商管理等採購工作'],
     'groups':[('需求、詢價及下單',[1,3,4,12,13,14,15,17,22,23,24,25,26,27,28,34,37,38,39]),
               ('交期與來料異常',[2,5,10,11,29,35,36]),
               ('供應商資料及評鑑稽核',[7,8,9,16,18,19,20,21,30,31,32]),
               ('付款文件與進口交接',[6,43]),
               ('其他範圍、包材與年度協作',[33,40,41,42,44,45])]},
]


def main():
    sums = {}
    for line in (SOURCE / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest, name = line.split(maxsplit=1)
        sums[name.lstrip('*')] = digest
    cases, queries = [], []
    for config in CONFIG:
        path = SOURCE / config['file']
        assert sha(path) == sums[config['file']]
        source = read(path)
        turns = source['turns']
        units = project_turns(turns, set(config['questions']))
        context, source_spans = query_from_units(units, range(1, len(turns)+1))
        employee = '\n'.join(turn['employee'] for turn in turns)
        case = {'case_id':config['case_id'], 'label':config['label'],
                'source_path':str(path.relative_to(ROOT)).replace('\\','/'), 'source_sha256':sha(path),
                'source_kind':'historical natural A / synthetic employee', 'turn_count':len(turns),
                'employee_statement':employee, 'interview_context':context, 'units':units,
                'major_work_facets':config['major'], 'manual_question_turns':config['questions'],
                'manual_groups':[{'theme':label,'answer_turns':ids} for label,ids in config['groups']]}
        cases.append(case)
        initial = turns[0]['employee']
        def add(variant, index, text, spans, theme=None):
            queries.append({'query_id':f"{case['case_id']}-{variant}-{index}", 'case_id':case['case_id'],
                            'variant':variant, 'text':text, 'text_sha256':text_sha(text),
                            'source_spans':spans, 'theme_metadata_not_embedded':theme})
        add('initial',1,initial,[units[0]['answer']])
        add('whole',1,context,source_spans)
        anchor = span(1,'employee',initial,0,initial.index('。')+1)
        covered = set()
        for index,(theme,ids) in enumerate(config['groups'],1):
            text,spans = query_from_units(units,ids,anchor)
            add('segments',index,text,spans,theme)
            covered.update(ids)
        assert covered == set(range(1,len(turns)+1))
    dump('cases.json',cases)
    dump('queries.json',queries)
    dump('corpus.json',read(OLD/'prepared.json')['corpus'])
    # Manifest is made only after all execution scripts exist; no rankings yet.
    own = [HERE/name for name in ('protocol.md','pipeline.py','projection.py','test_sources.py','prepare.py',
           'run.py','gpu_worker.py','judge.py','report.py','verify.py','cases.json','queries.json','corpus.json',
           'judge-prompt.txt','judge-schema.json')]
    previous = PARENT.parent/'2026-10-04-representative-occupation-top5/run-01'
    inputs = own+[SOURCE/c['file'] for c in CONFIG]+[SOURCE/'SHA256SUMS.txt',DOC_CACHE,OLD/'prepared.json',OLD/'evaluate.py',
                    previous/'artifact-hashes.json',previous/'judge-prompt-02.txt',previous/'judge-schema.json']
    dump('execution-manifest.json',{'created_utc':datetime.now(timezone.utc).isoformat(), 'before_new_rankings':True,
         'authorization':'user requested four methods on original A interviews and selected employee answers with necessary questions',
         'max_cost_usd':'1.00','max_responses':100,'max_output_tokens':4096,'max_seconds':1800,
         'n':20,'final_k':5,'rrf_k':2,
         'inputs':{str(path.relative_to(ROOT)).replace('\\','/'):{'sha256':sha(path),'bytes':path.stat().st_size} for path in inputs}})
    print(f'Frozen {len(cases)} source interviews, {len(queries)} queries; no new rankings')


if __name__ == '__main__':
    main()
