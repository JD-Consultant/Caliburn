# 實作驗證與需求追溯

- 狀態：**持續維護的驗證與需求追溯表**。本頁定義驗證責任，表內要求不構成通過證明。已驗、部分、離線及未驗範圍依[架構驗證](../architecture/verification.md)判讀。
- 需求效果唯一來源：[V01–V28](../architecture/verification.md)、[共用執行與恢復](agent-execution.md)、[JD 工具與保存](jd-storage.md)。執行原件與結果只留本機。

安排測試時先選[驗證層級](#1-分層測試不以-mock-冒充產品)，再查[V 責任對照](#2-v-驗收與責任對照)及[E／JDT 接縫](#3-執行工具-gate-不遺漏)。測例寫法、命令入口與證據要求分別見[§4](#4-行為反例的寫法)、[§5](#5-命令與證據)；已驗及未驗結果由[§6 的入口](#6-已知限制與未驗範圍)查閱。

## 1. 分層測試，不以 mock 冒充產品

| 層級 | 工具／目標 | 必須成立 |
|---|---|---|
| Unit | pytest／Vitest；純命令、來源判定、投影、context transition | 快且確定，不需模型金鑰／資料庫；測效果不是所有內部呼叫 |
| Contract | JSON Schema／生成物／真 SDK mock transport | 實際 wire、角色、枚舉、scope、items 次序與 call pairing；生成不漂移 |
| Integration | 真 PostgreSQL＋官方 saver＋HTTP client／獨立程序 | 交易、固定歷史、原操作、控制資格與重啟；不用 SQLite／MemorySaver 替代 |
| Browser protocol | Playwright Test＋明示攔截的 HTTP 回覆 | 真瀏覽器的跨頁、Web Locks、焦點及送出次序；攔截回覆不算後端交易或模型證據 |
| UI journey | Playwright Test＋真 API／PG＋需要時的 scripted provider | 候選預覽、SSE 重連、人工鎖定、引用查看、PDF；依實際接線標明哪些回覆由替身提供 |
| Provider | 有界 OpenAI direct API | strict 真接受、reasoning／compact 接續、模型能力／計量；不讀內部推理 |
| Quality／product | 合成訪談及授權的真人試點 | 事實、責任、範圍、細節、精簡與引導，兼看成本／耗時，不以 token 越少越好 |

測試資料預設全合成，並明確區分已知／未知資訊。除了正常路徑，也須涵蓋使用者取消、來源刪除、同名重用、無既有依賴的新情境、多工具失敗及持續 quota 問題等反例。

## 2. V 驗收與責任對照

依主要責任分組，保留原 V 編號，方便與架構反例矩陣交叉查閱。

### 來源與作用範圍

| 需求 | 主要責任 | 首要測試情境 |
|---|---|---|
| V01 | 訪談／JD／Memory／傳輸邊界 | scope 隔離，重名／相同序號的兩檔案 |
| V02 | 訪談／A 完成 | 開場 1、pending input 與正式序號，取消不引用 |
| V04 | A 綁定／Memory 發布 | pinned Memory 與背景發布交錯 |
| V24 | 工具／領域權限 | 注入／偽造 scope 的後端拒絕 |
| V28 | 訪談讀取／角色綁定 | 正式序號 K／H／F＋前問範圍 |

### 執行、控制與恢復

| 需求 | 主要責任 | 首要測試情境 |
|---|---|---|
| V05 | 共用執行／角色準備 | 128K／160K 邊界、超量與完整 compact 採用 |
| V06 | Responses adapter／共用執行 | native output→input、mixed message／calls |
| V07 | 共用執行／業務原結果 | R／tool／Step 各位置程序重啟 |
| V08 | A 控制／supervisor | 暫停、取消、final、晚到 writer 競爭 |
| V09 | A 完成／公開結果 | 正式完成原子性、斷線同答覆重取 |
| V22 | 外送准入／原件恢復 | 未知原結果與有界付費 attempts |
| V27 | 歷史／候選／保留責任 | 回退基底／快照／公開歷史與保留關係 |

### Memory 整理與發布

| 需求 | 主要責任 | 首要測試情境 |
|---|---|---|
| V10 | Memory 調度 | F／派送／合併要求／重啟 |
| V11 | B1／B2／Memory 編排 | B 權限、私有 context、B1 → B2 單向交接與階段恢復 |
| V12 | Memory 候選／快照 | 候選綁定跟隨，歷史快照不變 |
| V13 | Memory 發布 | 下層改動傳到固定引用修訂，未變重用 |
| V14 | Memory diff／B2 分析 | diff 的新增／刪除／改回與按需語意處理 |
| V15 | Memory 失敗／A context | B 最終失敗，A 續談與原話可讀 |
| V19 | Memory 正文編輯 | V4A 唯一近似、所有 hunks 原子 |

### JD、工具與交付

| 需求 | 主要責任 | 首要測試情境 |
|---|---|---|
| V16 | JD 領域／人工與模型工具 | JD 完整 CRUD、同規則與多對多關係 |
| V17 | JD 來源／A 核對 | 人工改動＋來源換版兩基準、明確確認 |
| V18 | JD 引用／Memory 固定修訂 | 原來源 identity、改名／移除／同名重用 |
| V20 | JD／Memory 工具 | 精簡 map、完整局部、按需下鑽及定位 |
| V21 | 公開訊息／PDF／安全邊界 | 公開中間訊息／正式 PDF／敏感資料 |
| V23 | JD 撤回 | 條件撤回 JD，不倒轉訪談／Memory |

### 分析品質與使用效果

| 需求 | 主要責任 | 首要測試情境 |
|---|---|---|
| V03 | A／分析品質 | 長訪談前案後補／更正與按需回查 |
| V25 | 品質評估／真人試點 | 真人顧問與員工耗時分別記；實際用戶試點待安排，不是技術切換先決條件 |
| V26 | 請求組裝／角色工具 | 發送邊界實際 context；工具成本與效果同測 |

## 3. 執行／工具 gate 不遺漏

### 共用執行 E01–E15

| Gate | 承接責任 | 必驗接縫 |
|---|---|---|
| E01、E02、E03 | Responses／compact／saver | output／compact 完整保存；第一個 Step 的 R 同樣可續 |
| E04、E05、E06 | JD／Memory 原操作與共用執行 | 原 operation 與候選位置；原結果不明不能當沒做 |
| E07、E08、E09 | A 控制／歷史基底 | 執行資格、控制競爭、取消不帶中途 C |
| E10 | Memory 角色歷史／交接 | B1 → B2 交接與同階段恢復沿合法私有歷史；B1 無理解外洩，B2 不回交 |
| E11 | 共用 compact／資格採用 | C 尚未採用／採用不明／取消後的邊界 |
| E12、E13 | A 完成／Memory 發布及調度 | formal commit／通知成功確認遺失與重掃 |
| E14 | 候選 UI／人工准入／PDF | 預覽、人工寫入限制、正式 PDF |
| E15 | executions／外送 workflow | 不疊 retry、不重置預算、模型等待無長交易 |

### JD 模型工具 JDT-01–09

| Gate | 承接責任 | 必驗接縫 |
|---|---|---|
| JDT-01 | Schema 生成／provider adapter | 生成 strict variants、實際 provider wire |
| JDT-02、JDT-03、JDT-04、JDT-05、JDT-06 | JD 領域／模型工具 | CRUD／定位／來源粒度／原子修訂／兩類差異 |
| JDT-07、JDT-08 | JD 候選／A 完成／共用執行 | 候選到正式、原 call/result、多工具按序 |
| JDT-09 | JD 模型品質與成本評估 | 同資料比較成功率、錯改、工具及 context 成本 |

## 4. 行為反例的寫法

以 `test_cancelled_turn_cannot_publish_late_tool_result` 表達取消競爭的測例意圖：

1. 建立 fresh job file、有正式 JD／Memory；A 輪前 C 已採用，輸入 a 尚無正式序號。
2. 保存原 R，其中一筆工具要求改候選；在候選提交前插入 barrier，另一連線先確立取消。
3. 放行舊工具及晚到模型／checkpoint；斷言正式 JD、正式訪談序號、Memory frontier 均未因 a 改變。
4. 新輸入 b 新 Turn 組裝：含有效輪前 C、目前 maps，不含 a 或包含 a 的輪中 C；同時存在的獨立 Memory 新發布不被回滾。
5. 互換順序再測完成先贏時返回同一正式結果，不假造取消成功。所有切斷由 hooks／barriers 控制，不靠固定 sleep。

這個測例驗證外部可見效果，不要求 production 新增名為 barrier 的 API。測試注入位於 adapter／repository 邊界，僅供測試 fixture 使用。

另以 property-based／parametrized 測試對 Memory 快照生成合法 CRUD 序列：任意歷史快照不變、同身分單一修訂、delete 不改歷史、changed-back 仍新修訂。可使用 Hypothesis 等成熟工具；有具體不變量才引入，不另造 fuzz framework。

## 5. 命令與證據

精確命令由 [backend README](../../apps/api/README.md)及 [frontend README](../../apps/web/README.md)維護；本頁只列檢查用途，不手抄可能失同步的 shell 指令。一般檢查不外送模型，provider／品質實測依當次授權及資料範圍執行。

| 使用方 | 檢查用途 |
|---|---|
| API | 單元、契約、真 PostgreSQL 及程序恢復，依改動風險選取 |
| Python 品質 | Ruff lint／format、mypy strict |
| Web | 單元、型別、lint、build；有互動風險時跑 Playwright 旅程 |
| 契約 | 從唯一 schema 再生並確認無差異 |
| 文件 | links／anchors、JSON fences、Mermaid 語法與差異一致性；純文字整理不重跑產品全套 |

證據紀錄沿[貢獻指南](../../CONTRIBUTING.md#驗證與提交)，須能核對下列內容：

- 所有測試：commit／版本、配置、資料 scope、命令、期望、觀察、失敗與限制。
- Provider 測試：另記實際 usage／成本及 request IDs，不含密鑰。
- 整合測試：另記程序／交易交錯。

原話及完整 request 只保留當次測試必要且授權的資料。

變更驗收按適用範圍核對確定性、機制及核心旅程測例。真模型的重大事實、權限、引用錯誤須逐項揭露，不能用平均分掩蓋。

非確定品質用[既有案例 rubric](../../apps/api/tests/fixtures/job_analysis_quality/rubric.md)，明說結果分布及樣本限制，不臨時改評分規則求過關。

真實節時 ROI（V25）可列後續試點，不杜撰數字，也不因此新增營收／使用者研究平台。

### 5.1 Web 與交付的現行測試入口

以下按責任列出可執行的代表測試，以及各自要辨認的差異，方便修改接線後選擇反例；這不是最近一次通過清單。

正式 App 的 QueryClient factory 與輸入 validator 直接供整合／契約測試使用，避免測試另建一套政策而漏掉實際行為。

- **HTTP 失敗與原命令**

  [HTTP 邊界](../../apps/web/src/shared/api/http.test.ts)、[命令拒絕](../../apps/web/src/app/command-boundaries.test.tsx)

  timeout、取消、非 JSON／非法格式及業務拒絕分開；一般錯誤不能退休待確認命令

- **卸載、晚到成功與刷新**

  [共用命令](../../apps/web/src/shared/commands/use-stored-command.test.tsx)、[真 API 晚到回應](../../apps/web/tests/e2e/command-lifecycle-focus.spec.ts)

  原表單卸載仍刷新並條件清理；較新命令不被刪除；刷新失敗不改判已知成功

- **訪談 hint 跨頁競爭**

  [store](../../apps/web/src/features/interview/turn-hint-store.test.ts)、[多分頁](../../apps/web/tests/e2e/hint-concurrency.spec.ts)

  同檔共鎖、不同檔並行、舊 ACK、清除後回覆、等待鎖期間的原文保護；部分 Turn／POST 回覆由瀏覽器攔截提供

- **刪除與路由範圍**

  [刪除清理](../../apps/web/src/app/use-deleted-job-files.test.tsx)、[UUID 路由](../../apps/web/tests/e2e/uuid-route.spec.ts)

  重複通知去重、失敗後只重試本機步驟、漏接後 metadata 確認；非法 UUID 不發檔案查詢

- **SSE 與已保存歷史**

  [SSE hook](../../apps/web/src/features/interview/use-consultant-activity-stream.test.tsx)、[活動 HTTP](../../apps/api/tests/integration/test_activity_stream.py)、[摘要 HTTP](../../apps/api/tests/integration/test_reasoning_summary_http.py)

  CLOSED 有限恢復與 CONNECTING 原生重連分開；無模型設定仍可讀已保存歷史；不以斷線宣告完成

- **JD 導覽與草稿**

  [工作區語意](../../apps/web/src/app/WorkspaceLayout.test.tsx)、[JD 導覽](../../apps/web/tests/e2e/jd-navigation.spec.ts)、[逐欄編輯](../../apps/web/tests/e2e/jd-inline-edit.spec.ts)

  展開祖先後才捲動／聚焦；窄寬切換保留掛載；背景讀取不替換草稿基底

- **測試接線**

  [QueryClient 政策](../../apps/web/src/app/query-client.test.tsx)、[輸入契約](../../apps/web/src/shared/api/canonical-input.contract.test.ts)

  測正式 factory／validator，不能以測試副本證明正式接線

- **關閉期限與自有程序**

  [啟動器單元](../../scripts/run-app.test.mjs)、[真程序](../../scripts/run-app.process.test.mjs)、[checkpoint 等鎖](../../apps/api/tests/integration/test_launcher_checkpoint_shutdown.py)

  90 秒正常期限、五秒強制確認；POSIX 子群組及 Windows 路徑依平台區分；PG 測試用合成取消通知，不冒充真 console Ctrl+C

- **Docker／RAG 連線範圍**

  [Compose 解析](../../scripts/docker-compose.test.mjs)

  基本模式、公版 overlay 及獨立 RAG 分開核對；設定解析不等於目標 GPU／模型已可運作

#### 瀏覽器測試的共同界線

[Playwright 配置](../../apps/web/playwright.config.ts)要求明示 loopback 測試 App，使用單一 Chromium worker、零重試，失敗保留 trace／截圖。

真正 PostgreSQL、程序與瀏覽器測試須使用隔離合成資料；所需外部環境不可用時明列未完成，不能把攔截或 skip 當成整合通過。

## 6. 已知限制與未驗範圍

本頁維護測試分工及追溯，不維護另一份結果摘要。已知限制、受測版本及後續證據從下列責任頁查閱：

| 要確認的結果 | 證據入口 |
|---|---|
| A／B 接續、壓縮、Memory 發布及取消恢復 | [架構驗證反例矩陣](../architecture/verification.md#2-核心反例矩陣) |
| JD 分析、來源核對、Plan 及真人使用效果 | [架構驗證與限制](../architecture/verification.md) |
| PDF、文字層及前端互動的覆蓋 | [介面與交付](interface-and-delivery.md) |
| 已確認的後續工作及產品政策 | [架構與現行責任](../architecture/README.md) |

舊證據不能代表後續版本的所有情境，A 與 B 的證據也不能互相替代；具體結論須沿原件核對。
