# 實作驗證與需求追溯

- 狀態：**持續維護的驗證與需求追溯表**。本頁定義驗證責任，表內要求不構成通過證明。已驗、部分、離線及未驗範圍依[架構驗證](../architecture/verification.md)與[產品實驗](../experiments/product-validation/README.md)判讀。
- 需求效果唯一來源：[V01–V28](../architecture/verification.md)、[E01–E15](../specs/2026-09-27-shared-agent-execution-and-state-design.md#71-職責異常驗證映射)、[JDT-01–09](../specs/2026-09-29-jd-model-tool-contract-review.md#7-行為邊界與證據層級)。實驗原件與結果由[產品驗證與實驗資料](../experiments/product-validation/README.md)路由。

## 1. 分層測試，不以 mock 冒充產品

| 層級 | 工具／目標 | 必須成立 |
|---|---|---|
| Unit | pytest／Vitest；純命令、來源判定、投影、context transition | 快且確定，不需模型金鑰／資料庫；測效果不是所有內部呼叫 |
| Contract | JSON Schema／生成物／真 SDK mock transport | 實際 wire、角色、枚舉、scope、items 次序與 call pairing；生成不漂移 |
| Integration | 真 PostgreSQL＋官方 saver＋HTTPX／獨立程序 | 交易、固定歷史、原操作、控制資格與重啟；不用 SQLite／MemorySaver 替代 |
| UI journey | Playwright Test＋離線 scripted provider | 真 API／PG、候選預覽、SSE 重連、人工鎖定、引用查看、PDF |
| Provider | 有界 OpenAI direct API | strict 真接受、reasoning／compact 接續、模型能力／計量；不讀內部推理 |
| Quality／product | 合成訪談及授權的真人試點 | 事實、責任、範圍、細節、精簡與引導，兼看成本／耗時，不以 token 越少越好 |

測試資料預設全合成且有明確已知／未知。使用者取消、來源刪除、同名重用、無既有依賴的新情境、多工具失敗、持續 quota 問題都要有反例，不只測順路。

## 2. V 驗收與責任對照

| 需求 | 主要責任 | 首要測試情境 |
|---|---|---|
| V01 | 訪談／JD／Memory／傳輸邊界 | scope 隔離，重名／相同序號的兩檔案 |
| V02 | 訪談／A 完成 | 開場 1、pending input 與正式序號，取消不引用 |
| V03 | A／分析品質 | 長訪談前案後補／更正與按需回查 |
| V04 | A 綁定／Memory 發布 | pinned Memory 與背景發布交錯 |
| V05 | 共用執行／角色準備 | 128K／160K 邊界、超量與完整 compact 採用 |
| V06 | Responses adapter／共用執行 | native output→input、mixed message／calls |
| V07 | 共用執行／業務原結果 | R／tool／Step 各位置程序重啟 |
| V08 | A 控制／supervisor | 暫停、取消、final、晚到 writer 競爭 |
| V09 | A 完成／公開結果 | 正式完成原子性、斷線同答覆重取 |
| V10 | Memory 調度 | F／派送／合併要求／重啟 |
| V11 | B1／B2／Memory 編排 | B 權限、私有 context、B1 → B2 單向交接與階段恢復 |
| V12 | Memory 候選／快照 | 候選綁定跟隨，歷史快照不變 |
| V13 | Memory 發布 | 下層改動傳到固定引用修訂，未變重用 |
| V14 | Memory diff／B2 分析 | diff 的新增／刪除／改回與按需語意處理 |
| V15 | Memory 失敗／A context | B 最終失敗，A 續談與原話可讀 |
| V16 | JD 領域／人工與模型工具 | JD 完整 CRUD、同規則與多對多關係 |
| V17 | JD 來源／A 核對 | 人工改動＋來源換版兩基準、明確確認 |
| V18 | JD 引用／Memory 固定修訂 | 原來源 identity、改名／移除／同名重用 |
| V19 | Memory 正文編輯 | V4A 唯一近似、所有 hunks 原子 |
| V20 | JD／Memory 工具 | 精簡 map、完整局部、按需下鑽及定位 |
| V21 | 公開訊息／PDF／安全邊界 | 公開中間訊息／正式 PDF／敏感資料 |
| V22 | 外送准入／原件恢復 | 未知原結果與有界付費 attempts |
| V23 | JD 撤回 | 條件撤回 JD，不倒轉訪談／Memory |
| V24 | 工具／領域權限 | 注入／偽造 scope 的後端拒絕 |
| V25 | 品質評估／真人試點 | 真人顧問與員工耗時分別記；實際用戶試點待安排，不是技術切換先決條件 |
| V26 | 請求組裝／角色工具 | 發送邊界實際 context；工具成本與效果同測 |
| V27 | 歷史／候選／保留責任 | 回退基底／快照／公開歷史與保留關係 |
| V28 | 訪談讀取／角色綁定 | 正式序號 K／H／F＋前問範圍 |

## 3. 執行／工具 gate 不遺漏

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

這測例驗外部可見效果；不要求 production 新增名為 barrier 的 API。測試注入在 adapter／repository 邊界，僅測試 fixture 可用。

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



每項證據包含 commit／版本、配置、資料 scope、命令、期望、觀察、失敗與限制。provider 加實際 usage／成本及 request IDs（不含密鑰），整合加程序／交易交錯記錄。原話及完整 request 不默認永久記錄；只保留當次測試必要且授權的資料。

**變更驗收：**按適用範圍核對確定性、機制及核心旅程測例；真模型重大事實、權限、引用錯誤逐項揭露，不能用平均分掩蓋。非確定品質用既有指南 rubric，結果分布及樣本限制明說，不臨時改評分規則求過關。真實節時 ROI（V25）可列後續試點，不杜撰數字，也不因此新增營收／使用者研究平台。

## 6. 已知限制與未驗範圍

- Luna 仍有跨輪漏引、未提交來源對齊及定位錯誤反例；短定位與工程驗收不等於分析品質改善。
- B1／B2 輪前壓縮已有調低門檻的探針觀察，壓縮後完成發布等分支仍未完整實測；A 與 B 的證據不能互相替代。
- Memory 最終失敗後需正式訪談再前進三輪才允許新批次；此政策仍待確認，尚未於真長旅程自然觸發。
- 真人顧問與員工的實際省時效果未驗；合成樣例不代表一般使用收益。
- PDF 部分字型的文字層複製／搜尋限制、就地編輯真實輸入法的跨瀏覽器驗證仍未解決或未覆蓋。

各項證據由[目前決策](../current-decisions.md)及[實驗發現](../reports/experiment-findings.md)路由；本頁不另抄批次數字，也不把未驗項目改記為通過。
