"""Create frozen synthetic labels; no embeddings, retrieval or model calls."""
import copy
import hashlib
import json
from datetime import datetime, UTC
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREVIOUS = HERE.parent/'2026-10-04-retrieve-rerank'
CORPUS = HERE.parent/'2026-10-04-occupation-retrieval/corpus.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(name,value):
    with (HERE/name).open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    corpus = {r['id']:r for r in json.loads(CORPUS.read_text(encoding='utf-8'))}
    old = json.loads((PREVIOUS/'cases-v4.json').read_text(encoding='utf-8'))
    development = copy.deepcopy(old)
    for case in development:
        case['previous_split'] = case['split']
        case['split'] = 'development'
    new = [
      {'case_id':'H01','split':'new_holdout','kind':'positive','employee_messages':[
        '每天我在吧檯詢問客人要的口味與飲品，協助點單。我會依當天咖啡豆狀態調整磨豆刻度，試喝後調整萃取時間與粉量，按店裡配方做濃縮、拿鐵和手沖，奶泡也由我打好。',
        '飲品送出時我會解釋風味；我自己操作收銀系統、核對實收金額和當班結帳表。客人反映太苦或等太久時，我先溝通處理並記錄回饋，超過授權的退費要請店長確認。',
        '收班後我清潔消毒咖啡機相關器具、杯皿及吧檯，放回指定位置並填保養清潔紀錄。咖啡豆烘焙與門市人事排班由別人負責，我沒有決定整店菜單或招募員工。',
        '另外每週我負責店內的帳務核對：按既定會計科目把各項收入支出登到總帳和明細帳，逐筆對收付款憑證，確認分類及金額相符。發現差額就找經辦人查明，整理更正資料交主管確認，不能自行抹平差異；這項工作不是只印收銀機日結表。'
      ],'specs':[
        ('飲品介紹與點單',1,False,'TFB5131-002v3','T1.1',['P1.1.1','P1.1.2','P1.1.3']),
        ('磨豆萃取與咖啡奶泡製作',1,False,'TFB5131-002v3','T2.1',['P2.1.1','P2.1.2','P2.1.3','P2.1.4','P2.1.5']),
        ('收款與當班結帳',2,False,'TFB5131-002v3','T1.2',['P1.2.1']),
        ('顧客問題與回饋記錄',2,False,'TFB5131-002v3','T1.3',['P1.3.2','P1.3.3']),
        ('吧檯器具清消與維護紀錄',3,False,'TFB5131-002v3','T3.2',['P3.2.1','P3.2.2','P3.2.3']),
        ('每週總帳明細帳與憑證核對',4,True,'FAC4311-001v2','T2.1',['P2.1.1','P2.1.2','P2.1.3'])]},
      {'case_id':'H02','split':'new_holdout','kind':'positive','employee_messages':[
        '我跟主設計一起聽客戶說海報和型錄需求，把尺寸、文字、圖片風格及視覺元素記下來，找參考照片與素材。素材到齊後，我依主設計指示用繪圖軟體整理出設計初稿和提案資料，由他決定方向。',
        '方案確認後，我按照指示繪製版面與圖像、標明設計細節，配合印刷端討論版面設定及排版，把修改內容記錄下來，協助輸出設計圖及打樣。最後定稿仍要交主設計與客戶確認。',
        '我也把客戶資料、設計作品和各版檔案整理歸檔，更新檔案清單。報價與簽約不是我的權限，我不負責整個品牌策略，也不寫應用程式。',
        '每週另有一項固定責任：依資訊負責人給的程序備份公司訂單資料庫，核對備份是否完成，並在隔離的測試資料庫演練還原，保存備份和復原紀錄。出錯就通報他，沒有擅自修改正式資料表、索引或效能參數的權限。這是資料庫的備份，不是把設計圖複製到隨身碟。'
      ],'specs':[
        ('客戶視覺需求與素材蒐集',1,False,'AVA2172-004v3','T1.1',['P1.1.2','P1.1.3']),
        ('依指示整理設計初稿及提案',1,False,'AVA2172-004v3','T2.1',['P2.1.1','P2.1.2']),
        ('版面繪製排版紀錄與打樣',2,False,'AVA2172-004v3','T2.2',['P2.2.1','P2.2.2','P2.2.3']),
        ('客戶與作品資料歸檔',3,False,'AVA2172-004v3','T1.2',['P1.2.1','P1.2.2']),
        ('每週資料庫備份與測試還原紀錄',4,True,'INM3513-004v4','T3.1',['P3.1.5'])]},
      {'case_id':'H03','split':'new_holdout','kind':'positive','employee_messages':[
        '日常我接收部門和廠商的支出請款，核對原始單據、經辦簽核、會計科目與金額，資料不齊就退回補件。依公司的記帳規則整理應付款項，但付款核准與銀行轉帳由主管處理。',
        '每月我記錄並核對總分類帳與明細帳，逐項對回原始交易，跟經辦單位查明錯誤後更正。我還編製資產負債表、綜合損益表、現金流量表與權益變動表，確認餘額和總帳相符，依報表類別存檔。',
        '人事提供薪資彙整表後，我核對薪資及人事費用文件，製作薪資發放傳票，送主管簽核。薪資制度與人員聘用不是由我決定；我也不負責公司的投資決策或稅務策略。',
        '另外每月由我處理辦公用品採購：收齊各部門品項規格和需求量，找供應商確認條件並比較報價，整理資料送主管核准後下單，追蹤供應商是否按約定時間交貨。有延誤就聯絡供應商及使用部門，不自行超支或改需求。'
      ],'specs':[
        ('請款原始憑證科目與權責核對',1,False,'FAC4311-001v2','T1.1',['P1.1.1','P1.1.2','P1.1.3']),
        ('每月總帳明細帳與原始交易核對',2,False,'FAC4311-001v2','T2.1',['P2.1.1','P2.1.2','P2.1.3']),
        ('編製四大財務報表與餘額核對',2,False,'FAC4311-001v2','T3.1',['P3.1.1','P3.1.2']),
        ('薪資文件核對及發放傳票',3,False,'FAC4311-001v2','T4.1',['P4.1.1','P4.1.2']),
        ('每月用品採購條件報價與交期追蹤',4,True,'BAS3323-001v4','T2.1',['P2.1.1'])]},
      {'case_id':'H04','split':'new_holdout','kind':'positive','employee_messages':[
        '我按家用冷氣的設計圖和現場指示，先核對施工範圍、動線與所需零件，檢查防護措施、消防設備和工具測試裝置是否正常，與施工主管確認支架位置及承重要求，才準備進場。',
        '安裝時我先依檢查表確認絕緣與安全防護完成，再依說明固定支架、設備與配件。我會量尺寸、裁切彎曲管線、焊接冷媒配管，注意焊接汙染，做規定的尺寸和壓力檢查並填紀錄；超出作業指示的異常先問主管。',
        '完工後我清潔工具並歸位，整理現場，填完工紀錄向主管回報。系統設計、工程報價與整家公司的人員排程不是我負責的；目前也沒有承接大型中央空調系統規劃。',
        '每季我還負責公司材料庫房的完整盤點：照庫存清單逐項清點備料和備用工具，核對帳上數量，記錄短少或多出的差異、整理盤點異常報告交主管確認。帳面數字要經核准才調整，不是只替當天施工拿幾個零件。'
      ],'specs':[
        ('施工現場安全及防護檢核',1,False,'SET7127-001v3','T1.1',['P1.1.1','P1.1.2']),
        ('圖面施工範圍工具與支撐準備',1,False,'SET7127-001v3','T2.1',['P2.1.1','P2.1.2','P2.1.3']),
        ('按說明完成安裝固定與防護確認',2,False,'SET7127-001v3','T2.2',['P2.2.1']),
        ('冷媒配管裁焊與尺寸壓力檢查',2,False,'SET7127-001v3','T3.2',['P3.2.1','P3.2.2','P3.2.3','P3.2.4']),
        ('完工清理歸位及紀錄回報',3,False,'SET7127-001v3','T2.3',['P2.3.1','P2.3.2']),
        ('每季材料庫房盤點與異常報告',4,True,'MMP4321-003v4','T1.3',['P1.3.1','P1.3.2','P1.3.3'])]}
    ]
    source_hashes = {}
    for case in new:
        case['topics'] = []
        case['grades'] = {}
        case['hard_negatives'] = []
        case['unscored'] = 'Engineering source labels cover listed actions only; quotes retain frequency, authority and denials. Not exhaustive corpus relevance or employee responsibility truth.'
        for index,(work,passage,secondary,ident,task_code,indicator_codes) in enumerate(case.pop('specs'),1):
            row = corpus[ident]
            assert sha(ROOT/row['source']) == row['source_sha256']
            source_hashes[row['source']] = row['source_sha256']
            doc = json.loads((ROOT/row['source']).read_text(encoding='utf-8'))
            task = next(t for unit in doc['ocs_content']['ocu_units'] for t in unit['tasks'] if any(c['code']==task_code for c in t['task_codes']))
            indicators = {p['code']:p for b in task['competency_blocks'] for p in b['indicators']}
            support = {'id':ident,'source':row['source'],'source_sha256':row['source_sha256'],
                       'task_code':task_code,'task_name':task['task_codes'],
                       'indicators':[indicators[code] for code in indicator_codes],
                       'scope':'Only the described supported action; not all duties of this source position.'}
            case['topics'].append({'topic_id':f"{case['case_id']}-T{index:02}",'work':work,'secondary':secondary,
                                   'employee_message':passage,'employee_quote':case['employee_messages'][passage-1],'support':[support]})
            case['grades'][ident] = max(case['grades'].get(ident,0),2 if secondary else 3)
    assert sum(len(c['topics']) for c in new)==22
    dump('development-cases.json',development)
    dump('holdout-cases.json',new)
    dump('case-manifest.json',{'frozen_utc':datetime.now(UTC).isoformat(),'before_new_embeddings_or_rankings':True,
         'observed_development_employees':18,'development_topics':64,'new_holdout_employees':4,'new_holdout_topics':22,
         'sources':source_hashes,'parent_cases_sha256':sha(PREVIOUS/'cases-v4.json'),
         'files_sha256':{name:sha(HERE/name) for name in ('development-cases.json','holdout-cases.json','freeze_cases.py','protocol.md')},
         'limits':'Synthetic source-derived new combinations; source overlap; no real employee/expert completeness gate.'})
    print('Frozen 18 observed cases/64 topics and 4 unranked new cases/22 topics')


if __name__=='__main__':
    main()
