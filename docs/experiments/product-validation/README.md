# 產品驗證與實驗資料

這裡保留專題報告使用的合成訪談、模型輸出、工具互動、指標、雜湊與分析程式。已結案的施工清單和交接日誌不放在這裡；實驗原件不因後續修改產品而改寫。

## 按問題找資料

| 問題 | 保存資料 |
|---|---|
| 指引如何影響追問、JD 粒度與引用？長訪談如何延續？ | [24 份指引比較與 45 輪旅程](data/instruction-experiments-2026-10-01/README.md) |
| 舊指引、模型與推理設定的比較結果是什麼？ | [早期實驗索引](data/earlier-experiments-2026-10-01/INDEX.md) |
| 原生接續、Context、來源工具及換版核對如何驗證？ | [執行探測](data/runtime-probes-2026-10-01/README.md) |
| 用差異代替重複全文，對輸入量與完成率有何影響？ | [24 次來源差異子任務](data/source-diff-eval-2026-10-02/README.md) |
| B1／B2 壓縮是否生效？哪些部分尚未驗到？ | [背景壓縮觀察](data/b-role-compaction-2026-10-02/README.md) |
| 顧問在引導示範中讀了什麼、引用了什麼？ | [倉庫訪談原件](data/inventory-demo-guided-20261003/) |
| 來源核對指引與定位錯誤如何重現？ | [引用核對實驗原件](data/reference-alignment-prompt-20261003/) |

方法、結果與判讀見[專題報告第四、五章及附錄 B](../../reports/project-report/report.md)；跨情境的已驗範圍見[驗證說明](../../architecture/verification.md)，問題整理見[實驗發現](../../reports/experiment-findings.md)。不同批次不能合併成同一次受控實驗，也不將合成訪談當成真人使用成效。

## 離線核對

在儲存庫根目錄執行，不呼叫模型、不連資料庫、不產生費用：

```powershell
uv run --project apps/api --locked python -X utf8 -B docs/reports/project-report/verify_evidence.py
uv run --project apps/api --locked python -X utf8 -B docs/experiments/product-validation/data/source-diff-eval-2026-10-02/analyze.py --check-report
```

第一個命令核對報告表格、訪談原件及來源核對數據；第二個命令重算來源差異實驗。它們驗證保存資料與計算，不代表重新完成真模型評測。

原始 manifest 中的舊路徑保留為執行當時紀錄。資料曾存於重建計畫目錄，現獨立保存；分析程式只調整取檔位置，不修改原始輸出、雜湊或判準。資料包中的工具副本保留當時環境設定，重跑付費實驗前須另行確認設定與授權。
