# JD／顧問採用：整體方向與 H4 接續審查

2026-09-14；JD-R002／OI-01、OI-02。程式基準 `f160be97`（`jd-b1-pair-readback-20260914`），另含本輪未提交的 HF-07 source owner 窄修。這次是整體設計／原碼與固定測試審查，並修訂交接文件；沒有實作背景服務、建表、呼叫 provider 或切換正式入口。

## 1. 結論與適用範圍

**方向成立；來源／B1 adapter 的既有修正可以保留。現在需要收斂的是完整採用的施工接縫與文件，不是重做顧問、重新選框架或擴建來源引擎。**B1 固定接合完成不等於 H4 完成；CT49／CT50 的既有自然顧問成果也不能因新 App 未接好而被說成未實作。

本次回看 9/12 的關聯式需求、schema、業務與工具責任，9/13 的欄位充分性、完整旅程、框架選型、C 核心／App 接合、B1／B2 採用映射、窗口契約與接續計畫；再核 `extraction.py`、`extraction_app.py`、`conversation_sources.py`、宿主資源及 `4f94fbfb` 的 `scheduling.py`／`sources.py`／`consolidation.py`。這不是全產品每個功能的重新驗收。

產品仍是：員工訪談為主，也能不開 AI 完整管理六章 JD；職責／任務／成果／要求／共享 K/S 是關聯式項目。唯一工作稿、同頁聊天、當輪實際改動、人與 AI 共用業務保存、JD-only 撤回沿既定設計。沒有新增必填分析欄、排版編輯器、審核按鈕、另一個 LLM 工作區或歷史聊天選輪入口。Excel 延後。

## 2. 發現與處理

| ID／層級 | 實際證據與影響 | 本次處理／退出條件 |
|---|---|---|
| HF-01／交接錯誤 | 接續計畫頁首說 B1 adapter 完成，§1／§3／§8 卻仍要求先做 source port 或採用映射；§7 還要求補已完成 CA-01／02 紅測。package README 說「不含模型執行」、C 尚未接入，與程式不符 | 修正目前路由與 README；歷史 H1–H3 保留並明標不是新任務。H4 只依[執行計畫](../../../plans/2026-09-14-jd-h4-runtime-integration.md)接續 |
| HF-02／下一片必要接縫，尚非執行中 bug | 新 `plan_batch()` 接 first/last IDs、回窗口前綴與布林；B1 `start()` 接單一固定 source ref，超過 `max_windows` 即拒絕。舊 `extraction_batch()` 則回涵蓋前 N 個窗口的整批 ref。現有 API 未閉合這條交接；而目前 `unprocessed_source()` 只回 bounds dict，尚沒有契約所需的 `through_reference` 固定 target 入口。不能把整個 target 交 B1，或只取最後一個 window 丟掉前面的 | 由同一 source owner 先以 `unprocessed_source(after, through)` 取得連續範圍，再發一個簽章 `purpose="window"` target；再由 owner 以 target＋publication cursor 產生有界 batch ref。語意詳[映射 §3.6](../../2026-09-13-jd-consultant-b1-b2-adoption-mapping.md#36-固定目標到有界批次2026-09-14-接續設計)。以超過一批、追加原話及重開驗收，不重寫 B1 |
| HF-03／背景設計尚未落地 | `ManualHost.close()` 只等待現有登記工作；尚無 B 背景准入／排空。B1 的 `files` 是最近批次狀態，舊 B2 `start()` 從該狀態取材。若 B1-only 持續開始新批，可能覆蓋未整併交接；B1 完成也不能推進 publication cursor | 先以舊 `BackgroundRow` 的六欄責任作候選基線，R3 先驗證現有 Saver／catalog 是否真的不能承載；只有缺口成立才走 migration／ADR。無論落點為何，都要由同一 owner 管理狀態轉移及恢復規則，且 B1→B2→發布完成後才准入下一批。隔離測試可先做一批 B1 的真 PG 恢復，不把它啟用成日常自動整理 |
| HF-04／過度設計風險 | 前次將 v1 context 一次性轉換寫成啟用前必做。已定 fresh data、不搬舊資料，且 B1 runtime 尚未啟用；沒有查得需要轉換的實際產品資料 | v1 繼續明示拒絕。新 fixture 使用 v2，舊合成 artifact 保留且標不支援重抽即可；不安排 migration、全库掃描或轉換工具。本次未檢視真 DB，不能宣稱其中完全無 v1。若日常啟用時真的遇到需保留的舊工作，先報具體影響再決定，不猜 pair、不換最新來源 |
| HF-05／證據表述 | P3 使用 `InMemoryStore`，不是「落盤／PG」；移除檢查轉紅是實作者報告，本次及前次記載的獨立正常重跑不等於獨立變異重跑。「不代表完整旅程有進展」又過度否定了有效局部交付 | 改為「局部進展、不代表整體完成」；明列證據作者與測試層級。沒有由文件用詞創造新的產品 bug |
| HF-06／已確認的採用紀錄缺漏 | `3921a99d` 修改 `memory.py` 的 pair 保存／讀回驗證，`adoption.json` 仍記舊 hash `5aca9aa0…` 及舊調整內容；其後沒有更新該檔。這會誤導封裝核對，並非 prompt 被改或模型結果錯誤 | 本輪僅更新 manifest 的該檔 hash 為 `251c5e8f…` 並補精確接合說明；九個已採用檔逐一按原始 bytes 核對。未重建 wheel，R1封裝不得拿H3舊wheel當含B1的新產物 |
| HF-07／source owner 的實質缺陷 | `_cursor_boundary` 原先只比較 cursor 與目前訊息的 ID。用現有 fixture 在後續 checkpoint 以同一 ID 替換內容後，沿襲合法 lineage 的 cursor 仍被當成精確前綴，`unprocessed_source()` 會回空而跳過已變更原話；契約 §7.2 要求的是完整訊息序列，不是 ID 集合 | 先建立反例，再在同一 source owner 比較完整 immutable message 值後才做 ID／邊界計算；不新增 digest、cursor、表或第二套 lineage。新增案例後 source 43 passed、整合組 **212 passed**。這是已修的 P1 可靠性缺口，與 B1 runtime 尚未接通分開記錄 |

HF-02／03 是下一片要閉合的工程接縫，**不倒退已通過的 P1／P2／F-04／P3／HF-07**。目前未找到需要推翻關聯式 JD、重做 B1 prompt 或新增通用定位／回退引擎的證據。

## 3. 哪些必要，哪些不應增加

| 機制 | 整體判斷與限度 |
|---|---|
| LangGraph Saver＋Store＋publication | 各管執行進度、詳記／候選與目前理解／發布結果；責任不同。共用 PostgreSQL 不等於三者自動成為一個交易 |
| source 的固定位置／purpose／pair | 針對已重現的換分支、越過回合、交叉配對保留有限驗證；簽章交 ItsDangerous，走鏈交既有 history。App 產生與驗證，模型不手填 token 組成。不是大廠規定相同欄位，也不是任意 DB 竄改的完整防護系統 |
| OpenAI／Anthropic adapter | 框架共用流程及訊息介面；provider 的拒絕、終局、結構化輸出仍要按其契約處理。B1 用已驗 OpenAI 路線合理，無需寫兩套抽取流程，也不新增雙 provider 切換產品 |
| 准入小表 | 可記錄尚未發佈目標／批次、阻擋原因與恢復次數，但目前仍是候選責任；先驗證 Saver／catalog 是否無法承載，不能把它當既定必要表。若缺口成立，才由隔離 migration／ADR 引入；不保存第二份原話、Memory 或已整併游標，也不在 constructor 自動 setup |
| 部分 Store 寫入的未引用產物 | 9/06[抽取驗收 §限制](../../2026-09-06-analysis-only-agent-extraction-results.md)已實測允許一份未引用 artifact；它不被 A 當目前 Memory。新 PG 驗收應確認這條界線，不能要求「任何中斷零多餘檔」而重造跨 Saver／Store 交易或 GC 引擎 |
| 恢復與重試 | SDK 傳輸 retry、B1 格式更正、B 工作續作與發布查回是不同層。沿已驗預算；不套三層 RetryPolicy、不每次 tick 重置額度。C 的未知結果只讀對帳不能套成 B1 永不續作 |
| 背景容量與鎖 | 一個本機 B worker 可是有意的容量選擇，不等於全 App 大鎖。不能持鎖等網路而阻擋別份 JD／前景；同文件 B1/B2/重抽不得同時執行。未有吞吐證據，不新增 distributed worker／striping framework |

## 4. 本次官方證據核對

查閱日均為 **2026-09-14**。下表限於本次會影響選擇的主張；套件實際安裝組合沿 App lock，不因網頁更新而升級。

| 官方來源 | 狀態／版本／授權界線 | 支持與不支持 |
|---|---|---|
| [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling) | 現行 API 指引；服務文件非本地可採用套件授權。經 OpenAI Docs 搜尋後讀原頁 | App 執行、驗參數、回工具結果；可由程式得知的值不勞模型提供。不規定 JD 資料表、window token 或 pair 欄位 |
| [LangGraph Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)／[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | 現行文件；本地 LangGraph 1.2.11、checkpoint-postgres 3.1.2，MIT。舊 durable-execution URL 本次導向 Persistence，已跟到實際章節 | 固定 thread／checkpoint、原生續作與 `sync`。replay 會再執行其後節點；不是外部副作用 exactly-once 保證。不採用頁面 beta DeltaChannel，也不照一般清理建議刪本案來源依賴的 checkpoints |
| [AWS Making retries safe](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | 現行 Builders' Library 原則文，較早原則仍有效；不是要安裝 AWS 服務 | 相同 caller intent／request id 及效果記錄的原子性；成功結果遺失後返回等價結果。支持既有 publication／JD operation，不要求在 B1 再建一套 receipt |
| [Anthropic 現行 harness 設計](https://www.anthropic.com/engineering/managed-agents)／[Managed Agents 文件](https://platform.claude.com/docs/en/managed-agents/overview) | 2026-04-08 官方工程文；Managed Agents 為 beta、服務端保存 session，商用服務，非免費本機 OSS 元件 | 檢討模型進步後不必要的 harness，穩定職責介面；本案不因此改用託管服務。舊 Building Effective Agents 頁面已提示工具景觀變動，本次有跟讀新頁，未用舊框架名單證明今日選型 |
| [ItsDangerous Concepts](https://itsdangerous.palletsprojects.com/en/stable/concepts/) | 2.2.x／本地 2.2.0，BSD-3-Clause | serializer／salt 的不同用途簽章。固定 root、source_first/source_last 是本案資料語意，不是 ItsDangerous 幫忙證明來源 lineage |
| [Python concurrent.futures](https://docs.python.org/3.12/library/concurrent.futures.html) | Python 3.12 穩定 API，PSF；頁面 patch 3.12.14，本地 3.12.13 | Future 完成與 cancel、shutdown 的界線。cancel 不會停止正在執行的工作；不把 timeout 當死亡。文件也提醒執行緒池不適合無期限常駐任務，不能把無限 worker loop 包成一個 Future |
| [PostgreSQL Constraints](https://www.postgresql.org/docs/18/ddl-constraints.html) | PG18，PostgreSQL License；本次未建表／升 DB | PK/FK/CHECK 適合一文件一准入列與有效狀態限制；不決定本案表名、欄位數或產品流程 |

共同原則是責任明確、App 檢查實際結果、原生可恢復執行、相同意圖避免重複副作用及有證據才加複雜度。**不存在公開證據證明各大廠使用本案同一套 A/B1/B2/C 架構、13 表或 token 格式。**本案選擇要用已驗方法、產品需求及反例說明，不能要求每個業務欄位都有同名大廠實作。

## 5. 獨立驗證與本輪限制

在 App 既有環境、`uv --offline --frozen --no-sync`、可寫暫存目錄執行：

```powershell
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -c pyproject.toml -q -p no:cacheprovider tests/test_extraction_app.py tests/test_interview_window_source.py ../../packages/consultant-memory/tests --basetemp=S:/caliburn/.research-tmp/holistic-review-20260914-pytest --tb=short
```

**212 passed／10.93s**。含 B1 接線、窗口來源、Memory 套件及 HF-07 反例；未安裝套件，未換 lock。這證明可在既有 App 環境獨立跑 package，不再把先前單獨解析依賴失敗當永久未驗。沒有重跑全 App 2804 案例、真 PG、Windows 新程序、自然模型或 P3 變異測試；不與前次 109／40／81 的重疊案例相加。P3 變異紅測歸實作者結果，HF-07 的正常反例與修正後案例由本次窄跑實測。

來源核對先排除計算範圍誤判：manifest 的檔案 hash 依原始 bytes（部分檔 CRLF），不是全部轉LF；`instructions_sha256` 是 Python assignment 原碼加一個LF，值為 `83b14376…`，不是字串值的 `0f621a77…`。兩種 prompt 計算都與 `4f94fbfb` 相同。初次自寫檢查器把兩者混用，故誤列 publication／references／prompt 不一致；修正檢查器後只有 HF-06 的 `memory.py` 是真缺漏。這是審查工具假設的修正，沒有放寬產品。

下一施工以[H4 runtime 執行計畫](../../../plans/2026-09-14-jd-h4-runtime-integration.md)為唯一詳細順序：先一批 B1 真 PG 保存／恢復和有界 batch 接合，再 B2 交接／C 競爭，最後完整通知與宿主生命週期。廣搜到此停止；只按實際接點缺口补證據，不再以「再核一次窗口」代替產品進度。
