"""List ordinal grades separately; no sum, mean, nDCG or invented recall."""
import statistics
from pipeline import *


def main():
    check_manifest('analysis-manifest.json')
    results = read(HERE / 'results.json')
    grades = {(r['case_id'],r['document_id']):r for r in read(HERE / 'judgments-02.json')}
    corpus = {d['id']:d for d in read(HERE / 'corpus.json')}
    cases = {c['case_id']:c for c in read(PARENT / 'cases-v1.json')['cases']}
    timings = {(r['case_id'],r['method']):r for r in read(HERE / 'timing-summary-03.json')}
    embedding = {r['query_id']:r for r in read(HERE / 'query-vectors.json')}
    rows, text = [], ['# 五份固定需求：代表主要職位的前五比較', '',
        '本批是五案開發比較與 gpt-6-luna／high 的 v2 盲評，不是真人真值、完整 Recall 或 JD 收尾驗收。分級逐份列出，不作總分或平均分。', '',
        'R01 整段 dense；R02 整段 dense＋rerank；R03 保留脈絡分段 dense＋RRF；R04 同分段 dense＋rerank＋RRF。各查詢 N20，去重後員工全域 K5，RRF k2。', '',
        '時間為實際暖機 DB／GPU／檔案交接／合併的中位數，使用已算好的查詢向量。F01-R02 首筆含 startup（59.194s）另列，該組兩個暖機樣本，其餘組三個；新 embedding 串行實測另列，F01 整段首筆 embedding 亦含首用成本，不報 p95。', '']
    for case_id, case in cases.items():
        text += [f"## {case_id}：{case['discussion_label']}", '', '主要工作：'+'；'.join(case['major_work_facets'])+'。', '']
        for result in [r for r in results if r['case_id']==case_id]:
            method = result['method']
            final = []
            for index, hit in enumerate(result['selected'],1):
                grade = grades[(case_id,hit['id'])]
                final.append({'rank':index,'document_id':hit['id'],'title':corpus[hit['id']]['title'],
                              'retrieval':hit,**grade['judgment']})
            strong = {facet for hit in final if hit['grade']==3 for facet in hit['main_work']}
            partial = {facet for hit in final if hit['grade']==2 for facet in hit['main_work']}
            summary = {'case_id':case_id,'method':method,'selected':final,
                       'strong_main_facets':[facet for facet in case['major_work_facets'] if facet in strong],
                       'partial_only_main_facets':[facet for facet in case['major_work_facets'] if facet in partial-strong],
                       'main_facets_without_2_or_3':[facet for facet in case['major_work_facets'] if facet not in strong|partial],
                       'characters':result['characters'],'query_count':len(result['query_ids']),
                       'pair_count':20*len(result['query_ids']) if method in ('R02','R04') else 0,
                       'serial_embedding_seconds':sum(embedding[q]['embed_seconds'] for q in result['query_ids']),
                       **timings[(case_id,method)]}
            rows.append(summary)
            vector = [str(hit['grade']) if hit['grade'] is not None else '?' for hit in final]
            text += [f"### {method}：[{', '.join(vector)}]", '',
                     f"暖機中位 {summary['median_seconds']:.3f}s（{summary['warm_sample_count']} 筆）；串行 embedding {summary['serial_embedding_seconds']:.3f}s；{summary['query_count']} 查詢／{summary['pair_count']} pairs；正文 {summary['characters']:,} 字元。", '',
                     '| 檢索名次 | 公版／固定來源 | 分級 | 代表主要領域 | 理由／界線 |', '|---|---|---|---|---|']
            for hit in final:
                clean = lambda value: str(value).replace('|','／').replace('\n',' ')
                text.append(f"| {hit['rank']} | {clean(hit['title'])}（{hit['document_id']}） | {hit['grade'] if hit['grade'] is not None else '不確定'} | {clean('；'.join(hit['main_work']))} | {clean(hit['reason'])} |")
            text += ['', '強代表領域：'+'；'.join(summary['strong_main_facets'])+'。',
                     '尚未看到 2／3 分支持的主要領域：'+('；'.join(summary['main_facets_without_2_or_3']) or '無')+'。', '']
    text += ['## 限制與原件', '',
             '同一領域多份 3 不會相加成整位員工的完整支持。逐份證據、部分適用及不確定見 graded-results.json；所有方法、低分及失敗均保留。', '',
             '五案已用於開發比較；只有七個規則例的校準，評審與分段仍需新案例／真人驗證。805 語料可能沒有恰好的職位；前五沒看到不能區分全庫缺來源或檢索漏失。沒有調 N、RRF k、模型、表示自動化或 ANN，因此不能選成正式參數。', '',
             '主要原件：protocol.md 與全部 amendments／manifests、queries.json、dense-rankings.json、database-checks.json、pairs.jsonl、results.json、兩輪 benchmark-results、judge-trials/、judge-usage.jsonl、judgments.json／judgments-02.json。首輪校準 6/7，補清 2/1 邊界後第二輪 7/7；正式49回應有1筆員工引句漏「也」，以來源修正記錄補回，沒有改分或重評。費用及原失敗見 grading-summary.json／grading-reconciliation.json。', '']
    dump('graded-results.json',rows)
    (HERE / 'report.md').write_text('\n'.join(text),encoding='utf-8',newline='\n')
    print(json.dumps([{'case_id':r['case_id'],'method':r['method'],'grades':[d['grade'] for d in r['selected']],
                      'strong_main_facets':r['strong_main_facets'],'missing_main_facets':r['main_facets_without_2_or_3'],
                      'median_seconds':r['median_seconds']} for r in rows],ensure_ascii=False))


if __name__ == '__main__':
    main()
