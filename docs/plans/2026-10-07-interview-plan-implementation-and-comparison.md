# 長訪談筆記實作與 P1／P2 真實模型比較

> 執行方式：superpowers:subagent-driven-development；root 整合跨切片接線，獨占檔案分工、TDD 與切片／全體審查。依本次明確授權連續執行，不重問計畫或付費確認。

**Goal:** 讓同一顧問能維持長任務的焦點與重要未完分析，完成保存／恢復與 UI 測試，直接比較只有指引與指引加筆記對最終正式 JD 的效果。

**Architecture:** 重用 V4A 與原執行保存。plan owner 保存候選、不可變完整效果與原結果；workflow 協調 scope／資格及完成交易。A 原能力分派、全文投影與按需工具，UI 只讀同份內容。

**Tech Stack:** 既有 Python／SQLAlchemy／Alembic／PostgreSQL、LangGraph／Responses SDK、React／TanStack Query 5.104.0、canonical schema generator。

**Spec:** [INTPLAN 唯一設計](../specs/2026-10-06-consultant-interview-planning-and-focus-design.md)，[ADR0081](../adr/0081-consultant-interview-focus-and-unresolved-plan.md)。

## 全域約束與授權

- 2026-10-07 使用者：「同意 開始實作 做完測試 並直接比較『只有指引』與『指引＋筆記』不用我授權 真實api key 可以直接用」。此授權適用本功能與合成材料的真模型比較；不輸出 key／merge／push／發布／清既有資料。
- 在既有 `consultant-jd-analysis` 工作樹施工，保留開始前所有未提交變更。這些已包含有效顧問方法與本題設計；不從 HEAD 另開遺失基準的 checkout。不將其他工作提交或改寫。
- 只記焦點／重要未知／線索，Memory／原話為已理解內容；正文 nullable 與空字串逐字保留。
- canonical schema 一次生成 Python／TS；模型不配置 scope／operation／revision／writer。
- 真 PG 只用 loopback `_test` DB 的隨機隔離 schema；真 API 用新合成職務檔案與專用 namespace／程序，不遷移或測試既有員工資料。
- 施測前凍結 manifest、模型／prompt／工具與材料。先有限 pilot 核 cost／流程，再完成代表性配對；所有結果及停止原因保存，不選最佳一組。
- 不自動 commit。每個切片記實際 Red／Green／review，測試環境壞掉或拼錯 import 不算業務 Red。

## Review Focus

1. 原來源 `None` 的無文字效果保留 `None`；故意清空保留 `""`。
2. 先成功操作的失 ACK／較早原操作重播回原結果但不倒退 head。
3. 原 captured 舊工具能力及 C／pending projection 精確位置，inactive 核帳不中斷。
4. 完成／取消競爭與 completed 重入不走 active-only preview，不改後續 Turn。
5. 終局當 render 停 candidate；失敗刷新不標成功，舊在途 GET 不冒充終局新讀取。

## T1：純編輯、工具與生成契約（plan_tools）

**Files:** `adapters/body_edits.py`、`body_matching.py`；Memory 原薄入口；`transport/model_tools/interview_plans.py`；`agents/job_consultant/tools.py`；tools canonical schemas；HTTP `interview-plan-view`／`consultant-turn` schema 與全部相依生成物；unit/contracts tests。

**Interfaces:** `apply_body_diff(body,diff,*,policy=DEFAULT,allow_blank_body=False)->str`、`describe_body_change(before,after)->str`。`InterviewPlanTools(workflow,writer)` prepare 保存完整 PlanEdit，execute 回原 result_text；`consultant_tool_definitions(interview_plans_enabled:bool=True)` 與 optional handler。read `{}`→`{plan}`，edit `{diff}`→updated＋actual diff／unchanged，禁止其他欄位；limits 沿 spec §5.2。

- [x] 寫可重現的空來源／空結果及 nullable no-op、Memory 非空回歸；執行目前核心證明新用途缺失。
- [x] 移共用純核心，Memory 薄相容入口；核唯一定位／全數成功／換行及完整實際 diff。
- [x] canonical schema 生成，工具 prepare／execute roundtrip、容量拒絕與原序列化結果測試。
- [x] 跑受影響 unit/contracts、generator check、import boundaries；記 Red／Green，靜態審查。

## T2：候選、原操作與採用／完成交易（plan_storage）

**Files:** `features/interview_plans/{models,persistence,service}.py`；新 migration 與 env ORM 登錄；interviews／executions metadata 公開查詢；`workflows/interview_plans.py`、`consultant_completion.py`；PG integration tests。

**Interfaces:** `PlanPosition(job_file_id,execution_id,revision_id)`；`PlanSnapshot(position,body)`；`PlanEdit(operation_id,position,diff,next_plan,result_text)`；`PlanEditResult(snapshot,result_text)`。`start_interview_plan(session,writer,InterviewReadScope)->PlanSnapshot` 同原 capture 交易；`read_adopted_plan(session,scope)->PlanSnapshot|None`；`InterviewPlanWorkflow.read_current(ExecutionScope)->PlanSnapshot|None`、`apply(writer,PlanEdit)->PlanEditResult`；`InterviewPlanReadWorkflow.read_adopted(job_file_id)->PlanSnapshot|None`。feature `read_base/read_current`、`validate_final`；complete 加 `plan_position:PlanPosition|None=None`，v2 caller 必填。

- [x] 先用真 PG 證明原 start/base、nullable 空值、原操作／過期與資格缺行為。
- [x] 兩表／FK／CHECK／cascade／immutable migration；same-session service／typed owner 交集與 LIMIT1。
- [x] 完成交易加原 final plan 校驗；核未知確認／取消競爭／completed replay／失效 writer／整檔刪除。
- [x] 跑受影響 postgres integration、migration upgrade與同scope查詢；核不讀 foreign owner ORM，記證據及審查。

## T3：原能力、固定新輪、精確換窗與完成恢復（root）

**Files:** A `context_binding.py`、新 `interview_plan_context.py`、`runner.py`／原方法提示；共用 `context_compaction.py` 窄 native exact reader；`bootstrap.py` 組裝；context／SDK fake／PG journey tests。

**Interfaces:** v1 binding 原 shape，v2 加 required plan base；TurnContext nullable PlanPosition。A builder `{role:user,content:JSON(data_kind,plan)}`。同 capture 交易呼叫 T2 start，新輪 history→plan→app_data→raw。私有 graph input_binding／projection、thread／exact C、callback 委派順序沿 spec §6.9；不增通用 State 或替換原 request。runner 依原能力建 T1 handler及wrapper，完整final後讀同Turnhead；completed 跨行程核原final/exchange/binding/head後回原結果。

- [x] 新輪全文以 Red 開始；另驗 fake SDK／saved checkpoint 的舊cap不retrofit、pending binding及inactive callback，原型別與capture缺失反例有 Red／Green。
- [x] 接 T1/T2、原binding版本分派與完整 raw checkpoint；補原cap／缺root、start已提交但capture不可靠裁決。
- [x] 精確 C／plan item graph；核 projection／parent中斷與原 saved request 恢復、取消核帳、完整window重新准入。
- [x] P1共同行為與P2工具指引分開常數，隔離fixture可禁plan toolkit而使用同共同行為；production無新使用者模式開關。
- [x] 測 complete ACK／跨行程結果、下一Turn不倒退；受影響unit/SDKfake/PG測試及審查。

## T4：同份 HTTP preview 與唯讀 UI（plan_ui）

**Files:** HTTP `interview_plans.py`、`consultant_turns.py`；`workflows/consultant_status.py`；Web `interview-plan-api.ts`、`use-interview-plan.ts`、`InterviewPlan.tsx`、`InterviewPane.tsx`、validation；局部fixtures／HTTP／React tests。

**Interfaces:** GET `/api/job-files/{file}/interview-plan`→InterviewPlanView；ConsultantTurn requirednullable plan_preview，物件內 plan nullable。state read workflow由rootbootstrap接。queryFnconsumeAbortSignal，同file queryKey／cache保存正文；verifiedactive/paused才preview，terminal當render停；exactcancel(default revert/no silent)→invalidate:none→query(options, stale0)，in-flight共用且schema/file/currentterminal成功才confirmed，失敗retry。

- [x] 寫 nullable／空、terminal render／刷新錯誤／舊在途 promise與換檔反例，先跑Red。
- [x] 接正式GET／activepaused preview；null／空／不可用呈現，同份SafeMarkdown唯讀與折疊。
- [x] 跑HTTP／React受影響tests、typecheck/lint/build及必要瀏覽器旅程；不新增poller／SSE／正文副本。

## T5：整體檢查、真實 P1／P2 與文件交付（root＋獨立審查）

**Files:** 本計畫 evidence；`docs/experiments/product-validation/interview-plan-comparison-2026-10-07/` protocol／manifest／HTTP driver／guard／全結果／正式JD／語意對照；現行責任及狀態入口。

- [x] 先跑影響面unit/contracts/PG/SDKfake/Web與generator／ruff/mypy/TS/lint/build；新程式整體spec＋code quality審查，修load-bearing findings；分次範圍與最後schema修正後結果沿 [T5](evidence/interview-plan-2026-10-07/t5-validation.md)。
- [x] 凍結可見prefix/JD來源/Memory快照，P2從可見材料自建筆記；人工條件回答、HTTP-only旅程。八案 160 個 accepted source ID/body 及 144 個已送後續裁決接線核對；課務 r1 P1 Turn 10 政策越界與裁決代理營運 metadata 曝露保留，不宣稱全場完全公平或全 context 盲。
- [x] 兩種工作輪廓各配對重複兩次，八案各 20 Turn completed＋共同收束。四個 r2 實際 A within-Work C 的 fullC／同位置 projection→nextA 已核；公開 item 重算與 opaque 原 hash witness 界線分列。局部未知、換題返回及語意變形反例已核，保存機制與取證效果分開。
- [x] 正式保存 JD／來源依凍結 rubric 與三指南完成四組匿名評閱，全部鎖定後解盲；有效返回、必要／不必要追問的具體反例、角色分項 usage／費用及各次停止原因沿[完整結果](../experiments/product-validation/interview-plan-comparison-2026-10-07/results.md)保留，不宣稱問句已窮舉評分。
- [x] P2 相對 P1 分機制、最後 JD 及負擔回報，相關責任文件與入口已回寫。結果為兩組 P2 較好、一組 P1 較好、一組各有得失；八案仍有重要缺口／錯誤，品質效果門檻未證，測完不等於高品質完整 JD 驗收通過。獨立選問優先順序候選仍另行施測，不混入本核心比較。

T5 已完成工程檢查、核心比較、盲評、機制核對及文件交付；§7 的筆記穩定增益與高品質完整 JD 驗收尚未成立。全 API／其後窄修的命令與範圍沿 [T5 驗證](evidence/interview-plan-2026-10-07/t5-validation.md)，不重跑或合算舊測試數。

## 證據／工程裁決

- 開始前 branch／status 已核；本功能尚無程式改動。使用者與其他任務的工作保留。
- 授權已涵蓋實作／真API比較；writing-plans 的再次 human handoff 不另成產品審批，沿本次明確指示直接施工。
- 各切片 Red／Green、實際命令、成本與review隨執行補本欄；未驗證不勾完成。
