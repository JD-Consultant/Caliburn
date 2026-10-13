# 擴充與修改

先讀 [Codemap 與流程](../README.md#codemap)及 [OCS 欄位契約](../README.md#6-field-contract)。單檔與批次 CLI 共用 `conversion.convert_file`；新能力接在實際負責模組，避免另寫一份轉換流程。

| 修改目的 | 負責位置 | 必要核對 |
|---|---|---|
| PDF 文字、表格或位置抽取 | `parsers/pdf_parser.py`、`parsers/models.py` | 從固定 bytes 抽取一次；回傳不依賴已開啟 PDF 的 `PDFDocument` |
| 特定 section 的欄位解析 | `transformers/sections/` | 保留來源順序、位置及跨頁關係；`ocs_transformer.py` 只組裝各 section |
| 欄位或關係檢核 | `validators/schema.py` | 結構沿生成模型；來源核對沿 parser 的抽取快照 |
| JSON 保存 | `writers/json_writer.py` | 暫存檔在目標同目錄；成功後原子替換，失敗保留原目標 |
| 新流程效果或 CLI 參數 | `conversion.py`、`cli.py` | 單檔與批次的失敗診斷及退出碼一致 |

目前 parser、transformer、writer 由 `convert_file` 直接組裝具體實作。若出現真正需要替換的第二條路徑，再按呼叫端所需方法定義小介面；不要先增加基底類別或註冊框架。

修改解析時，使用有代表性的來源 PDF、既有 golden JSON 及拒絕反例。先確認既有測試能捕捉改動目的，再執行相關測試及完整套件：

```powershell
uv run --project apps/pdf-to-json --locked --extra dev pytest apps/pdf-to-json/tests
```

這條命令由 repository 根目錄執行。通過結構與來源檢核不代表 PDF 沒漏字，涉及抽取品質的改動仍須對照代表原件。JSON 結構由共用 [ocs-contract](../../../packages/ocs-contract/) 管理；變更該契約時一併核對 indexer 消費端。
