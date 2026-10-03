# 執行、品質與來源探測原件

2026-10-02 從本機 `.research-tmp/eval/` 整理的既有**合成**實驗輸出；不是本日重跑，也不是新驗收結論。正式判讀沿 [T14](../../../../history.md#source-d3293e9b28c75bbb6616)、[T16](../../../../history.md#source-6d2d7ab4abfedbf8416e)、[T17](../../../../history.md#source-98d840caa9eed7fb2840)。本次保留失敗、網路錯誤、修正前後與比較組，不只挑成功結果。

| 目錄 | 材料與用途 |
|---|---|
| `continuation/` | 輪前準備、原生接續、壓縮、token／限流探測；檔名中的 offline／provider／network 是不同實驗，不可混稱全部真模型通過 |
| `sources/` | 來源保留、次序、範圍、Memory 來源變更與 JD 重核；部分為受控 fixture，不冒充自然訪談 |
| `journeys/` | 核心旅程、補充／更正、收尾與長旅程預演；Sol 只屬歷史比較，產品仍採 Luna |
| `quality/` | 早期基線、情境精確度、Memory 品質、工具說明與 reasoning effort 對照 |
| [SHA256SUMS.txt](SHA256SUMS.txt) | 本包 56 個原件的 SHA-256；搬移前後位元組一致，JSON／JSONL／PDF 不改寫換行 |
| [relocations.csv](relocations.csv) | 84 個原位置到保存位置的對照、大小與雜湊。28 個已存在且逐位元相同的原件沿用[既有資料包](../instruction-experiments-2026-10-01/README.md)，不再保存第二份 |

保留原檔名與實際內容；有些 `.json` 是陣列，有些是物件，`.jsonl` 按行解析。context 審閱輸出屬已挑選的觀察，不是可用來恢復執行的完整 checkpoint。未補造缺少的模型版本、時間或實驗設定；精確執行條件回查相應證據與程式提交。

本次只搬移已完成的 JSON／JSONL、PDF 與既有 PNG；腳本、仍被程序占用的日誌、資料庫與私有設定留在本機。舊證據中的 `.research-tmp/eval/...` 代表當時輸出位置，現在請依 `relocations.csv` 查原件。沒有外送資料或重新呼叫模型。憑證與 opaque reasoning 模式掃描未命中；這不是對 repo 其他未盤點資料的安全認證。

本地 Git 保存不等於遠端備份；報告引用時須同時交代原實驗結果與限制。
