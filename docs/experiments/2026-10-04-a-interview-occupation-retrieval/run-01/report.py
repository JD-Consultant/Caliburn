import statistics
from decimal import Decimal
from pipeline import *


def main():
    check_manifest()
    cases = {c['case_id']:c for c in read(HERE/'cases.json')}
    corpus = {d['id']:d for d in read(HERE/'corpus.json')}
    judgments = {(r['case_id'],r['document_id']):r['judgment'] for r in read(HERE/'judgments.json')}
    results = read(HERE/'results.json')
    timing = {(r['case_id'],r['method']):r for r in read(HERE/'timing-summary.json')}
    embeddings = {r['query_id']:r for r in read(HERE/'query-vectors.json')}
    usage = [json.loads(line) for line in (HERE/'judge-usage.jsonl').read_text(encoding='utf-8').splitlines()]
    cost = sum(Decimal(row['accounted_usd']) for row in usage)
    graded, lines = [], ['# A 訪談原文的四種方法：逐份結果', '',
        '合成員工／歷史自然 A 訪談；單一模型 v2 正文盲評，不是真人驗收或全庫 Recall。所有方法使用相同完整員工事實判讀，初始 I01/I02 只是同人第一則回答的配對控制。逐份分級，不作總分／平均分。', '',
        'R01 完整原文 dense；R02 完整原文＋rerank；R03 工作主題分段＋RRF；R04 相同分段＋rerank＋RRF。N20／全域去重 K5／RRF k2；I01 初始 dense，I02 初始＋rerank。', '']
    for case_id, case in cases.items():
        lines += [f"## {case_id}：{case['label']}", '',
                  f"{case['turn_count']} 輪；完整員工原話 {len(case['employee_statement'])} 字元；搜尋含必要問題的原文 {len(case['interview_context'])} 字元。", '']
        for group in (g for g in results if g['case_id']==case_id):
            selected = []
            for index, hit in enumerate(group['selected'],1):
                judgment = judgments.get((case_id,hit['id']))
                selected.append({'rank':index,'document_id':hit['id'],'title':corpus[hit['id']]['title'],
                                 'retrieval':hit,'validated':judgment is not None,
                                 **(judgment or {'grade':None,'uncertain':True,'main_work':[],'reason':'評審結果未通過來源核對','evidence':[],'limitations':[]})})
            row = {'case_id':case_id,'method':group['method'],'selected':selected,
                   'characters':group['characters'],'query_count':len(group['query_ids']),
                   'serial_embedding_seconds':sum(embeddings[q]['embed_seconds'] for q in group['query_ids']),
                   **timing[(case_id,group['method'])]}
            graded.append(row)
            labels = [str(s['grade']) if s['grade'] is not None else '不確定／未核對' for s in selected]
            lines += [f"### {group['method']}：{'、'.join(labels)}", '',
                f"暖機中位 {row['median_seconds']:.3f}s（三筆）；新 embedding 串行 {row['serial_embedding_seconds']:.3f}s；{row['query_count']} 個查詢；最終正文 {group['characters']:,} 字元。", '',
                '| 名次 | 公版 | 分級 | 理由／限制 |', '|---:|---|---:|---|']
            for item in selected:
                lines.append(f"| {item['rank']} | {item['title']}（{item['document_id']}） | {item['grade'] if item['grade'] is not None else '不確定'} | {item['reason'].replace('|','／')} |")
            lines.append('')
    lines += ['## 用量及限制', '',
        f"{len(usage)} Responses；已知／預留用量估算 US${cost}，不是帳單。七例沿上一輪同錨點規則回歸；領域粒度、跨對象 1/2 界線仍有疑義。初始與後期差別同時包括資訊量、重複、必要問題與更正，不能分離純因果。", '',
        '每案 query 數不同，分段時間須按實際查詢數判讀；全部使用暖機模型與已算好的向量，首次 embedding 及載入另列。沒有測全端、真人、Memory、自動分段、ANN 或 JD/PDF 收尾。原始逐字證據與所有時序見 graded-results.json／cases.json／queries.json／judge-trials/。', '']
    dump('graded-results.json',graded)
    with (HERE/'report.md').open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('\n'.join(lines))
    print(f'Reported {len(graded)} groups, {len(judgments)} validated unique pairs')


if __name__ == '__main__':
    main()
