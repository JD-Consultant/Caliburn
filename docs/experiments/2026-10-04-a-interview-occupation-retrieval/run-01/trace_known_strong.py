"""Post-hoc stage trace of already judged grade-3 pairs; no new retrieval or labels."""
from pipeline import HERE, dump, read, sha


def position(rows, ident):
    return next((index for index, row in enumerate(rows, 1) if row['id'] == ident), None)


def main():
    groups = read(HERE / 'results.json')
    graded = read(HERE / 'graded-results.json')
    dense = {row['query_id']: row['ranked'] for row in read(HERE / 'dense-rankings.json')}
    known = {}
    for group in graded:
        for row in group['selected']:
            if row['grade'] == 3:
                known[(group['case_id'], row['document_id'])] = row
    trace = []
    for (case_id, ident), judgment in sorted(known.items()):
        methods = []
        for group in groups:
            if group['case_id'] != case_id:
                continue
            query_trace = []
            for query_id, ordered_pool in zip(group['query_ids'], group['query_rankings']):
                dense_rank = position(dense[query_id], ident)
                query_trace.append({
                    'query_id': query_id,
                    'full_dense_rank_1_based': dense_rank,
                    'initial_n20_included': dense_rank <= 20,
                    'pool_rank_after_method_order_1_based': position(ordered_pool, ident),
                    'order': 'rerank' if group['method'] in ('I02', 'R02', 'R04') else 'dense',
                })
            methods.append({
                'method': group['method'],
                'queries': query_trace,
                'merged_rank_1_based': position(group['merged_ranking'], ident),
                'final_k5_rank_1_based': position(group['selected'], ident),
            })
        trace.append({'case_id': case_id, 'document_id': ident, 'title': judgment['title'],
                      'existing_grade': 3, 'main_work': judgment['main_work'], 'methods': methods})
    dump('known-strong-reference-stage-trace.json', {
        'scope': 'post-hoc trace only for already judged grade-3 pairs in the union of final results',
        'not_full_recall': True, 'new_model_calls': 0, 'new_grades': 0,
        'inputs': {name: sha(HERE / name) for name in
                   ('results.json', 'graded-results.json', 'dense-rankings.json')},
        'references': trace,
    })
    lines = ['# 已評為 3 的公版：排序階段追蹤', '',
             '這是事後診斷，只追蹤本輪前五聯集內已有的 3 分公版；不是完整相關來源集合，不能計完整 Recall。沒有新搜尋、模型呼叫或評分，沒有依結果調參。名次均從 1 起算。', '',
             '| 員工／公版 | 方法 | 每個查詢的全庫 dense 名次 → 該方法候選池內名次 | 合併名次 | 最終前五名次 |',
             '|---|---|---|---:|---:|']
    for row in trace:
        for method in row['methods']:
            stages = '; '.join(f"{query['query_id']}: {query['full_dense_rank_1_based']} → "
                               f"{query['pool_rank_after_method_order_1_based'] or '未入 N20'}"
                               for query in method['queries'])
            lines.append(f"| {row['case_id']}／{row['title']} | {method['method']} | {stages} | "
                         f"{method['merged_rank_1_based'] or '未入候選'} | "
                         f"{method['final_k5_rank_1_based'] or '未保留'} |")
    lines.extend(['', '機讀原件：[known-strong-reference-stage-trace.json](known-strong-reference-stage-trace.json)。', ''])
    with (HERE / 'stage-trace.md').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(lines))
    print(f'{len(trace)} already judged strong pairs traced; no labels or queries added')


if __name__ == '__main__':
    main()
