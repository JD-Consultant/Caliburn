import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def p(text,**kwargs):return {'type':'p',**kwargs,'children':[{'text':text}]}
def section(kind,title,*children):return {'type':'jd_section','section_kind':kind,'children':[{'type':'h2','children':[{'text':title}]},*children]}
def group(kind,*texts):return {'type':kind,'children':[p(t) for t in texts]}
monthly='依服務安排每月檢查設備狀態，核對異常訊息並記錄需處理事項；超出本人授權的處置交主管決定。'
corrected='僅對已約定服務的設備每月檢查狀態，核對異常訊息並記錄需處理事項；未約定者不做固定月檢，超出本人授權的處置交主管決定。'
fault='接到操作員異常描述後對照故障訊息與設備狀況，區分零件磨耗與外物干涉；處理已授權的機械調整，電控程式由另一職位處理，修後驗證並交接未排除問題。'
value=[section('identity','職務基本資料',p('設備維護工程師')),
 section('purpose','職務目的',p('維持服務範圍內設備的可用狀態，將異常與未排除問題交接相關人員。')),
 section('work','主要職責與工作任務',{'type':'jd_duty','children':[{'type':'h3','children':[{'text':'設備維護與異常處理'}]},
  {'type':'jd_task','children':[p('設備月檢'),p(monthly),group('jd_outcomes','設備狀態紀錄','待處理事項清單'),group('jd_requirements','記錄設備與檢查日期','異常註明觀察依據','超出授權範圍交主管決定')]},
  {'type':'jd_task','children':[p('故障診斷與處理'),p(fault),group('jd_outcomes','完成驗證的處理結果','可接續的維修紀錄'),group('jd_requirements','保留故障訊息與判斷依據','未排除問題交接操作員','不自行修改電控程式')]}]}),
 section('knowledge','所需知識',{'type':'jd_knowledge','children':[p('设备訊息與機械狀態的對應'),p('用於月檢辨識異常與故障判斷。')]},
         {'type':'jd_knowledge','children':[p('機械處置的授權與交接界線'),p('分辨本人處理、主管決定與電控職位責任。')]}),
 section('skills','所需技能',{'type':'jd_skill','children':[p('交叉比對狀態與訊息'),p('將觀察與故障訊息比對，區分需進一步處理的差異。')]},
         {'type':'jd_skill','children':[p('機械調整後驗證與交接'),p('確認處理結果並說明尚未排除的問題。')]}),
 section('conditions','工作條件與必要資格',p('本人僅處理已授權機械工作，電控程式由另一職位處理；其他必要資格尚未說明。'))]
data={'synthetic':True,'purpose':'Fixed engineering fixture; not natural model or P3/P6 quality evidence.',
 'utterances':{'intro':'我是設備維護工程師，想整理自己的工作。',
 'draft':'我的工作是設備月檢與故障處理，維持服務範圍內設備可用。依服务安排每月檢查狀態，核對異常訊息，留下設備狀態紀錄與待處理清單，記設備與日期、觀察依據；超出授權交主管決定。故障時依操作員描述對照訊息與機械狀況，分辨磨耗與外物干涉，只做已授權機械調整，電控程式由另一職位處理。修後驗證，保留判斷依據與維修紀錄，未排除問題交接操作員。我需要懂訊息與機械狀態對應、授權交接界線，兩項工作都用交叉比對；故障另需調整後驗證與交接。其他資格還沒說明。請先整理這些工作。',
 'correct':'更正月檢範圍：僅對已約定服務的設備每月檢查；未約定者不做固定月檢。其他故障處理都不變。',
 'continue':'我剛在文件补上交接文字，請保留手改，並把職務目的改為維持服務範圍內設備可用，清楚交接異常與未排除問題。',
 'thanks':'目前先這樣，謝謝。',
 'lost':'請把職務目的補為維持服務範圍內設備可用，清楚交接異常與未排除問題，供後續維護接續。',
 'cancel':'我先想一下，這輪請稍候。'},
 'expected_initial_content':value,'monthly_original':monthly,'monthly_corrected':corrected,'fault_description':fault,
 'manual_text':'未排除問題交接操作員，並附設備識別資訊。',
 'continued_purpose':'維持服務範圍內設備可用，清楚交接異常與未排除問題。',
 'lost_purpose':'維持服務範圍內設備可用，清楚交接異常與未排除問題，供後續維護接續。',
 'synthetic_tool_intents':{'draft':['read_file','read_file','read_file','jd_read','read_conversation','jd_edit','jd_read','jd_edit','jd_change_read'],
 'correct':['jd_read','read_conversation','jd_edit'], 'continue':['jd_read','jd_edit'],'lost':['jd_read','jd_edit']}}
(ROOT/'experiments/jd-editor/fixtures/core-scenario.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
