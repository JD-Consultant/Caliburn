"""Freeze engineering topic judgments before any new reranker result."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIRST = HERE.parent/'2026-10-04-occupation-retrieval'
SECOND = HERE.parent/'2026-10-04-occupation-retrieval-generalization'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    if (HERE/'frozen.json').exists():
        raise ValueError('Labels already frozen')
    corpus = json.loads((FIRST/'corpus.json').read_text(encoding='utf-8'))
    by_id = {r['id']: r for r in corpus}
    original = json.loads((SECOND/'cases.json').read_text(encoding='utf-8'))
    queries = json.loads((SECOND/'run-02/retrieval/queries.json').read_text(encoding='utf-8'))
    # Only confirmed employee actions are mapped. Source roles may contain extra responsibilities.
    maps = {
        'E01': [('診斷小客車故障','SET7231-002v3','T2.1',1),('拆裝修護機件並復驗','SET7231-002v3','T2.2',2),('底盤煞車轉向懸吊檢查修護','SET7231-002v3','T2.4',1),('例行保養','SET7231-002v3','T1.2',2),('廢油工具與工作區維護','SET7231-002v3','T3.2',3)],
        'E02': [('圖面公差判讀','MPM7223-002v3','T1.1',1),('夾持工件與校正','MPM7223-002v3','T2.1',1),('選刀與補償設定','MPM7223-002v3','T3.1',1),('車削加工及異常排除','MPM7223-002v3','T3.3',2),('首件及過程尺寸量測','MPM7223-002v3','T4.1',2),('機台日常保養','MPM7223-002v3','T5.1',3)],
        'E03': [('依配方準備秤量原料','TFB7912-002v3','T1.2',1),('攪拌發酵成形與烘烤裝飾','TFB7912-002v3','T2.1',1),('外觀與内部品質辨別回報','TFB7912-002v3','T2.2',2),('原料庫存期限及異常隔離回報','TFB7912-002v3','T3.1',3),('環境與器具清潔','TFB7912-002v3','T3.2',3)],
        'E04': [('防火牆與網路防禦設定','INM3513-001v4','T2.2',1),('遠端VPN連線設定','INM3513-001v4','T2.3',1),('日誌警示監控調查與授權變更','INM3513-001v4','T3.4',1),('資安事件範圍確認及核准圍堵','INM3513-001v4','T4.4',2),('弱點修補與驗證','INM3513-001v4','T3.2',2)],
        'E05': [('客房清潔鋪床與準備','THM9112-001v3','T1.1',1),('房間設備異常報修','THM9112-001v3','T1.1',2),('遺留物登記交付','THM9112-001v3','T1.3',2),('送毛巾枕頭及客訴回報','THM9112-001v3','T2.1',3),('備品整理補充','THM9112-001v3','T3.1',1)],
        'E06': [('穴盤種子準備與播種','NAO6010-003v3','T1.1',1),('育苗階段灌溉與苗況管理','NAO6010-003v3','T1.3',1),('環控設備操作及簡易異常處理','NAO6010-003v3','T1.4',2),('環境數據紀錄','NAO6010-003v3','T1.5',2),('病蟲害辨認及通報','NAO6010-003v3','T2.1',2),('出貨包裝','NAO6010-003v3','T3.2',2)],
        'E07': [('工具材料與安全準備','MPM7212-001v3','T1.1',1),('清理接合面與銲前處理','MPM7212-001v3','T1.2',1),('參數銲材定位與銲接','MPM7212-001v3','T2.1',1),('清除熔渣外觀及變形自檢','MPM7212-001v3','T2.2',2),('設備簡易維護及紀錄','MPM7212-001v3','T2.3',3)],
        'E08': [('需求毛況確認及清潔美容','PIC5193-001v3','T1.1',1),('安全保定與造型修剪','PIC5193-001v3','T1.2',2),('異常辨識停工告知與轉介','PIC5193-001v3','T1.4',1),('工具環境清潔消毒','PIC5193-001v3','T1.3',3),('居家照顧提醒','PIC5193-001v3','T2.2',2)],
    }
    documents = {}
    for key in {v[1] for values in maps.values() for v in values}|{'BAS3323-001v4','MMP4321-003v4'}:
        row = by_id[key]
        path = ROOT/row['source']
        if sha(path) != row['source_sha256']:
            raise ValueError('Public source changed')
        documents[key] = json.loads(path.read_text(encoding='utf-8'))

    def topic(case, index, name, doc_id, task_code, message_index, secondary=False):
        matches = [t for u in documents[doc_id]['ocs_content']['ocu_units'] for t in u['tasks']
                   if any(x['code'] == task_code for x in t['task_codes'])]
        if len(matches) != 1:
            raise ValueError('Task reference is ambiguous')
        task = matches[0]
        return {'topic_id':f"{case['case_id']}-T{index:02}", 'work':name,'secondary':secondary,
                'employee_message':message_index,'employee_quote':case['employee_messages'][message_index-1],
                'support':[{'id':doc_id,'source':by_id[doc_id]['source'],'source_sha256':by_id[doc_id]['source_sha256'],
                            'task_code':task_code,'task_name':task['task_codes'],
                            'indicators':[p for b in task['competency_blocks'] for p in b['indicators']]}]}

    cases = []
    for old in original:
        case = {**old,'split':'regression','original_split':old['split']}
        case['topics'] = [topic(case,i,*values) for i,values in enumerate(maps.get(case['case_id'],[]),1)]
        case['unscored'] = 'Topic labels cover listed supported actions, not every sentence, frequency or authority boundary. Negatives have no exhaustive task-level corpus labels.'
        cases.append(case)
    extras = [
        ('M01','E01','development','每週我另外處理車廠零件的請購，先核對規格、數量與需要日期，向供應商要報價，比較價格、交期與過去品質，提出選擇理由。主管核准後我開訂單、追未到貨交期；收到材料的點收由倉庫同事做，我不自行決定替代零件。','每週零件詢比價下單與催貨','BAS3323-001v4','T1.2'),
        ('M02','E04','holdout','每個月我還負責資訊設備的採買執行，核對同事核准的規格、數量和預算，蒐集廠商價格與交貨期限並製作比較資料，交主管決定供應商。決定後由我向廠商下單、追交期，驗收由提出需求的人確認；我不決定全公司採購政策。','每月設備詢比價下單與交期追蹤','BAS3323-001v4','T1.2'),
        ('M03','E05','development','我每月另外輪值做備品庫房盤點，把儲位的實物和庫存清單逐項核對，記下品名、數量與差異，整理盤點差異表交庫房主管。帳面調整由主管核准，我不直接把差額改掉；這項工作和每天清潔客房分開做。','每月備品實物帳面盤點及差異回報','MMP4321-003v4','T1.3'),
        ('M04','E08','holdout','每季我另外負責店內用品庫房的盤點，逐項清點洗劑、護毛用品和備用工具，核對庫存清單，整理短少與多出的数量並回報負責人。庫存資料的差額要核准才調整，我不自行把差異抹掉；平日美容後記耗材缺口不能代替這次完整盤點。','每季用品庫房盤點與差異報告','MMP4321-003v4','T1.3'),
    ]
    original_by_id = {c['case_id']:c for c in cases}
    for new_id,base_id,split,addition,name,doc_id,task_code in extras:
        base = original_by_id[base_id]
        case = {**base,'case_id':new_id,'split':split,'original_split':None,
                'domain':'mixed_'+base['domain'],'employee_messages':base['employee_messages']+[addition],
                'grades':{**base['grades'],doc_id:2},'derived_from':base_id,
                'rationale':'混合合成工作；採購／零售倉儲標準只作局部任務參考，不推定兼任整份職位。'}
        case['topics'] = [topic(case,i,*values) for i,values in enumerate(maps[base_id],1)]
        case['topics'].append(topic(case,len(case['topics'])+1,name,doc_id,task_code,4,True))
        cases.append(case)
        queries.append({'case_id':new_id,'raw_employee':'\n\n'.join(case['employee_messages'])})
    dump(HERE/'cases.json',cases)
    dump(HERE/'queries.json',queries)
    sources = [FIRST/'corpus.json',SECOND/'cases.json',SECOND/'run-02/retrieval/queries.json',
               SECOND/'run-02/retrieval/fixed-rankings.jsonl',HERE/'protocol.md',HERE/'cases.json',HERE/'queries.json',HERE/'prepare.py']
    dump(HERE/'frozen.json',{'sources':{p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        'topic_count':sum(len(c['topics']) for c in cases),'cases':len(cases),
        'new_holdout':['M02','M04'],'labels':'engineering non-exhaustive source-supported task mapping',
        'unscored_examples':['E01 偶爾示範新人扭力工具','E03 進貨驗收溫度、每週兩次頻率與協助新配方',
                            'E05 督導放行、清潔劑稀釋','E06 隔離苗株、出貨點數及管線清洗',
                            'E08 新人示範、耗材缺口'],'full_employee_coverage_verified':False})
    print(f'{len(cases)} cases, {sum(len(c["topics"]) for c in cases)} labeled topics frozen')


if __name__ == '__main__':
    main()
