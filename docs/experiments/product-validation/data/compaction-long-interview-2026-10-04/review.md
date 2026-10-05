# 資料準備與判準審查

本輪為生成前的資料審查，非顧問、B1／B2 或 JD 的品質評測。主代理核對資料與程式；另由一個只讀工程代理獨立核對 61 個來源事件及 14 案的 51 個事實列項。不是真人專家盲評，不代替後續實際輸出判讀。

## 發現與處理

| 發現 | 核對與修正 | 影響 |
|---|---|---|
| 評分來源清單漏 e038、e040 | e038 支持以品號／批號辨識，e040 支持現場安全與不推定搬重物；補入對應案例來源 | 避免正確引用被誤扣；未增補員工事實 |
| 調撥判準把保留批號升成結案門檻 | e019 明定雙方收發紀錄相符，e020 是完成後保留批號；分開表述 | 收回未被原話支持的加強要求，不為判準改員工資料 |
| e057 不一定在每組都模糊 | 顧問的實際前問不同；若已唯一指向一張表，不能強制以「沒追問」扣分 | 施測前先判資格；不同資格不作相同條件配對 |
| e061 沒有逐項詢問後 19 個細節 | 分開 32 個明確回提／更正觀察與 19 個正式主張查核；未採用細節不算回憶失敗 | 51 是列項數，不作同等取用測試分母；漏掉工作以12領域涵蓋另評 |
| 評分時點說明誤寫 `before_event_id` | 實際欄位及語意都是 `observe_after_event_id`，已修正 | 只修說明，不更動時間線 |

主代理逐一回到對應員工原文核對後採用上述修正。這些是測量設計與資料修訂，不是 production bug，也不需要偽裝成程式 TDD。研究審查沒有否定資料可成稿的職務範圍；未達壓縮門檻仍只代表尚未測得壓縮壓力。

## 腳本驗證

九個資料投影／權限／容量反例先在具名未實作函式上失敗，再完成實作並通過。另四個計數案例先失敗，再驗證：失敗立即停止、不猜零、超過五次先拒絕、有效計數保留輸出預留、無效 boolean 計數不能當成功。

人工程式審查同時檢查：重用產品的 SDK 和容量，不重寫工具 schema；同步檔案／Git I/O 留在同步 CLI，網路計數使用受限 async；不對 provider 錯誤印原文或任意 headers；已有輸出目錄拒絕覆寫；沒有 create／compact 執行分支。格式與來源投影均再核對。

型別檢查起初以已安裝套件解析 `caliburn`，沒有找到本機型別來源；指定 `MYPYPATH=apps/api/src` 後，定位到研究 JSON 回傳的 `Any` 和初始失敗列的過窄推導。補足 JSON 邊界型別及員工原文的字串檢查，沒有使用 ignore 或改產品套件；strict mypy 通過。修改未改變已計數的請求內容。

可重現的程式檢查命令（PowerShell，儲存庫根目錄）：

```powershell
uv run --project apps/api --locked python -X utf8 -B -m pytest docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/test_preparation.py -q -p no:cacheprovider
uv run --project apps/api --locked ruff check --config apps/api/pyproject.toml docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/preparation.py docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/test_preparation.py
$env:MYPYPATH = 'S:\caliburn\apps\api\src'
uv run --project apps/api --locked mypy --strict --follow-imports=silent docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/preparation.py
```

計數預檢的連線失敗保留於 `preflight-01`；允許直連後的五個計數保留於 `preflight-02`。不是無限重試，也未用新模型輸出迎合判準。

## 尚未審查的結果

資料預檢時尚無正式來源序號對照、顧問真實對話、JD 成品、Memory／摘要產物或壓縮採用紀錄，當時未審查它們的品質，也未將準備通過寫成主比較完成。後續端到端先導的審查記錄如下；四組比較及壓縮仍未完成。

## 端到端先導審查

這一輪使用 [先導計畫](pilot-plan.md)及 [pilot.py](pilot.py)，未修改正式產品。一個只讀工程代理核對研究腳本、權限、計數、預算、原生接續與保存接線，指出兩個具體問題：DSN 覆寫可能繞過指定研究資料庫，以及研究護欄把 128K 誤當所有生成的拒絕門檻。主代理以反例重現並修正，沒有另加產品金額攔截、容量政策或 Agent loop。

護欄原有四項測例及上述五項測例均先出現預期失敗，再通過。離線分析另以五項反例核對：計數不可混入生成 usage、未回覆的生成要保留、未知 usage 不能填零、Windows 原件路徑可辨識、原生前綴的 phase 與工具 call_id 不可錯配。後兩項包含各自有效與錯誤輸入；測試的統計及判斷不含真模型品質自動評分。

真 API 啟動於兩個研究修正前，因此 [manifest](pilot-01/manifest.json)的啟動雜湊對應當時原件，不對應目前的修正稿。完成後以精確雜湊核對並保存 [executed-script](pilot-01/executed-script.json)，明示事後還原；原始 trace 及產物不追改。實際 DSN 沒有覆寫、最高輸入未達 128K，兩個有問題的分支都未被觸及。修正的邊界驗證是離線證據，不能冒稱已用真 API 重驗高容量接線。

主代理再按 trace 核對完整前綴與工具配對、五輪起始角色及原文、Memory 上界與 B2 新增差異，並以現行產品來源 Workflow 回查所有 JD 引用，最後只讀查詢 PostgreSQL 的提交狀態。獨立代理沒有執行付費測試或真人分析評分；兩者分開記錄。[先導結果](pilot-results.md)給出數值及未施測範圍。

最終驗證使用本專案的 Ruff 設定及 `MYPYPATH=apps/api/src`，而非工具預設的 88 字元／套件解析規則。既有 33 項 response step／loop 測例與本研究 27 項離線測例合計 60 項；沒有為文件更新重跑全產品測試或付費模型。

```powershell
uv run --project apps/api --locked python -X utf8 -B -m pytest apps/api/tests/unit/test_response_steps.py apps/api/tests/unit/test_response_loop.py docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/test_preparation.py docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/test_pilot.py docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/test_pilot_analysis.py -q -p no:cacheprovider
uv run --project apps/api --locked ruff check --config apps/api/pyproject.toml docs/experiments/product-validation/data/compaction-long-interview-2026-10-04
uv run --project apps/api --locked ruff format --check --config apps/api/pyproject.toml docs/experiments/product-validation/data/compaction-long-interview-2026-10-04
$env:MYPYPATH = 'S:\caliburn\apps\api\src'
uv run --project apps/api --locked mypy --strict --follow-imports=silent docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/preparation.py docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/pilot.py docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/analyze_pilot.py
```

真模型不作為上述命令的一部分。重新施測需明確隔離 DSN、新輸出目錄及 `--live`；不能覆寫 `pilot-01`。只核查資料時讀原件，或匯入 `summarize_trace`／`inspect_context` 計算，不需金鑰或資料庫。已存在的 `analysis.json`、`context-audit.json` 拒絕覆寫。
# 主實驗接線審查

## 外送後的研究接線與計數修正

`main-01` 完成八段訪談，第九段外送前等待時主動停止；29 個生成全部取得回應、38 個計數、無 compact。生成 usage 估算 US$0.015787140，計數行政預留另計，非帳單。原件及隔離 schema 全部保留：[停止紀錄](main-01/external-stop.json)、[停止時分析](main-01/stopped-analysis.json)。這次未形成四組比較，也不是 provider／正式產品失敗。

實際 trace 顯示生成回應提供 token limit／remaining 200,000，但後續計數回應沒有這些標頭。研究 hook 原先一律取代速率快照，清空資訊後，大於 40K 的估計請求會反覆走 60 秒保守等待。依 [OpenAI 速率限制文件](https://developers.openai.com/api/docs/guides/rate-limits) 使用實際回應資訊；缺少標頭不視為新的空配額。測例重現資料被清除的 `KeyError`，再改為 count 只有提供 token 資訊才替換該快照；生成／compact 仍更新。沒有改速率限額、取消計數或新增重試。先停止舊程式再修改，接下來另開完整比較，不拼接前後版本。

離線分析器的獨立審查另發現：工具結果可能先送入 compact，再被 canonical window 摘除；只從生成 input 計算查閱會漏算，造成壓縮組貌似更省閱讀。新增反例先得到 0≠1 的失敗，再納入 compact request 並以原 call_id 去重。生成 response 才登記新呼叫，歷史重送不再重複計數。這是分析器修正，未改主實驗的模型結果或來源。

上述五個相關測例通過，Ruff／strict mypy 通過。新比較 run 估算用量界線降為 US$1.90，US$0.10 留給停止的 run，原 US$2 界線不擴張。

再次唯讀復核確認上述修正，並指出 trace 應記錄本次回應的實際 headers，不能把內部保留的節流快照冒充為計數回應新給的 headers。於同一測例加上 `{}` 斷言先得到失敗，再分開記錄本次 `headers` 與內部快照。這讓等待來源可重建，不改節流決策。復核的外送就緒結論以此修正為前提；真模型品質仍待施測。

主比較沿用已核准的四組與固定員工原文，沒有修改正式產品。九個來源投影與外送護欄反例先失敗，再完成最小實作。真 PostgreSQL 前置檢查另外確認四組初始 Context 先保存、移除研究 patch 後仍可恢復同一請求；20 項檢查通過，未呼叫模型。

獨立唯讀審查發現：研究 HTTP 回應 hook 使用 `CompactedResponse.model_validate`，會拒絕 compact 合法保留的 `user`／`input_text`。鎖定 SDK 3.20.0 的 `BaseModel.construct` 採遞迴、非嚴格解析；正式 SDK 也是這條接法。新增實際 hook 測例重現 `ValidationError`，再改用同一 SDK 的 `construct` 估算 usage，不改回應、不刪 compact output。測例轉綠，研究護欄與 hook 共十項通過。這是研究腳本修正，不是正式 Runtime 的壓縮缺陷。

研究腳本另經 Ruff 與 strict mypy 檢查。較早的型別檢查攔下 flat summary 資料組裝錯誤：`read_interviews` 回傳的是 `InterviewHistoryEntry`，原文欄位在 `.message` 內；已按正式型別修正，尚未外送主生成。

修正後，獨立審查只讀復核同一 P1，判定可在已定護欄內開始外送；不代表真模型品質或壓縮成效通過。最新驗證：本目錄與原有 response loop／step 共 70 項測試通過，Ruff 通過，三份主執行／投影／PG 前置腳本 strict mypy 通過。
