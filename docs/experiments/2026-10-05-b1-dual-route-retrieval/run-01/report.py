"""Derive human-readable reports from sealed-input experimental outputs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def write(name, text):
    with (HERE / name).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


def main():
    summaries, results, traces = read('summary.json'), read('results.json'), read('target-ranks.json')
    names = {'O': '原話整段', 'B1-W': 'B1整合', 'B1-S': 'B1逐情境', 'B2-S': 'B2逐理解'}
    head = '''# B1 雙路廣蒐比較結果

2026-10-05。隔離研究已計算並獨立核對。**B1整合與逐情境都需每路Top40才保留12/12已知主要公版、8/8已知面向；原話Top20已達相同已知涵蓋。** B1逐情境在這份固定清單沒有比整合增加命中，query數及候選配對量較多；B1尚未做本輪精搜，不選正式參數或接線。

## 初搜結果

以下每個query的D整份與T任務各取N個不同父公版，完整聯集去重，再跨同員工全部query保留候選；不在聯集後截20，不rerank或選最後五份。

| 輸入 | 每路Top N | 已知公版 | 已知面向 | 排除疑義後公版 | 總query數 | 候選配對量 | 員工去重父數總和 |
|---|---:|---:|---:|---:|---:|---:|---:|
'''
    table = ''
    for s in summaries:
        table += (f'| {names[s["variant"]]} | {s["depth_each_route"]} | '
                  f'{s["known_targets_retained"]}/{s["known_targets_total"]} | '
                  f'{s["known_facets_retained"]}/{s["known_facets_total"]} | '
                  f'{s["clear_targets_retained"]}/{s["clear_targets_total"]} | '
                  f'{s["query_count"]} | {s["query_parent_pair_workload"]} | '
                  f'{s["employee_unique_parents_total"]} |\n')
    body = '''
12份公版沿前輪模型grade3判讀，8面向為7案已有支持的主要工作；H01課程行政的1面向仍未評，不纳入分母，coverage為null。這不是全805公版qrels或完整Recall，也不是人工職位真值。多媒體及資材两份疑義沿原分保留，排除敏感度得相同深度結論。

## 可以作的判斷

- **原話雙路Top20保留控制基線。** 原話的12來源／8面向在三個深度相同，工作量247→480→926；沒有已知增益要求一律加深。
- **B1的Top20唯一已知缺漏是全端共同參考。** 「網站系統設計人員」B1整合／逐情境D29、T48，Top20沒有；Top40從D找回。F01只有一個B1情境，兩種文字相同，不能稱獨立分段實驗改善。B1整合另已由T補回整份單路漏掉的冷氣來源；逐情境的原D單路已找回它，雙路增加候選但未增加本清單已知命中。
- **B1若作下一個精搜候選，先比較整合Top40。** 相同已知涵蓋下，整合8query／485候選配對，逐情境35query／2174配對（4.48倍）；員工去重父數485與1108是另一種數量。還沒驗最後K5品質，不能由候選量直接宣稱整合職位排序更好。
- **Top80沒有本清單增益。** B1整合配對485→949、逐情境2174→4189；這只說已判主要參考，未評的其他有效公版可能增加。

## 方法及驗證範圍

沿八個已觀察合成案例的發布B1/B2，不重新生成、修字或補事實。只用Memory body；B1整合按原文字順序、逐情境沿原物件，非逐句。原話控制保留必要顧問問題；各輸入長度、物件數、可見脈絡不同，不是等成本純改寫比較。單物件W/S相同不是獨立樣本。

同一公版D805／T8068點（含803概述）、本機BGE-M3 1024 dense，沿既有SHA及revision向量，NumPy float64新算exact cosine；父分數為最高chunk，按score再父ID處理同分，正文不截斷。不新算embedding、不重啟Qdrant、不執行Memory、GPU rerank或外部LLM；費用0。這輪資料庫行為控制沿舊真Qdrant輸出，B1新T查詢尚無fresh DB試驗。

63queries、126個完整805父排名及558999 point cosines另存。83個控制（40個O/B2雙路、43個B1整份）與48個舊深度候選結果不變。独立核驗以不同rowwise dot重算向量分數、重建父max／前綴／聯集、96候選組／48target追蹤及12摘要，最大cosine誤差1.34e-15以內；1318個旧seal檔不變。四個向量/重複chunk反例測試觀察未實作Red後Green。以上驗算不是語意真人驗收。

離線運算耗時另存[計算紀錄](offline-compute.json)，不是fresh DB、精搜或App服務延遲；候選配對數也不是已執行的rerank次數。未驗B1最終K5品質、連續Memory更新、真人、新holdout、全庫Recall、ANN、p95或JD完成。既有模型分级、少量Memory忠實度及引句恢復/請求順序疑義沿前輪保留。

原件：[事前協定](protocol.md)、[輸入SHA](input-manifest.json)、[查詢全文](queries.json)、[完整父排名](all-rankings.json)、[point分數](chunk-scores.npz)、[全部96組候選](results.json)、[逐target各query名次](target-ranks.json)、[摘要](summary.json)、[控制](control-checks.json)、[獨立核驗](verification.json)、[進度](progress.md)。最後審查與封存另附，沒有production改動、commit、push或資料清除。
'''
    write('README.md', head + table + body)
    detail = '# B1雙路廣蒐逐案與主要參考追蹤\n\n同協定的初搜候選；只列已有判讀，非全庫Recall。\n\n'
    detail += '| 案例 | 輸入 | 每路Top N | 已知來源 | 已知面向 | query數 | 配對量 | 去重父數 |\n|---|---|---:|---|---|---:|---:|---:|\n'
    for r in results:
        refs = r['known_targets']; facets = r['known_facets']
        label = f'{len(refs["retained_ids"])}/{len(refs["known_ids"])}' if refs['coverage'] is not None else '未評'
        flabel = f'{len(facets["retained"])}/{len(facets["known"])}' if facets['known_coverage'] is not None else '未評'
        detail += f'| {r["case_id"]} | {names[r["variant"]]} | {r["depth_each_route"]} | {label} | {flabel} | {len(r["query_ids"])} | {r["query_parent_pair_workload"]} | {r["employee_unique_parents"]} |\n'
    detail += '\n## 已知主要公版的入池深度\n\n每路最低N為各query D/T名次的最小值，只作診斷，不事後選新深度。詳細各query定位見target-ranks.json。\n\n| 案例 | 輸入 | 公版 | 最佳D | 最佳T | 最低N | 疑義敏感度排除 |\n|---|---|---|---:|---:|---:|---|\n'
    for t in traces:
        detail += f'| {t["case_id"]} | {names[t["variant"]]} | {t["title"]} | {min(p["D"]["rank"] for p in t["paths"])} | {min(p["T"]["rank"] for p in t["paths"])} | {t["minimum_N"]} | {"是" if t["sensitivity_excluded"] else "否"} |\n'
    write('report.md', detail)
    print('Generated README/report from 12 summaries, 96 groups and 48 target traces')


if __name__ == '__main__':
    main()
