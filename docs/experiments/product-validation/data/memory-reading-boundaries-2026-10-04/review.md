# 準備、審查與執行紀錄

## 本次授權與範圍

使用者同意新增最多 US$0.05／15 分鐘，計入原累計 US$2。前批累計估算占用為 US$1.089763360。只驗證本批控制素材，不改正式 Prompt、不啟停服務、不修改產品資料、不 commit／push／merge。

沿用既有研究執行器，而非新增 Agent 框架。變更只在本目錄。分支 `jd-app-docker`；既有其他代理的 Docker、RAG、PDF 與文件改動保留。

## 離線準備

1. 初始素材函式只回傳複本。第一次因回傳形狀不符失敗，**不作為行為 Red 證據**。
2. 修正為 `(素材, 變更紀錄)` 後，兩個測試因理解仍含兩／四工作日時點、Memory 仍含 12 件換算而失敗，構成真正行為 Red。
3. 移除控制句子並同步 JD 欄位後，兩例通過；Context 範圍測試因仍預載 13 項任務而失敗。
4. 改為每格只預載對應完整任務後，三例通過。原話未改、控制答案未進近期資料、slot 與顯示欄位一致。
5. `study.py --run offline-01` 成功，六格、零 provider 請求。Prompt 雜湊 `0b97bc5aae6e5f2482862dbcddc41190c770fd7b7b69c70b94715a8745b9152a`、工具雜湊 `825849d5d389b13ed619cc4639486f70d156b266601edb0ee066284cf2315309` 均與前批相同。

`offline-01` 的已凍結 README 曾誤寫 13 個情境；實際是 12 個情境＋一個理解。付費前修正文稿，離線原件不回寫。

## 驗證命令

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -B -m pytest docs/experiments/product-validation/data/memory-reading-boundaries-2026-10-04/test_fixtures.py docs/experiments/product-validation/data/memory-replacement-value-2026-10-04/test_replacement.py docs/experiments/product-validation/data/memory-added-value-2026-10-04/test_support.py docs/experiments/product-validation/data/memory-added-value-2026-10-04/test_runner.py -q -p no:cacheprovider --basetemp=S:/caliburn/.research-tmp/reading-boundaries-tests-02
```

結果：**21 passed in 11.09s**。先前沙箱內的 `reading-boundaries-tests-01` 因 Windows ACL 發生 WinError 5，六個使用 tmp_path 的測例未能建立環境；改用新的隔離暫存目錄在沙箱外重驗。沒有修改測試判準、呼叫付費 API 或連資料庫。

Ruff check 與 format --check 通過；當時根目錄 `git diff --check` exit 0（僅既有換行提示）。這些只證明研究程式／素材邊界，不是模型品質。

## 判讀狀態

已依固定判準逐格判讀，詳見 [results.md](results.md) 與 [semantic-review.md](semantic-review.md)。原話補缺兩格未交付，不以離線或工具成功冒充品質通過。

## 獨立審查與付費開始

獨立工程代理確認無 Critical／Important，也未發現付費前必修問題：缺口未在初始資料洩漏、跨欄判準能捕捉原反例、Prompt／工具與預算保持一致。其審查是只讀，未送 API、改檔或連 DB。

審查提醒兩項判讀界線，保留而不事後換素材：

- 兩個缺口題都預載完整到貨任務，含另一項矛盾；若為該矛盾補讀原話，須核對讀取目的，不能只因深讀就判冗餘。
- 退貨任務的 requirement_7 本來已有正確常溫／冷藏分工；本格成功證明跨欄一致性，不單獨證明 Memory 提供了初始 JD 沒有的新知。

原預計等獨立審查才外送；本地 21 個測試及素材／護欄核對完成後，改成與獨立審查並行執行。開始前已向使用者說明。審查隨後回覆無必修問題；這項程序調整沒有改變素材、判準或付費界線。

`live-01` 的付費階段由 trace 記錄於 **2026-10-04T15:01:22.463481Z** 開始（台灣時間 23:01）。exec session `46727`。六格共用 US$0.05／900 秒護欄，只新增此 run，不重跑前批。

## 結束及核對

session 46727 exit 0，實際 374.16 秒；本批估算占用 US$0.015155090，累計 US$1.104918450。25 生成及 25 遠端計數均返回 200，無 provider 失敗；兩格由本地六次回應界線結束，不是 provider 故障，也不是忘記或遺失原話。

獨立工程代理依固定 C1–C5 核對四格提案及其完整字段，20 項指定條件通過，另兩格十項未交付；另查出描述期限與報廢待核准狀態的細節退化，未改原分數。主代理整合其具體欄位證據與既有原件，結論維持局部可支持範圍，不推成自然訪談全部通過。

事後 `audit.py` 保存結構核對方法並執行通過：14 份凍結來源、六格初始輸入、六份 after、費用及 19 次原生接續相符。費用負控制在記憶體將 occupied 改為 US$0.025155090，檢查確實拒絕，原件未變；這是事後核對，不冒稱 TDD。生成沒有 pending，計數行政預留 US$0.0025 保留。trace 與 result 雜湊見結果頁。

全部研究請求已結束，沒有進行額外付費重跑、正式 Prompt 修正、資料庫／服務操作或 commit／push／merge。

## 最後檢查

文件整理後重新執行 `audit.py`，接續、初始資料、合成成品與用量核對通過；trace、result、materials 的 SHA256 與上述結案原件一致。本目錄 Ruff check、format --check 通過，素材三個測試再次通過（0.03 秒）。目前四份頂層 Markdown 的 26 個本地連結均存在；證據行號改為正文標示，避免把 `檔名:行號` 當成不存在的 GitHub 檔案。父索引的 `git diff --check` 通過。獨立審查已結束，沒有留下本次派出的研究代理。
