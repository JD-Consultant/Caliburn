"""Freeze synthetic contrastive queries before any model inference."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]


def dump(name, obj):
    with (HERE / name).open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    cases = [
        dict(case_id='N01', base='員工：我主要負責會員網站的頁面和互動。拿到設計稿後做版型、表單驗證、手機與電腦的顯示調整，串接同事提供的 API，測試登入和資料顯示是否正確，修正操作問題。', question='顧問：你有負責分析關鍵字和競爭網站、制定搜尋引擎優化策略、追蹤搜尋排名及曝光成效嗎？', explicit_no='員工：沒有，分析關鍵字和競爭網站、制定搜尋引擎優化策略、追蹤搜尋排名及曝光成效都不是我的工作，是行銷同事負責。', primary='INM3514-001v4', probe='IDC3512-001v2', probe_chunk='IDC3512-001v2:task:1:1'),
        dict(case_id='N02', base='員工：我主要處理日常帳務和月結。整理發票、收付款單據及費用憑證，核對金額和會計科目後入帳，追蹤應收應付、銀行對帳，月底做調整分錄和帳表，整理事務所需要的資料。', question='顧問：你有負責尋找供應商、詢價、比價、議價、選定供應商及下單嗎？', explicit_no='員工：沒有，我不負責尋找供應商、詢價、比價、議價、選定供應商或下單，這些由採購同事處理。', primary='FAC4311-001v2', probe='BAS3323-001v4', probe_chunk='BAS3323-001v4:task:1:2'),
        dict(case_id='N03', base='員工：我主要做倉庫的收貨驗收、上架、揀貨和盤點。對照送貨單確認品項與數量，掃條碼登記入庫，再依儲位放貨；按照出貨單揀貨，月底複點自己負責的區域，有差異就登記並回報主管。', question='顧問：你有負責尋找供應商、詢價、比價、議價、選定供應商及下單嗎？', explicit_no='員工：沒有，我不負責尋找供應商、詢價、比價、議價、選定供應商或下單，這些由採購同事處理。', primary='MMP4321-003v4', probe='BAS3323-001v4', probe_chunk='BAS3323-001v4:task:1:2'),
    ]
    queries = []
    for case in cases:
        base, question = case['base'], case['question']
        variants = {
            'base': base,
            'question_only': base + '\n' + question,
            'no_short': base + '\n' + question + '\n員工：沒有，這些我沒有做。',
            'no_explicit': base + '\n' + question + '\n' + case['explicit_no'],
            'yes_short': base + '\n' + question + '\n員工：有，這些我都有做。',
            'uncertain': base + '\n' + question + '\n員工：我不確定這些算不算我的工作，現在還不能確認。',
            'no_repeated3': base + ('\n' + question + '\n員工：沒有，這些我沒有做。') * 3,
            'confirmed_projection': base,
        }
        for variant, text in variants.items():
            queries.append(dict(case_id=case['case_id'], variant=variant,
                                query_id=f"{case['case_id']}-{variant}", text=text,
                                text_sha256=hashlib.sha256(text.encode()).hexdigest()))
    dump('cases.json', cases)
    dump('queries.json', queries)
    sources = [HERE/'protocol.md', HERE/'prepare.py', HERE/'worker.py', HERE/'cases.json', HERE/'queries.json',
               EXP/'2026-10-05-memory-public-unit-retrieval/run-01/corpus.json',
               EXP/'2026-10-05-memory-public-unit-retrieval/run-01/queries.json',
               EXP/'2026-10-05-memory-public-unit-retrieval/run-01/query-vectors.json',
               EXP/'2026-10-04-public-chunk-retrieval/run-01/chunks.json']
    sources.extend(sorted((EXP/'2026-10-04-public-chunk-retrieval/run-01/vector-batches').glob('*.npz')))
    dump('input-manifest.json', {str(p.relative_to(EXP)).replace('\\', '/'):
        dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size) for p in sources})
    print(f'frozen {len(cases)} cases, {len(queries)} variants, {len(set(q["text"] for q in queries))} unique queries')


if __name__ == '__main__':
    main()
