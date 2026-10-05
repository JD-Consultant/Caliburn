# 外送前檢查與執行紀錄

## 方法與範圍

使用者同意本次新舊 prompt 真模型對照最多 US$0.10／20 分鐘，計入原累計 US$2。沿前次固定合成材料，不重跑長訪談、不重製 Memory、不修改工具或原 21 項判準。正式產品只使用前輪已確認的顧問指引修改，本次研究沒有再改 production。

新資料包的 `policy_study.py` 凍結兩組指引與同一份材料，重用既有研究迴圈。為了同一批共用預算並交錯兩組，迴圈只補兩項：按格選指引，以及明確的格身分；沒有另一套 API 或重試機制。前次 live 原件、執行碼與 trace 保持不變。

## 離線反例與驗證

初次沙箱內測試被 Windows 暫存目錄 ACL 阻擋，沒有執行到行為反例；不算 Red。改用新的 basetemp 及已核准的本機離線執行，觀察到 **2 failed、4 passed，11.09 秒**：同題同組的兩格共用預設身分，使第二格碰到未結算計數鍵；每格指引 selector 也未被執行，未送出預期文字。

最小修正後，連近期投影、讀取與費用／時間護欄的研究測試共 **18 passed，11.00 秒**。新增測試只替換外部 provider，檢查真正的 request、獨立起始資料及保存結果；不以假模型提案判斷 prompt 的自然遵循。Ruff 與格式整理完成。

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -B -m pytest docs/experiments/product-validation/data/memory-replacement-value-2026-10-04/test_replacement.py docs/experiments/product-validation/data/memory-added-value-2026-10-04/test_support.py docs/experiments/product-validation/data/memory-added-value-2026-10-04/test_runner.py -q -p no:cacheprovider --basetemp=S:/caliburn/.research-tmp/reading-policy-green-01
apps/api/.venv/Scripts/python.exe -X utf8 -B docs/experiments/product-validation/data/memory-reading-policy-2026-10-04/policy_study.py --run offline-01
```

離線準備有八個不重複格身分、兩題 21 項核心判準；零外送、工具與前次指紋相同、兩組使用同一份起始輸入、共同研究補充不變。原指引指紋仍為 `1cbfcc49f1e1de70d1d1e1972e21a1b7543efc06dc83ae19571d8fa017ec0c16`，新指引為 `0b97bc5aae6e5f2482862dbcddc41190c770fd7b7b69c70b94715a8745b9152a`。費用起點沿前次結案原件 `1.056535185`，不把占用歸零。

真模型的完成、用量、來源支持及語意判讀另存；本頁的離線通過不作為效果改善結論。

## 獨立複核與啟動

獨立唯讀審查確認：唯一模型處置是顧問指引；原指引與共同研究補充、材料、題目、工具、Luna／high、每格六步接續及全批共用護欄相符；八格 ID 不重複，前次原件不覆寫。未發現 Critical／Important 問題。審查回覆到達時第一格已在執行，未據此調整已啟動的指引或方法。

`offline-01`、`offline-02` 代表各自準備時版本，不冒稱均為最終執行碼。`live-01` 在真正外送前重新保存當前來源、方法與指紋；費用與時間自 trace 的 `paid_phase_started` 起計。啟動命令如下，不再另啟一份執行：

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -B docs/experiments/product-validation/data/memory-reading-policy-2026-10-04/policy_study.py --run live-01 --live
```

本對話 exec session 為 `94950`；若無法讀取，改查原件，不因沒有結果檔就重送。

## 結案與原件核對

執行約 502.11 秒結案，八格均有結果：新指引四格交付，舊指引三格交付、一格達六次模型回應界線。25 次生成與 25 次遠端計數均返回；新占用 US$0.033228175，累計 US$1.089763360，未超出本次或原累計授權。沒有追加請求、重試未交付格或修改正式資料。

結案後逐項核對 11 份保存來源、兩組指引、工具及八格 initial 的指紋。實際外送中各題兩組起始輸入相同，每格均只有兩則 user 訊息；模型、high、共同工具及各格指引與凍結內容一致。17 次同格接續保有前次工具 call／result；公開 reasoning 加密雜湊與 assistant phase 與後續輸入一致。前次替代價值比較 trace 雜湊未變。

逐格用量及 `after` 由既有分析函式產生，未回寫 trace、manifest 或提案。另一位工程代理唯讀核對八格的核心內容、完整修改欄位直接來源及冷藏跨欄反例，與主判讀一致；九項未交付不算通過，亦沒有把輔助問題加進凍結分數。結果見[局部比較](results.md)及[語意判讀](semantic-review.md)。

用新的 `.research-tmp/reading-policy-final-01` 重跑相同離線回歸，**18 passed，11.49 秒**；未連模型或資料庫。三份研究程式的 Ruff 與格式檢查通過。六份結果／方法／入口文件共 35 個本機連結目標存在，未逐一驗既有錨點；八格用量及套用後欄位重新計算一致。文件更新後 trace 與結果雜湊未變，顧問指引仍是外送前凍結的同一份。沒有 commit／push／merge。
