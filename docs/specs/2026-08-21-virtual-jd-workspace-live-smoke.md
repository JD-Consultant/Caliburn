# Virtual JD workspace live smoke evidence

- 日期：2026-08-22
- 狀態：**partial；exact profile 仍有未解 blocker，不是 live pass**
- 範圍：current Deep Agents virtual JD workspace、deterministic candidate check／repair、pending-only publication；不接 RAG／Reference、不做能力級別／A、不啟用 auto mode 或正式 eval。

## 1. Provider schema 修正

第一次 exact provider smoke 到達 OpenAI 後，strict response schema 因 `OutputEvidenceReference.occurrence` 是 optional 而被 `invalid_json_schema` 拒絕。這是 provider wire 與 OpenAI strict required-field 規則的契約錯位，不是模型品質結果。

最小修正如下：

- provider-facing `occurrence` 改為 required strict integer；唯一 quote 填 `0`，重複 quote 填 1-based occurrence；
- `AnalysisBasisTable` 將 provider sentinel `0` 映射回 workspace `WorkspaceEvidenceReference.occurrence=None`，正整數原樣保留；
- agent prompt 明示 sentinel 規則；
- fixtures、schema contract、mapper 與 runtime regression 一併更新。

這保留模型不知道 source UUID／offset 的邊界，也沒有新增 provider-specific abstraction。focused API regression 已驗證 schema requiredness、sentinel mapping 與既有 evidence resolver；Web integration coverage 也維持綠燈。

## 2. Exact profile live result

runner 直接以 `apps/api/.env` 的 dotenv values 載入 owner key/base URL，並在 runner 內固定 disposable PostgreSQL：

```text
postgresql+asyncpg://postgres:password@localhost:5432/caliburn_reviewed
postgresql://postgres:password@localhost:5432/caliburn_reviewed
```

Profile 固定為：

- requested model：`openai/gpt-5.6-luna`
- provider：`OpenAI`
- fallback：disabled
- reasoning：`max`
- existing model-call policy：8 calls、2 lookup waves
- total Tool-call policy：48 calls（由 12／24 的診斷結果經 owner 核准後調整；這是保險絲，不是目標）
- model-facing Tools：`ls`、`read_file`、`grep`、`write_file`、`edit_file`、`delete`、`check_candidate_document`

schema 修正後的第一輪 smoke 已實際走到 GPT-5.6 Luna，並確認 exact seven-Tool surface 已 bound/exposed；實際 Tool calls 只觀察到 `ls` 與 `read_file`。Luna 反覆讀取這兩個 lookup，跨過既定兩波 lookup limit，production middleware 回傳 `LookupWaveLimitExceeded` 並 fail closed。

後續以 TDD 確認一個窄導覽契約缺口：Deep Agents 已在 Skill metadata catalog 列出每個精確 `/skills/<id>/SKILL.md`，但本輪 context 只列 `/sources` root，沒有告訴模型 HumanMessage 對應的 model-safe `source-###` 路徑；Evidence 又必須填 source handle。最小修正從同一份既有 `WorkspaceCatalog` 取出 handle，將 `/sources/current/source-###.txt` 寫入 `<workspace_index>.current_source_path`；沒有增加 DB query、Tool、model call、lookup wave、狀態或 mapping。

owner 核准的診斷 smoke 讓 runner 同時保存不含內容的 model-safe call path。第一輪結果如下：

1. 第一個 model Tool wave 一次提出並成功執行九個呼叫：精確讀取本輪 `/sources/current/source-002.txt`、列出 candidate root，並各讀一次 `work-discovery`、`task-boundary`、`duty-grouping`、`output`、`performance-indicator`、`knowledge`、`skill` 七份 `SKILL.md`；沒有重複 Skill read，也沒有讀取 `story-interview` 或 `completion-red-team`。
2. 第二個 model Tool wave 合法提出五個 candidate 導覽呼叫：讀 `header.json`、讀 `review-groups.json`，並列出 `duties`、`tasks`、`opks`。此時預計總數為 14，超過全域 `run_limit=12`；本版 LangChain middleware 在 model response 後先計整批並以 `exit_behavior="error"` 丟出 `ToolCallLimitExceededError`，所以第二批五個呼叫完全沒有執行。
3. 兩批都沒有再消耗 external lookup wave；source path 修正已生效。失敗點仍在第一次 candidate check／repair 之前，因此 14 也不是完整合法流程的最高需求。

依此 trace，先以 TDD 把全域 Tool 保險絲由 12 調到 24；24 仍在合法路徑中觸發上限。owner 再核准 48，並補上 `/approved/index.json`／`/pending/index.json` 導覽入口。同時以紅／綠 regression 修正 wave 分類：讀 `/skills` 是方法 progressive disclosure，不是外部資料查詢；只有 `/sources`、`/approved`、`/pending` 的 `ls`／`read_file`／`grep` 消耗 external-data lookup wave，真實第三波仍會拒絕。

第一個 48-call diagnostic 另暴露 smoke harness 自己的契約錯位：runner 把「先 check、修復 injected invalid O」追加到帶同一 `employee_source_id` 的 `HumanMessage`，但 production `ConsultantContextMiddleware` 每次推論都會按 Store authority 把該訊息恢復成真正員工原話。這是正確的 prompt-injection 防護，也代表模型從未收到那段 test-only 操作指令；該輪不能用來判定 Context 或 model-tier。runner 因此改成不注入 invalid candidate、不追加隱藏指令，只測代表性的真產品要求：「把員工已明確說出的工作整理成待審候選」。

修正 runner 後只重跑一次 Luna，結果仍沒有碰到 48-call 保險絲：

1. 第一個 model step 平行讀 exact current source、`/approved/index.json` 與七份實際選用的 Skill，共九個成功 Tool calls。
2. 第二個 model step 列 candidate root，讀 approved header／Duty／Task 與 `/pending/index.json`，共五個成功 Tool calls。
3. 第三個 model step 讀 candidate header／Duty／Task／review-groups，共四個成功 Tool calls。至此合計 18，仍遠低於 48。
4. 模型沒有執行 `write_file`、`edit_file` 或 `check_candidate_document`；下一步又要求列 `/approved`、`/pending` 與 candidate duties／tasks。前兩項構成第三個 external-data lookup wave，因此四個呼叫整批在執行前 fail closed。
5. disposable document 由 `finally` 精確清除；`consultant_documents`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`store` 相關筆數全部回到零。failure path 目前沒有把 payload-free attempt receipt 放進 runner report，因此本輪無法聲稱精確 provider cost／cache 命中；補齊前只能以設定上限與 Tool trace 判讀，不能捏造金額。

零成本 contract audit 找到一個更具體、可重現的介面缺口：`/approved/index.json` 只列已存在的 canonical resources；本 fixture 原本沒有 OPKS，因此 index、approved 與 candidate 都沒有任何 O／P／K／S 檔案範例。九個 Skill 教的是職務分析方法，不是 VFS wire format；`write_file` 的現行 Tool description 也只說「建立一個新 candidate resource」，沒有 path pattern、required fields、handle 或 Evidence JSON shape。模型能讀懂既有 Duty／Task 檔，卻無從可靠得知如何建立第一個 OPKS；它繼續找範例與這個缺口一致。相同問題也會出現在空白文件的第一個 Duty／Task，不應靠更強模型猜 contract。

因此較高 Tool 上限沒有帶來效果；繼續增加 Tool、lookup 或 model-call budget只會擴大 token、延遲與 provider 成本，不能視為品質修正。這份 trace 也不支持刪除 K／S、合併 O／P／K／S Skill、加 keyword selector／第二個 agent，或先換更昂貴模型。

官方資料支持先修 Agent–Tool contract：OpenAI 最新 model guidance 要求 Tool description 簡潔而精確，把 tool-specific 的用途、輸入、side effect 與常見錯誤放在 Tool description；保留能修正已量測缺口的少量 example，並只在結果仍通過品質門檻時才把較少 calls／tokens 算成改善。Anthropic 同樣要求把新人會缺少的隱含知識——特殊格式、術語與資源關係——明確寫進 Tool description/spec，並以 strict model enforcement。這支持提供**小而精確的 candidate resource creation contract**，不支持增加查詢預算或要求模型猜 internal Pydantic shape。[OpenAI latest model guide](https://developers.openai.com/api/docs/guides/latest-model) · [Anthropic — Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) · [Deep Agents Skills](https://docs.langchain.com/oss/python/deepagents/skills) · [LangChain Tool call limit](https://docs.langchain.com/oss/python/langchain/middleware/built-in#tool-call-limit)

owner 核准後，依上述裁決只修改既有 framework `write_file` description：加入可直接由真 Tool 執行、再由真 candidate parser 還原的 Duty／Task／Output 三筆 JSONL 建立範例，並列出 P／K／S path-kind 對應。candidate Evidence 的唯一 quote 使用 `null`，final structured output 才使用 `0` sentinel；沒有增加 Tool、root、model step、schema endpoint、agent 或 authority store。TDD 先看到範例集合為空而失敗，再用同一測試實際建立並解析相互連結的 Duty、Task、Output；focused gate 更新為 146 passed／6 skipped。

依約只再執行一次完全相同 Luna profile。creation contract 已跨過原 blocker，但整輪仍不是 live pass：

1. 前六個 model steps 共完成 17 個安全讀取／列目錄呼叫，包含 current source、approved/candidate resources，以及 `work-discovery`、`task-boundary`、`duty-grouping`、`output`、`completion-red-team` 五份按需 Skill；沒有第三波 external-data lookup，也沒有碰 48 Tool 上限。
2. 第七個 model step 成功 `edit_file` 一個既有 Task，並 `write_file` 兩個新 Task 與第一個 Output；這直接證明 compact creation contract 解決了 first-resource bootstrap，而不是只讓 deterministic fixture 通過。
3. 第八個 model step 發出 `check_candidate_document`。其後 agent 還需要一次 model call 產生 final structured response；LangChain `ModelCallLimitMiddleware` 在第九次呼叫前依既有 run limit 8 fail closed，錯誤為 `ModelCallLimitExceededError`。安全 callback 只會在下一次 model start 收集上一個 Tool result，所以本報告不能宣稱 check 成功，也沒有 pending publication 或員工可見最終結果。
4. 八次 payload-free receipt 合計 input 73,529、output 6,129、total 79,658 tokens；cache read 58,079、cache write 15,426 tokens，provider cost 合計 **US$0.01237768**。這表示 prompt caching 已實際工作，但它降低重複輸入成本，不能替代第九個 finalization step。
5. Tool trace 共 22 個 model-issued calls，仍低於 48。disposable document 由 `finally` 精確清除；`consultant_documents`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`store` 全部由 0 回到 0。

因此目前唯一已量測 blocker 從「模型不知道如何建立第一筆 candidate resource」前移成「完整候選編輯後沒有預留 finalization model step」。依 owner 的停止條件，本輪不再重跑、不自行把 8 調高、不換模型，也不加入 multi-agent。下一個決策應比較：最小提高 model-call 上限，或減少不必要的 approved/candidate 重複閱讀與 Skill 分波；先比較員工可見完成率，再看成本、延遲與複雜度，不能只追求較少 calls。

### 2.1 ADR 0065 校準後的唯一一次 exact-profile smoke

owner 後續核准 [ADR 0065](../adr/0065-interactive-consultant-finalization-and-token-budget.md)：互動 policy revision 2 將 model-call ceiling 由 8 校準為 11、累計 raw-token ceiling 由既有 32,000 校準為 160,000；24k 單次 context、兩波 external-data lookup、48 Tool calls、US$2 cost、180 秒 elapsed 與 retry 均未放寬。兩個新數字仍是單一員工回合的 fail-closed 保險絲，不是固定執行量。

依約只執行一次新的 `openai/gpt-5.6-luna`／OpenAI only／fallback disabled／`reasoning=max` smoke。resolved execution 確認 policy revision 2、11 model calls、160,000 raw tokens 與 exact seven-Tool surface；但 run 在第四個 model step 結束，沒有進入 candidate mutation／check：

1. 前三步完成 current source、approved/candidate projection 與八份按需 Skill 的安全讀取；第四步沒有 Tool call。
2. 第四張 receipt 的 `output_tokens=4,096`，正好等於 profile 的 `max_tokens=4,096`，`finish_reason=length`；LangChain 隨後因 provider-native strict final 無法完成解析而回 `StructuredOutputValidationError`／安全分類 `model_error`。
3. 四張 receipt 合計 input 35,003、output 6,444、total 41,447 tokens；cache read 21,652、cache write 13,339，provider cost **US$0.01150299**，model latency 合計 54,942 ms。runner 當時的安全摘要未投影既有 `reasoning_tokens` 欄位，且 disposable state 已依約刪除，因此不得補猜精確 reasoning 數字。
4. cleanup 後 `consultant_documents`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`store` 均回到 0。依單次付費限制沒有重跑。

根因層次與 11-call／160k 校準不同。OpenAI API 把 `max_output_tokens` 定義為可見輸出與 reasoning 共用的上限；OpenRouter 對支援 effort 的模型說明 `max／xhigh` 約配置 `max_tokens` 的 95% 作 reasoning budget，並明示必須另留 final response 空間，reasoning token 也按 output token 計費。這與本輪「精確 4,096＋`length`＋strict output parse failure」一致，也與 repo 先前 `max／4,096`、`max／16,384` 皆無可用 final，而 `medium／8,192` 成功完成 structured final 的紀錄一致。故目前不支持只把 4,096 加大後繼續讓每輪訪談都用 `max`；那會主要擴張推理成本，仍不保證留下足夠 final JSON 空間。

按 GPT-5.6 Luna 官方單價還原本次 provider cost：cache read 約 US$0.00043304、cache write 約 US$0.00333475、其他 input 約 US$0.00000240、output／reasoning 約 US$0.00773280；output／reasoning 約占整輪 **67.2%**。這表示 stable-prefix prompt caching 已在工作，但此樣本的主要成本槓桿已轉為 reasoning effort／output，而不是再增加 cache abstraction。

若把這個**失敗且沒有候選產出**的複雜回合純線性換算，50 輪約 US$0.58、100 輪約 US$1.15；這不是成功整份 JD 的報價，因成功 run 可能需要更多 model steps，短回合則可更早結束。產品決策必須看每份文件所有 durable receipts 的加總、完成率與失敗後浪費，不能只看單輪上限或單次便宜金額。

截至這一輪紀錄，11／160k deterministic policy 已通過 focused gates，但 exact max-profile live 仍不是 pass。owner 隨後因專業顧問品質疑慮，另核准一次不同 profile 的 `xhigh／32,000` 試跑；結果見下一節。這個後續授權不改寫 ADR 0065 對前一輪「相同 profile 不連續重跑」的歷史限制。

來源：[OpenAI GPT-5.6 Luna model／pricing](https://developers.openai.com/api/docs/models/gpt-5.6-luna) · [OpenAI Responses `max_output_tokens`](https://developers.openai.com/api/reference/resources/responses/methods/create) · [OpenAI GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model) · [OpenRouter reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens) · [OpenRouter usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)

### 2.2 Owner 核准的 `xhigh／32,000` profile 試跑

owner 明確要求先試較高 reasoning 品質後，執行一次 `openai/gpt-5.6-luna`／OpenAI only／fallback disabled／`reasoning=xhigh`／`max_tokens=32,000` 的相同產品情境。測試前發現 Caliburn profile contract 雖支援 `max`，卻漏列官方與 provider 均支援的 `xhigh`；新增的真 boundary test 先因 Pydantic literal validation 紅燈，再以最小修改把 `xhigh` 加進 `ConsultantModelProfile`／`ReasoningParameters` 並確認 OpenRouter binding 原樣轉送。production 預設 model／effort／output cap 均未改。

本輪沒有重現 `max` 的 output exhaustion：

1. 模型完成 11 次 primary calls，另有一次 LangChain summarization call；最後一張 primary receipt 為 `finish_reason=stop`，沒有 `length`，也沒有 `StructuredOutputValidationError`。
2. Tool trace 顯示模型修改既有 Task、新增兩個 Task、新增一個 O 與兩個 P，第一次 check 為 candidate revision 1；後續再修正既有 Task並成功 check revision 2。這證明 `xhigh／32,000` 能走過候選編輯與 deterministic candidate check，不只是產生文字。
3. 十二張 receipt 合計 input **122,703**、output **11,872**、total **134,575** tokens；其中 provider 回報 reasoning **8,472**，其餘可見／結構／Tool-call output 合計 3,400。cache read 95,314、cache write 27,353；provider cost **US$0.02299813**，model latency 合計 **125,548 ms**。同成本純線性換算 50 輪約 US$1.15、100 輪約 US$2.30；這仍不是完整 JD 報價。
4. run 最後在 semantic commit 前由 `ConsultantVerificationError` fail closed；不是 `ConsultantRunBudgetExceeded`，134,575 低於 160,000，receipt 時間亦低於 180 秒。正式 JD 未改、沒有 pending review bundle，因此本輪仍不是 live pass。
5. 安全 runner 當時只保存本機 verifier 的錯誤型別，不保存訊息，所以不能事後宣稱是哪一條 deterministic gate。可觀察到的具體交互是：summarization 後模型再次讀取五個先前已完整載入的 Skill，one-load `PackageSkillBackend` 依既定規則回 `already loaded` error，只有尚未讀取的 `completion-red-team` 成功。這是 summarization／context clearing 與 progressive Skill disclosure 之間的強烈衝突訊號，但在無 exact verifier message 或 deterministic reproduction 前，不把它寫成已證實根因。
6. disposable document 由 `finally` 精確刪除，`consultant_documents`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`store` 全部由 0 回到 0。

本輪支持把 `xhigh` 保留為正式候選：相較 `max`，它留下完整 final response 空間，也實際完成候選操作；但它尚未證明整輪可提交，且複雜回合已使用 84.1% raw-token ceiling、約 125.5 秒模型時間。下一步不是再提高 output／call ceiling或付費重跑，而是先用 deterministic test 定位 final verifier branch，並驗證摘要後已載入 Skill 的方法內容如何合法延續。完成前不把 `xhigh` 改成 production 預設。

runner 的安全摘要不輸出 key、headers、prompt、員工完整 payload 或 Tool payload。每次失敗都在 `finally` 只刪本輪 document；controller evidence 顯示 disposable document 已刪除，相關 persistence counts 回到零。

## 3. Reproduction commands

在同一 worktree、API dependency 已就緒且 local PostgreSQL `caliburn_reviewed` 可用時：

```powershell
cd S:\caliburn\.worktrees\langgraph-consultant-runtime\apps\api
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
$env:PYTHONPATH='S:\caliburn\.worktrees\langgraph-consultant-runtime\apps\api'
uv run python ..\..\.superpowers\sdd\2026-08-21-deep-agents-virtual-jd-workspace-plan\task-8-live-smoke.py
```

runner 直接讀取 `S:\caliburn\apps\api\.env`，不把 ignored env 複製到 worktree；DB/profile 的固定值由 runner 控制。live output 只接受 `passed` 或安全 provider/runtime failure；歷史八-call run 應解讀為 finalization model-call blocker，ADR 0065 後的唯一新 run 則是獨立的 per-call output／reasoning budget blocker；兩者都不是 live pass。

## 4. Deterministic browser authority review

browser QA 是另一個 local fixture evidence，不是上述 stochastic provider smoke 的替代品。controller 使用 plan-local ignored `task-8-browser-fixture.py` 建立一份 pending review document，驗證下列 employee-visible semantic decisions：

- accept job title；
- edit-and-accept work description；
- reject Duty with a reason；
- defer Task；
- leave one O pending。

reload 後各 decision status 保留；API snapshot 顯示 approved 只含員工接受的 job title／work description，單一 O 仍 pending，Duty／Task 仍為原核准內容，沒有其他 O/P/K/S 被暗中寫入。畫面沒有 `/candidate/`、`write_file`、`edit_file` 或 `check_candidate_document`。fixture document 已精確刪除，local servers 已停止。

這證明的是 deterministic employee authority／semantic review surface；它不證明 exact provider live run 已通過。

## 5. Relevant gates

```text
cd apps/api
uv run pytest tests/test_consultant_model_output.py tests/test_consultant_run_service.py tests/test_consultant_workspace_resources.py tests/test_consultant_candidate_loop.py -q

# workspace／creation-contract focused regression
uv run pytest tests/test_consultant_context.py tests/test_consultant_run_service.py tests/test_consultant_agent_and_skills.py tests/test_consultant_workspace_tools.py tests/test_consultant_workspace_resources.py tests/test_consultant_workspace_backend.py tests/test_consultant_candidate_publication.py tests/test_consultant_candidate_loop.py tests/test_consultant_model_output.py tests/test_consultant_model_runtime.py tests/test_consultant_task6_contract.py -q

cd apps/web
npm run test
npx tsc --noEmit
npm run lint
```

所有 PostgreSQL gate 都必須明確設定 disposable `TEST_DATABASE_URL`，且 cleanup 後查核 `consultant_documents`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`store`；未設定 DB 的 skipped tests 不可被報成 PostgreSQL pass。
