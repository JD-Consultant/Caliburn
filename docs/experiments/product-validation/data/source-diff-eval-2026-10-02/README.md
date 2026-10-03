# 來源差異配對試驗資料

完整問題、方法、結果與解讀見 [T14 實驗報告](../../../../history.md#source-071935d378a04bc247df)。這裡保留測量原件與可重算資料，不維護另一份結論。

| 檔案 | 用途 |
|---|---|
| [protocol.md](protocol.md) | 執行前凍結的假說、控制、判準及停止界線；原文不事後修分 |
| [cases.py](cases.py)、[experiment.py](experiment.py) | 六種合成資料、隱藏答案、兩組組裝、真模型執行與逐項計分 |
| [test_experiment.py](test_experiment.py) | 付費前檢查計分、顯示資料與 opaque 去敏；不代表語意答案無歧義 |
| [run-01](run-01/run.jsonl) | 計數階段連線失敗，零次模型生成准入 |
| [run-02-network/manifest.json](run-02-network/manifest.json) | 指引、工具、模型、環境、凍結資料與七個責任檔案雜湊 |
| [run-02-network/cases.json](run-02-network/cases.json) | 實際凍結案例與事前答案；答案未送入模型 |
| [run-02-network/results.jsonl](run-02-network/results.jsonl) | 全部 24 次結果與原分數；各 trial 另有同名 JSONL 軌跡 |
| [run-02-network/metrics.csv](run-02-network/metrics.csv)、[summary.json](run-02-network/summary.json)、[配對表](run-02-network/paired-table.md) | 離線重算的衍生統計，不是原始模型輸出 |
| [analyze.py](analyze.py)、[test_analysis.py](test_analysis.py) | 原件、凍結條件、usage、評分、衍生表與報告表格核查；另驗證數據或答案遭改時會拒絕 |

離線重核命令：

```powershell
python -X utf8 -B docs/plans/2026-09-29-target-rebuild/evidence/data/source-diff-eval-2026-10-02/analyze.py --check-report
```

原件保留模型可見文字與工具交互，不保存憑證、原始內部推理或加密 reasoning 內容；後者只留雜湊與長度。它們供研究核查，不是產品恢復備份。本次 provider 為既有 SDK 預設的 OpenAI 直連，請求與回傳均標示 `gpt-6-luna`；模型別名可能更新，不保證重新執行得到相同文字。

加上 `--check-code` 可另核對現行三個產品檔案是否仍與執行當時相同。本次已核對；日後產品改版不代表實驗原件失效，預設仍可獨立重算保存資料。四個凍結實驗檔案的雜湊則每次檢查。

原件日期是 2026-10-02，結果分析與報告整理於 2026-10-03；較早指引試訪的另一批 24 份資料不在本目錄，不合併計分。新付費比較另開新 run；本目錄的凍結資料、方法與已執行腳本不回寫。
