# T3：原能力、固定新輪與精確換窗接續

日期：2026-10-07。責任依 [INTPLAN §6.6／6.9](../../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md)，施工依[計畫](../../2026-10-07-interview-plan-implementation-and-comparison.md)。不以機制通過判斷模型或 JD 品質。

## 可辨 Red 與修正

- 新輪完整 nullable plan item：原程式只有 app data／raw，`len(items)==3` 實際 `2==3`；舊 `TurnContext` 沒有 plan position。接 v2 原 binding 與同交易 start 後，新／舊能力及原 request 固定 8 例通過。
- 保存 binding 型別：Pydantic strict Literal 仍接受 `true`／`1.0` 作版本 `1`，新增 projection 反例實際 `DID NOT RAISE`。沿同 TypeAdapter 加 JSON 原型別保真檢查，沒有第二套 shape validator；projection 11 例通過。
- start 已提交、原 capture 完全不存在，而今天關閉工具：原 guard 只在今日工具啟用時查 start，反例實際 `DID NOT RAISE ExecutionStateError`。改為 reliable absence 時無條件查原 start；原 pending graph 仍以 `None` resume 原模板、讀本輪 base，第一份完整 binding 才固定 Memory／F。獨立審查指出過嚴 node guard 後已撤回，沒有把合法 pending 工作當成損毀。
- 最後獨立審查核 saved toolkit：`minLength:true/1.0`、`maxLength:16000.0` 與新增不相容 assertion 六例實際 `DID NOT RAISE`；先導原 manifest 完整停止後才修 source，核精確整數型別及窄 assertion keys，annotation 字串不要求今天文案相同。19 例由 reviewer 獨立 Red–Green，沿[審查證據](review-context-final.md)。

## 已驗範圍

- 新輪 history → full plan → app data → raw；null／空／原字串，v1 不被今日 v2 工具 retrofit，v2 亦不因今日工具取消而降級。
- full native C 與保留項目不截斷；已保存 projection 重入不讀後來 head，不重新序列化原 item；C position 指向原 parent request 的精確完整 checkpoint。
- plan 讀取失敗／scope 不符、projection ACK 遺失、inactive 先委派 native 核帳；不把不可用當空筆記。
- 獨立 boundary tests 額外驗 raw `__start__` 已保存但 ACK 遺失、parent 下一 request 保存前／後故障；完整 C＋原 item 接回，原 compact／reader 各一次。
- 已完成重入以新的 saver／runner／client 核原完整 final、capture、exchange 與 final plan，provider transport 一旦被呼叫便使測試失敗；不使用 active-only preview。

## 命令與結果

使用本輪新自有 PostgreSQL `_test` 資料庫之 pytest 隨機 schema；現有服務與資料未動。SDK MockTransport 全為合成回應，以下不含真 provider 品質：

- `pytest tests/unit/test_interview_plan_projection.py tests/unit/test_role_prompt_contracts.py tests/unit/test_reference_tool_registration.py -q`：56 passed（後增 3 例 projection 版本型別）。
- `pytest tests/integration/test_consultant_runner.py tests/integration/test_consultant_runner_recovery.py tests/integration/test_interview_plan_context_binding.py -q`：18 passed（其後加 orphan／fresh saver 覆蓋）。
- 關聯 PG 9 檔：92 passed／1 舊 compaction fixture fail；舊 fixture 原先只計 app data＋raw，已明確加入 full plan 並保留完整 C prefix 校驗，該檔重跑 4 passed。
- 全 API unit/contracts：1,456 passed；全正式源碼 mypy 340 files 通過，Ruff 503 files 通過（其後新反例與邊界接線由總驗證更新）。

剩餘總檢查與真實 P1／P2、成本及語意評閱由計畫及比較原件維護；未 commit／push／merge。本頁保留實際先後證據，最終驗證數字另附，不合算不同時間的測試作全面成功。

最後 saved schema 修正後，主代理新跑工具／projection／boundary／prompt／reference 五個 unit 檔：**103 passed，2.23 秒**。真 PostgreSQL 的原 context binding、新 plan binding、runner、runner recovery、native compaction 五檔：**32 passed，40.86 秒**；Ruff／format 兩檔、mypy source 一檔均通過。全套回歸與其他層級沿 [T5](t5-validation.md)，不是重新宣稱所有較早數字都在最後 source 重跑。
