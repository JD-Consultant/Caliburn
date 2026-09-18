# Q019：完整 Context 預算與分析 Skills

> 2026-09-07 · `Q019-CONTEXT-SKILLS-WIRING-01` · **隔離接線／測試／整批獨立審核完成；自然模型品質尚未驗收。**
> 範圍／架構與來源：[短計畫](../plans/2026-09-07-context-budget-and-analysis-skills.md)。此頁只持有本段結果，不複製過去 Memory 討論。

## 1. 要完成的能力

| 項目 | 接線目標 | 驗收狀態 |
|---|---|---|
| SK-01 | 主顧問看精簡 Skills 清單，相關時讀分析方法；不每輪全載、不新增必填欄位 | 局部CLOSED：c93a1bd8＋fd9289a6，獨立審核通過 |
| CT-01 | A／B1／B2 的實際生成 request，整包 input＋輸出預留都受同一邊界核對 | 局部CLOSED：24b0038e＋4f56bb0d，獨立審核通過 |
| 整體 | 既有原生推理／壓縮、Memory／來源／錯誤恢復不被兩項接線破壞 | 主審514項通過；整批獨立審核Approved |

## 2. 為何這樣接，什麼不是官方保證

- **Skill 機制**使用 Deep Agents 的公開 `SkillsMiddleware`， metadata／正文分開讀；唯讀資產與 Memory 共用 filesystem tools，不因此帶入 shell、planning agent 或 JD 編輯。[官方 Skills](https://docs.langchain.com/oss/python/deepagents/skills)、[backends](https://docs.langchain.com/oss/python/deepagents/backends)
- **計數接點**使用 HTTPX 公開 request hook，看到 SDK 已序列化的 Responses body，再呼叫 OpenAI 官方 input count；不是自己猜加密 reasoning 大小。這是本案選用的保守 preflight，並非所有大廠必定每次多做一個請求。[HTTPX](https://www.python-httpx.org/advanced/event-hooks/)、[OpenAI input count](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count)
- **輸出空間**也要預留；設定的 output 上限包含 reasoning，不再重複扣一次。`truncation=disabled`，不靠 API 自動扔掉早期對話。原生 compaction 仍是另一項既有能力，計數不能預測未產生的 opaque item。[Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)、[Compaction](https://developers.openai.com/api/docs/guides/compaction)
- **代價**：每個需要生成的 request 多一次計數往返、資料傳輸；counter 有自己的 timeout。未量測真實端點延遲／用量，不宣稱免費或零成本。與模型的 input/output 計費紀錄分開說明；不把計數當另一次顧問分析。
- **本地超限**不應冒充網路故障。鎖定 SDK3.8 明確對 `OpenAIError` 原樣傳播，LC 的 `ModelError` 公開型別可表達不可重試的 context 錯誤；本輪真SDK＋合成HTTP回歸已驗證這個接點及服務收尾，真實endpoint另測。[固定 SDK source](https://github.com/openai/openai-python/blob/v3.8.0/src/openai/_base_client.py)、[LC exceptions](https://reference.langchain.com/python/langchain-core/exceptions/)

## 3. 分析方法的依據與界線

沿用已研究的 **方法**，不搬舊 schema／authority／固定階段：

- 工作範圍與具體案例：釐清實際行動、目的、情境、結果及角色；看見不明之處就問，不憑職稱補工作。OPM 說明職務分析包含任務、能力及其關聯；它沒有規定本案對話輪數或必填框架。[OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)
- 案例比較與共同工作：換句話說／完全涵蓋，與「相似但補充新的条件」不同；不能把兩個客戶網站直接當兩個固定職務，也不能去重時把案例差異刪掉。依原研究 [Task 邊界 §3.5](../../../../docs/specs/2026-07-28-task-boundary-merge-split-and-identity-research.md)及 [O*NET 2025 Revised Approach](https://www.onetcenter.org/reports/EmergingTasks_RevisedApproach.html)；O*NET 職業資料庫的多受訪者門檻與 discard 策略不搬入本案。
- 工作細節的深入問法：工作產出、可觀察的完成判準、實際用到的知識技能可以隨案例交錯追問；不等 Task 穩定才開始，不虛構 KPI／數值／能力級別。參考 [既有 P 方法原料](../../../../docs/specs/2026-08-01-opks-raw-performance-indicators.md)，只取目的與可觀察性；**不採該歷史稿的語意黑名單或舊資料掛載裁決**。

三份方法是本案提示內容的初稿，不是大廠提供的現成職務分析答案。依 Owner 要求先完成接線／審核，接著才用小額 Luna／medium 訪談檢查自然載入、追問品質、細節保留、重複分析與成本，逐步改 prompt。

## 4. 本輪證據

- 修改前完整基準：**427 passed／0 skipped，67.20s**，專用 PostgreSQL；1項既有 Starlette TestClient deprecation。沒有重啟／清空 Docker。
- CT 公開接點探針：真 ChatOpenAI＋SDK，mock count100／output30／capacity120 → counter1次、生成0次，直接不可重試的 ModelError，沒有SDK包裝成connectionerror或重試。
- Task1：初始RED7項缺Skills metadata／讀取路由→GREEN7項；補邊界後共30項新增，focused157passed。發現官方host型path拒絕拋ValueError，改由唯讀資產接點轉官方`ReadResult(error=...)`，讓模型收到輸入錯誤；未把I/O故障一律吞掉。全套 **457 passed／0 skipped，70.01s**；compileall／offline lock／diffcheck通過，1項既有TestClientwarning。Store/noStore metadata→按需讀、nativeopaque／compaction配對、C刷新、可信讀取重開恢復及B1不讀Skill ToolMessage皆有真framework＋合成HTTP測試。
- Task1 review找到同型 `ls` 路徑錯誤未回模型（SK1-R01/P2），以公開`LsResult(error)`補齊；RED兩個真ls失敗＋一個既有I/O傳播pass，另兩個grep預期為測試假設錯誤（官方回空命中）已校正且未改grep。修正後 **33項Skills測試通過，6.86s**；独立re-review確認CLOSED，其餘無finding。沒有將前次全套當修正後全套。
- Task2：35項真正缺接線的RED後實作。測試發現 SDK公開`base_url`使用不同URL型別，直接跨library比較會略過hook；以公開字串正規化修正。另補計數成功但JSON／形狀錯誤、非空input卻回0，以及Responses query參數略過比對的RED→GREEN；這些都不應被SDK當連線故障重試或直接放行。最終focused **178 passed／33.30s**，實作者全套 **512 passed／0 skipped／76.74s**。正式API測試採兩個真HTTP client＋MockTransport，沒有mock掉hook。
- Task2覆蓋：A每步包含當前／近期對話、原生items、Skill metadata與讀回正文、Memory導覽及讀取結果；B1含真正的structured-output schema，B2含工具錯誤回饋與後續讀取。超限在A開始前／讀Skill後皆安全封閉解鎖；B1／B2都blocked，之後三次排程不重發。Counter暫時失敗只有SDK原生三次嘗試，生成0次；本地超限不重試。
- 主審第一次整批重跑（24b0038e）：512 passed／0 skipped，75.52s，含專用PostgreSQL。獨立review另發現 **CT2-R01/P2**：counter HTTP200若含非法UTF-8，`UnicodeDecodeError`未歸為配置錯誤，外層SDK會誤包裝為可重試連線錯誤（count3次／生成0次）。這是合成邊界案例，不聲稱真實provider經常回這種內容。
- CT2-R01修正：先新增兩個真SDK／API回歸，RED確認count3、可重試及A中斷；僅將計數解碼的`UnicodeDecodeError`轉成既有配置錯誤。GREEN **54 passed／9.43s**；count1、生成0、不可重試、A安全封閉／resume409／原文保留一次，真正timeout／500的原生retry不變。獨立限定複核 **CLOSED**，Task2與整批均 **Approved**，無剩餘finding。
- **主審最終重跑（4f56bb0d）：514 passed／0 skipped，71.95s，exit0**，含專用PostgreSQL；1項既有Starlette TestClient deprecation。修正後`compileall`、`uv lock --check --offline`（83 packages）、整批與工作區`git diff --check`均通過。逐項數字不與最終全套相加。
- 本輪付費模型呼叫：**0**。合成 HTTP 證明程式接線，不證明官方實際端點／模型品質／實際帳單。

## 5. 尚未納入本段

不接 JD／UI／production；未合併／推送。一般無引用的久遠原文查找與 grep 上限提示沿既有後續邊界，不因本段完成就聲稱整體已毫無缺口。

本次正式入口只支援既有**同步**執行；不宣稱`ainvoke`已受此hook保護。部署必須明訂`Q019_CONTEXT_WINDOW_TOKENS`，與輸出預留／compaction門檻相容。API解析同一`base_url`供生成與計數兩client使用；不支持官方count的自訂endpoint、遠端prompt模板及未核對的內容欄位，均明確失敗，不偷偷退回估算。

過大request會沿既有不可重試配置錯誤收尾，另給`context_budget_exceeded`代碼；A解鎖、B停止重送。**這不是任意長對話自動恢復**：未產生的compaction不能預先計入，新輸入／工具結果突然過大可能仍需調整容量或壓縮策略，不偷偷丟資料。

下一gate：先確認真實endpoint的計數／原生延續契約及實際延遲，再以小額Luna／medium短訪談檢查Skill自然選用、問法、案例差異、記憶整理／更正／深讀及用量，依結果改顧問與Memory prompt。不把本段514項離線接線測試當自然模型品質分數；若真實契約、效果或成本推翻預期，再開具體finding討論，不重新泛論全套架構。

## 6. 保存與回看

程式範圍 `3ba74848..4f56bb0d`：Skills `c93a1bd8`、讀取錯誤修正 `fd9289a6`、Context預算 `24b0038e`、解碼錯誤修正 `4f56bb0d`。本地保存標記為 `q019-context-skills-v1`；不merge/push。方法與實際啟動設定見 [package README](../../experiments/analysis-agent/README.md)，後續決策入口仍為主checkout [current decisions](../../../../docs/current-decisions.md)。本頁只關閉已驗接線，不替代production ADR或自然模型驗收。
