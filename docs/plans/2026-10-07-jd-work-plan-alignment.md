# JD 工作計畫：工程對齊與有限比較計畫

> **供執行代理：** 依專案 SDD／TDD 規範逐切片執行；適用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`。下列 checkbox 只追蹤施工，不代表產品任務 schema。使用者確認分工並授權實作與測試；T1／T3 已完成工程驗證；v2 pilot 已通過，T4 依使用者指示縮為各一場，完整兩場已完成；匿名配對已鎖定並解盲，未呈現可辨整體增益；過程語意核對已完成，不能證明穩定品質增益。

**Goal:** 讓同一顧問以一份 Markdown 延續取得理解到交付 JD 的工作，公平比較只有指引與指引加 Plan 的最終效果。

**Architecture:** 保留既有 Plan 工具、保存及接續，更新內容用途與文案。Plan 與 Diff 是 Agent 的獨立元件；效果比較沿正式 HTTP 旅程及實際採用 JD，兩組使用相同既有 Diff 能力。

**Tech Stack:** 現有 Python／SQLAlchemy／PostgreSQL、LangGraph／Responses、React／SafeMarkdown／TanStack Query；版本沿現有 lockfile。

**Spec:** [架構元件分工](../architecture/system-boundaries.md#21-長任務的元件分工) → [INTPLAN 詳細契約 §10–11](../specs/2026-10-06-consultant-interview-planning-and-focus-design.md#11-工程變更範圍與驗證邊界)、[Accepted ADR0082](../adr/0082-consultant-jd-work-plan.md)。依 ADR0082 採用新用途；原 ADR0081 的八案結果不作新方案品質證據。

## 全域約束

- 獨立於[原筆記施工](2026-10-07-interview-plan-implementation-and-comparison.md)，不重置已完成任務；開始前核 branch／status，保留他人及既有 WIP，不自動 commit／push。
- 單一 Markdown、原 read／edit wire 與 V4A；正文／diff 各 16,000 字元、32 hunks，`null`／`""` 語意保留。無新任務表、migration、工具名稱或狀態解析器。
- Plan 與 Memory 共用的 V4A patch 是正文局部修改機制；本計畫只對齊其 Plan 用途與範例。獨立的變更檢視（Changes，下文保留舊稱 Diff 以對照工程沿革）不屬本計畫，不新增其提示、投影或接線，也不以先修改它作為施工或比較前提；文件稱呼不構成 tool／DB 更名工作。
- 原話／Memory／JD／指南各保留權責。完成短句不作依據；Plan 可保留已知未入稿及跨欄核對工作。
- 新輪固定資料；恢復用原 captured request，壓後 Plan 用原位置精確投影。取消不授採用；不固定多一次 planner 呼叫或背景 A Turn。
- 真 PG 沿 [API README](../../apps/api/README.md#測試與檢查) 的隔離 loopback `_test` DB；本計畫不自行啟動、清除既有資料或印出 key。
- 新付費比較只在新[協議](../experiments/product-validation/jd-work-plan-comparison-2026-10-07/protocol.md)的 manifest、材料、成本及有效授權界線完成核對後執行；不把原批剩餘額度當新批預算。

## Review Focus

1. 事實已知、尚未入稿遇上換題或壓縮，仍應留待編修工作；由 T1 範例與 T4 成品比較覆蓋。
2. 人工改稿後，Agent 能以既有目前稿／Diff 能力處理與安排不一致的地方；T4 只觀察整合情境，兩組固定相同能力，不驗收新的 Diff 功能。
3. 已保存舊 request 或恢復時 Plan 已變，仍沿原 request 與合法位置接續；由 T1 的既有 Plan context／projection 回歸覆蓋。
4. 部分完成、答不出、拒答、未探索與無 Plan 內容不能誤作全案完成；由 T1 內容審查、T3 空態、T4 行為案例覆蓋。
5. 員工模擬器只對一組額外披露、或暗中解鎖而 A 沒有新線索，不能誤歸因為 Plan 增益／未返回；由 T4 協議檢查及逐問披露核對覆蓋。

## T1：對齊 Plan 用途與可執行 patch 範例

**Files（既有檔案修改）**

- `apps/api/src/caliburn/agents/job_consultant/planning_instructions.py`：共同方法與 Plan 專屬用途分開。
- `apps/api/src/caliburn/transport/model_tools/interview_plans.py`：工具 description、V4A 範例及容量恢復文案。
- `apps/api/tests/unit/test_interview_plan_tools.py`、`test_role_prompt_contracts.py`：範例與實際 role 組裝。
- 回歸既有 `apps/api/tests/unit/test_interview_plan_projection.py`、`test_interview_plan_projection_boundaries.py` 與 `apps/api/tests/integration/test_interview_plan_context_binding.py`；不因本次用途對齊新增保存或恢復機制。

**Interfaces:** 保留 `FOCUS_INSTRUCTIONS`、`INTERVIEW_PLAN_INSTRUCTIONS`、`interview_plan_definitions() -> list[FunctionToolParam]`。不改工具參數、輸出與保存；共同方法兩組一致，Plan 專屬部分才提 read／edit／全文。

- [x] 建立目標內容與實際 patch 範例：盤點未知釐清後改為待入稿、目前焦點轉帶教；斷言保留收貨及尚未知的適用範圍原文，結果能以同一 read／edit roundtrip 取得。另保留原空來源建立、局部定位拒絕及容量測例。新範例以 `@@` 和 `*** End of File` 表示，不把觀察 diff 當輸入。
- [x] 執行下方窄測，記錄真正缺行為或格式的 Red；現有純文字能力已支持者直接記 baseline pass，不造無意義失敗。
- [x] 依 spec §11.1 修改兩處提示與例子；用有範圍的進度、精確未完命題及實際工具結果取代舊未知限定。新內容不須 runtime validator。
- [x] 重跑同組測試並靜態核對兩組提示組裝；回歸既有 Plan context／projection，確認舊 request 保留原能力／指令、恢復及壓後投影沿合法原位置。不要用 substring 斷言冒稱 Agent 真會回看或不漏問；PG 未配置而 skip 不能算恢復已驗。

```powershell
uv run --project apps/api --locked pytest apps/api/tests/unit/test_interview_plan_tools.py apps/api/tests/unit/test_role_prompt_contracts.py apps/api/tests/unit/test_interview_plan_body_edits.py apps/api/tests/contracts/test_interview_plan_contracts.py -q
uv run --project apps/api --locked pytest apps/api/tests/unit/test_interview_plan_projection.py apps/api/tests/unit/test_interview_plan_projection_boundaries.py -q
uv run --project apps/api --locked pytest apps/api/tests/integration/test_interview_plan_context_binding.py -m postgres -q
```

退出：工具範例可執行、wire 不變、無互斥內容指令。模型語意效果留 T4。

## T2：Changes 為獨立範圍，無施工項目

Plan 與 Changes 是 Agent 的獨立元件；本計畫不改 Changes 的提示、投影、讀取或恢復接線。保留編號以對照原計畫，沒有施工項目；T4 以兩組相同的既有能力觀察人工改稿整合情境。

## T3：同份唯讀 UI 改稱工作計畫

**Files:** `apps/web/src/features/interview/InterviewPlan.tsx`；受影響 `apps/web/src/app/InterviewPlan.test.tsx`、`apps/web/tests/e2e/interview-plan.spec.ts`。以局部搜尋定位舊 label 的其他測試，不改正式 route、queryKey 或 DTO。

**Interfaces:** `InterviewPlan({ jobFileId }: { jobFileId: string })`、`useInterviewPlan` 及 SafeMarkdown 不變；只對齊顯示文案及對應既有斷言。

- [x] 將標題、aria-label、載入／失敗／未建立／重試文案一致改為「工作計畫」。保留 `null`／空字串／不可用以及候選／上一採用版的分別；不加入勾選框、百分比或第二份展示正文。
- [x] 更新並執行現有元件測試，核 Markdown 子項仍直接呈現；純更名不新增只複製字串的測試。E2E 更新 locator，沿整合驗收時執行既有場景，不為改名另造旅程。

```powershell
pnpm --filter @caliburn/frontend test src/app/InterviewPlan.test.tsx
pnpm --filter @caliburn/frontend typecheck
```

退出：新名稱一致且既有行為保持。UI 結果不代替 Agent 效果。

## T4：公平比較準備、執行與文件交付

**Files:** 新[比較目錄](../experiments/product-validation/jd-work-plan-comparison-2026-10-07/)及其協議所列的 driver／manifest／資料／分析產物；不修改舊實驗原件。現行責任文件按 spec §11.3 隨實際進度回寫。

**Interfaces:** 使用正式 HTTP 建職務檔案、Turn、人工改稿與讀採用 JD；實驗限定的 Plan 開關只移除 Plan 能力與資料，保留共同顧問方法及相同既有 Diff 能力。完整輸入與採用成品、來源、Plan、native C／projection、usage 及盲評解盲關係由同批 manifest 連接。

- [x] 依新協議補 driver 的可見新線索、逐問披露判定、共同人工改稿事件及提前收束處理；先離線 replay 政策，證明未知／拒答不會披露答案、多題逐子問裁決、兩組遵循相同事件與披露規則。
- [x] 首版已凍結兩組共同指引／模型／材料及唯一差異，確認新 namespace／成本限制／pilot→主比較停止條件。先修工具或資料失敗，再比較效果；不得以缺失筆記的 run 冒充有效 Plan 組。
- [x] 依 v1 先導反例完成格式澄清與 v2 revision 核查，保留累計帳務；v2 有效 pilot 與獨立機制審查通過，批次原件沿既有 evidence。
- [x] 依使用者將範圍縮為各一場的指示完成兩場完整訪談與 Memory 收尾；保留原八場凍結協議、失敗及中止原件，中止場不列品質樣本。範圍變更、模型數字、成本與未觀察情境沿本任務 evidence。
- [x] 完成兩案正式 JD 匿名評閱與配對判斷，全部鎖定後解盲；有限比較未呈現可辨整體增益。
- [x] 核對兩場過程：語意忠實、有效返回、未入稿遺失、修正一致性、停止理由及負擔；列明未觀察情境，工程成功與成品增益分開判斷。
- [x] 完成 T1／T3 的獨立工程審查與受影響檢查，回寫設計、implementation、App README、verification 及索引；具體結果見[工程證據](evidence/jd-work-plan-2026-10-08.md)，原 ADR0081／舊試驗內容不改。
- [x] T4 比較 driver／材料完成，新增差異的獨立審查及必要離線政策驗證通過；結果見[複核紀錄](evidence/jd-work-plan-2026-10-08-review.md)，依使用者各一場的範圍完成上列品質及過程交付，不將原八場視為已執行。

退出：有可重現的工程與有限比較原件，明確交代是否改善、失敗原因及尚未驗情境；不以完成施工宣稱 JD 滿分。本次付費執行已依使用者縮減範圍結束；有限比較不證明穩定品質增益。

## 設計自查與目前交付

§10 的內容、時機、格式及控制界線映射到 T1／T3；Plan 恢復與壓後投影沿 T1 的既有回歸；效果與披露限制映射到 T4。T2 無施工項目，Changes 元件維持獨立範圍。Guide／Memory／存儲無語意變更，不複製成另一套任務系統。

T1／T3 已完成提示、可執行工具範例、唯讀 UI 文案及受影響驗證，結果集中在[2026-10-08 工程證據](evidence/jd-work-plan-2026-10-08.md)。v1 先導格式問題已澄清，v2 pilot 通過；依使用者範圍完成各一場，匿名配對已鎖定並解盲，未呈現可辨整體增益；過程語意核對已完成，有限比較不能證明穩定品質增益；有限比較判讀見[結果入口](../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v2/results.md)，實際批次狀態、機制核對與帳務沿既有 evidence，不在計畫另抄批次結果。工程成功與獨立審查不代表成品品質改善，不預填模型通過或沿用原八案結果。
