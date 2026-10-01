# 實作驗證與需求追溯

- 狀態：**分層施工與驗證進行中**；本頁只建立對照，已執行範圍沿任務 evidence；不以文件審查或元件測試勾選整體產品通過。
- 需求效果唯一來源：[V01–V28](../architecture/verification.md)、[E01–E15](../specs/2026-09-27-shared-agent-execution-and-state-design.md#71-職責異常測試映射全部待執行)、[JDT-01–09](../specs/2026-09-29-jd-model-tool-contract-review.md#7-剩餘工程-gate全部待實作驗證)。任務完成狀態在[task list](../plans/2026-09-29-target-rebuild/tasks.md)。

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

## 2. V 驗收對照任務

| 需求 | 主要任務 | 首要測試責任／證據 |
|---|---|---|
| V01 | T02、T05、T07、T15 | scope 隔離，重名／相同序號的兩檔案 |
| V02 | T02、T08 | 開場 1、pending input 與正式序號，取消不引用 |
| V03 | T14、T17 | 長訪談前案後補／更正與按需回查 |
| V04 | T08、T12 | pinned Memory 與背景發布交錯 |
| V05 | T06、T08、T10、T16 | 128K／160K 邊界、超量與完整 compact 採用 |
| V06 | T06、T16 | native output→input、mixed message／calls |
| V07 | T06、T08、T12 | R／tool／Step 各位置程序重啟 |
| V08 | T08、T09、T12 | 暫停、取消、final、晚到 writer 競爭 |
| V09 | T08、T09、T12 | 正式完成原子性、斷線同答覆重取 |
| V10 | T10、T11、T12 | F／派送／合併要求／重啟 |
| V11 | T05、T10、T11 | B 權限、gap、私有 context 與同批回交 |
| V12 | T04、T05、T12 | 候選綁定跟隨，歷史快照不變 |
| V13 | T04、T11、T12 | 下層改動傳到固定引用修訂，未變重用 |
| V14 | T10、T11、T14、T17 | diff 的新增／刪除／改回與按需語意處理 |
| V15 | T11、T12、T17 | B 最終失敗，A 續談與原話可讀 |
| V16 | T03、T07 | JD 完整 CRUD、同規則與多對多關係 |
| V17 | T07、T08、T17 | 人工改動＋來源換版兩基準、明確確認 |
| V18 | T04、T07 | 原來源 identity、改名／移除／同名重用 |
| V19 | T05 | V4A 唯一近似、所有 hunks 原子 |
| V20 | T05、T07、T16 | 精簡 map、完整局部、按需下鑽及定位 |
| V21 | T09、T13、T15 | 公開中間訊息／正式 PDF／敏感資料 |
| V22 | T06、T12、T16 | 未知原結果與有界付費 attempts |
| V23 | T13、T17 | 條件撤回 JD，不倒轉訪談／Memory |
| V24 | T05、T07、T15 | 注入／偽造 scope 的後端拒絕 |
| V25 | T14、T17 | 真人顧問與員工耗時分別記；實際用戶試點待安排，不是技術切換先決條件 |
| V26 | T06、T07、T10、T16 | 發送邊界實際 context；工具成本與效果同測 |
| V27 | T04、T08、T12、T15 | 回退基底／快照／公開歷史與保留關係 |
| V28 | T02、T08、T10、T12 | 正式序號 K／H／F＋前問範圍 |

## 3. 執行／工具 gate 不遺漏

| Gate | 承接任務 | 追加的必驗接縫 |
|---|---|---|
| E01、E02、E03 | T06、T12、T16 | output／compact 完整保存；第一個 Step 的 R 同樣可續 |
| E04、E05、E06 | T03、T04、T06、T12 | 原 operation 與候選位置；原結果不明不能當沒做 |
| E07、E08、E09 | T08、T09、T12 | 執行資格、控制競爭、取消不帶中途 C |
| E10 | T10、T11、T12 | B 回交仍有合法私有歷史，無理解外洩 |
| E11 | T06、T08、T10、T12 | C 尚未採用／採用不明／取消後的邊界 |
| E12、E13 | T08、T11、T12 | formal commit／通知成功確認遺失與重掃 |
| E14 | T03、T09、T13 | 預覽、人工寫入限制、正式 PDF |
| E15 | T06、T12、T16 | 不疊 retry、不重置預算、模型等待無長交易 |
| JDT-01 | T01、T07、T16 | 生成 strict variants、實際 provider wire |
| JDT-02、JDT-03、JDT-04、JDT-05、JDT-06 | T03、T07、T12 | CRUD／定位／來源粒度／原子修訂／兩類差異 |
| JDT-07、JDT-08 | T06、T08、T12 | 候選到正式、原 call/result、多工具按序 |
| JDT-09 | T14、T16、T17 | 同資料比較成功率、錯改、工具及 context 成本 |

## 4. 第一組可執行測例應長什麼樣

T08／T12 的 `test_cancelled_turn_cannot_publish_late_tool_result`：

1. 建立 fresh job file、有正式 JD／Memory；A 輪前 C 已採用，輸入 a 尚無正式序號。
2. 保存原 R，其中一筆工具要求改候選；在候選提交前插入 barrier，另一連線先確立取消。
3. 放行舊工具及晚到模型／checkpoint；斷言正式 JD、正式訪談序號、Memory frontier 均未因 a 改變。
4. 新輸入 b 新 Turn 組裝：含有效輪前 C、目前 maps，不含 a 或包含 a 的輪中 C；同時存在的獨立 Memory 新發布不被回滾。
5. 互換順序再測完成先贏時返回同一正式結果，不假造取消成功。所有切斷由 hooks／barriers 控制，不靠固定 sleep。

這測例驗外部可見效果；不要求 production 新增名為 barrier 的 API。測試注入在 adapter／repository 邊界，僅測試 fixture 可用。

另以 property-based／parametrized 測試對 T04 快照生成合法 CRUD 序列：任意歷史快照不變、同身分單一修訂、delete 不改歷史、changed-back 仍新修訂。可使用 Hypothesis 等成熟工具；有具體不變量才引入，不另造 fuzz framework。

## 5. 命令與證據

T01 落地基礎命令；產品旅程及 provider 命令隨相應任務加入，不建立假可用入口。已可執行的精確命令見 [backend README](../../apps/api/README.md)及 [frontend README](../../apps/web/README.md)：

| 使用方 | 待建立並實測的命令 |
|---|---|
| API | `uv run --project apps/api pytest …`；unit／contracts／integration／journeys 分 marker，預設不外送 |
| Python 品質 | `uv run --project apps/api ruff check apps/api`、`ruff format --check`；mypy 只選新 package |
| Web | 新 workspace `@caliburn/frontend` 的 `test`、`typecheck`、`lint`、`build`；`test:e2e` 在 T09 UI 旅程加入，不能把 T01 元件測試當 E2E |
| 契約 | 新 API package／script 的 `codegen`、`codegen:check`；再生無 diff |
| 文檔 | links／anchors、JSON fences、Mermaid render、task DAG／gate coverage、`git diff --check` |

每項證據包含 commit／版本、配置、資料 scope、命令、期望、觀察、失敗與限制。provider 加實際 usage／成本及 request IDs（不含密鑰），整合加程序／交易交錯記錄。原話及完整 request 不默認永久記錄；只保留當次測試必要且授權的資料。

**技術切換 gate：**所有適用確定性／機制／核心旅程測例通過；真模型重大事實、權限、引用錯誤不能用平均分掩蓋。非確定品質用既有指南 rubric，結果分布及樣本限制明說，不臨時改評分規則求過關。真實節時 ROI（V25）可列後續試點，不杜撰數字，也不迫使本機第一版新增營收／使用者研究平台。
