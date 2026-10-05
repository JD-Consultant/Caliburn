# 公版兩層參考結構核對協定

2026-10-04。使用者要求先處理向量資料庫與設計；暫不依賴分析方法無線索探索未知，後續補測收尾與開場至 PDF 旅程。候選責任見[設計](../../specs/2026-10-04-public-reference-retrieval-design.md)。

本輪只做確定性的結構核對，不呼叫模型、embedding、Qdrant 或付費 API，不產生或更改向量排名。沿用 805 份凍結公版及最近 22 個已觀察合成情境的 original_messages／quota_rerank／N20／K5 結果。原始 JSON 逐檔核 source_sha256 後在本包保存一次，查閱導覽以固定 hash 與 JSON Pointer 連到來源。

來源：`../2026-10-04-occupation-retrieval/corpus.json`，`../2026-10-04-retrieval-input-boundaries/cases-observed.json`、`inputs.json`、`metrics.jsonl`。沿凍結來源原始任務 group，不依 T code 數複製共用區塊。空／缺代碼但有正文的 group 仍可用來源位置定位。所有查詢都有條目，零命中也保留；同一公版只有一個職位導覽條目，保存全部查詢邊。

職位導覽可取得來源 JSON 的全部已解析任務 group，不被員工當次向量結果過濾。工作導覽明寫 `match_level=document`／`task_alignment=not_evaluated`，不得將其他任務自動標為已匹配、適用、已詢問或缺口。原型不增加 completion、employee_occupation 或 applicability 判斷。

通過條件：805 個來源 hash 一致，完整 group 指標及共用區塊一一對照；22 結果完整還原查詢與每條命中邊；每員工公版集合、數量與正文字符對照原 metrics；每個回傳公版的全部目錄可沿共享來源讀回；錯換 hash／pointer 可被獨立核對拒絕。核對由獨立程式重算，不信任 summary 的 passed 欄位。

準備 manifest 在結果生成之前保存來源／腳本／設計 hash。原輸入、失敗、資料轉換與驗證輸出均保留；此前封存檔案不修改。README 只報結構層級，不宣稱 Memory 搜尋、相關片段、未知發現、LLM 省費或 JD 完整度通過。來源 JSON 任務完整性不等於 PDF 逐字完整性或官方最新身分。
