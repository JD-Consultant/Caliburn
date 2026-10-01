# 實作規劃與交付審查紀錄

- 日期：2026-09-29 起；範圍：本計畫、實作文件及後續核心交付審查；各階段按下列章節區分。
- **§1–3 是施工授權前的歷史規劃審查**：當時產品／provider／PostgreSQL 測試全部未執行。該階段 PASS 只適用文件檢查，不覆蓋後續施工；目前進度見[任務表](tasks.md)，Goal 整理見 §4，施工後的有界跨層審查見 §5。

## 1. 本次審查修正

| 發現 | 修正與理由 |
|---|---|
| 新目標 `apps/api`／`apps/web` 與舊退役路由易被混讀 | AGENTS／register／入口明確「重新使用路徑，不接回舊架構」；ADR0077 保持現行，T18 才正式切換 |
| SDD 容易再複製 requirements／design／tasks 三份產品規格 | 原架構唯一描述效果，實作文件描述機制，task 直接引用；schema 生成來源再管 wire |
| 把框架 checkpoint 當成所有業務成功 | E01–E15 分別落任務；原 R 保存、候選提交、Graph 採用及正式完成分開 |
| B 私有 subgraph 每次呼叫可能意外換 namespace | T06／T10 明驗同批回交保留歷史；推薦明確角色 thread，由 Parent 轉譯，不複製 private state |
| title 正規化可能暗改已定精確選擇語意 | 上位驗收修成「既定 title 精確比較接線」，只校正模糊敘述，未增加強制 read／參照 |
| 規劃只列功能，未包含最後可交付流程 | 加入 PDF、公開中間訊息、條件撤回、safe startup／cutover；V25 真實 ROI 與技術 gate 分開 |
| 一個生成器被誤寫成同時產 Python／TS | 核對官方支援範圍，改為 datamodel-code-generator 與 json-schema-to-typescript 各司其職、同讀唯一 schema；不自造生成器 |
| 只在後期做 provider gate，可能太晚發現協定不相容 | T06 備少量全合成 preflight；另有當次外送授權才提前執行，T16 完整驗收仍保留 |
| 容量檢查可能被理解為自己估 opaque tokens | 明列官方 input token count 機制及其外送、失敗與計量責任，T06／T16 驗所選模型；不把 API 文件當成帳戶已通過 |

## 2. 不應誤稱已解決的項目

- 鎖定套件組合、官方 parser 的可重用範圍、原生 item 序列化、strict schema 真接受，仍須 T01／T05／T06／T16 實際證據。
- 新工作 thread／有效歷史基底、業務與 checkpointer 的中斷接縫必須通過 T12，不因文件選定就宣稱可恢復。
- B 輪前門檻、呼叫／重試上限有明示校準初值；費用／時間依當次外送 manifest，不預設無限或已獲授權。
- V4A 唯一模糊匹配只能減少定位歧義，不能證明模型的語意修改正確。工具與品質 eval 各自驗。
- 新程式資料夾與命令目前尚未建立；無產品程式、依賴、schema、資料刪除、付費請求或新提交。

## 3. 文件檢查

| 實際檢查 | 結果與邊界 |
|---|---|
| 文件範圍與連結 | PASS：11 份新文件及 7 份責任／入口修改；182 個本機連結與錨點可解析。current-decisions／docs README 僅查本次相關入口，不冒稱審完全部歷史 |
| Markdown／空白 | PASS：範圍內 fences 成對、無行尾空白；`git diff --check` 通過。沒有新增 JSON schema 示例，正式 shape 留唯一契約來源，未因此執行 codegen |
| 任務依賴 | PASS：T01–T18、27 條前置依賴無循環，圖與任務 metadata 一致；各項具契約、完成條件與非目標，全部仍未勾選 |
| 驗收追溯 | PASS：V01–V28、E01–E15、JDT-01–09 全部有任務對照。這是 52 項覆蓋的文件檢查，沒有執行這 52 項產品測試 |
| 圖面 | PASS：兩張新圖以 Mermaid 11.17.2、隔離 headless Chrome 實際渲染；檢視 10 個程式責任節點、18 個任務節點，標籤與箭頭可讀，未裁切。第一輪 sandbox 啟動遭 EPERM，經工具授權的隔離重跑成功，未使用使用者瀏覽器設定 |
| 權責與限制 | 人工／AI 共用領域規則；native items 不改成文字摘要；Memory 無逐引用核對；JD 保留兩種核對基準；新命名／路徑不復活退役接線；相容性與品質風險保留為實測 gate |
| 工作範圍 | 只有 Markdown／AGENTS 路由變更；未修改產品程式、schema、lock、DB、啟動入口；未發付費模型、刪資料、commit、push 或 merge |

本次未發現需要 Owner 重新裁決產品語意的阻塞；**不承諾計畫沒有任何實作風險**。下一步是 T01 的工具鏈／相容性與可測邊界，不能越過 gate 一次建完全部底層。工程測試發現反例時，先依上位契約修正相應機制；只有必須改產品效果時才回到決策討論。

## 4. Goal 分層整理與覆蓋審查

日期：2026-09-29；Owner 要求整理長 Goal 並提供短 `/goal` prompt，不減少既定工作、不重置 T01。本次只維護文件，沒有替換執行中的 Goal。原長 Goal 是本次 Owner 授權的來源紀錄；其分節要求按以下責任歸屬維護，不另複製一份完整 prompt 作第二套規範。

| 原 Goal 要求 | 維護位置及保留界線 |
|---|---|
| §一 產品目的／成果 | [計畫 §1／5](README.md)、[產品概念](../../product-concept.md)：員工訪談即可逐步形成專業、完整、高訊號 JD，不以人工代寫補救為 gate |
| §二 正式依據／狀態 | [計畫入口](README.md)、[AGENTS](../../../AGENTS.md)、[目前決策](../../current-decisions.md)：區分現行、目標、候選、歷史；不只讀摘要施工 |
| §三 範圍／取捨 | 計畫 §1／3、T01–T18：重建不遷移底稿、必要診斷可補、不造第二套平台；精確切換不等於刪舊資料 |
| §四 研究／選型 | [開發規範 §1／2／5](../../implementation/development-standard.md)、[選型](../../implementation/technology-decisions.md)：官方／原碼／多方做法／有限驗證，選受支援相容方案後鎖定；可研究改良而非永久鎖死 |
| §四之一 分析／Prompt／Tool／Context | 開發規範 §7、三份分析指南與相應工具責任契約、T14／T16／T17：分責、按需、型號契約、基準／保留例及真模型共同驗收 |
| §五 SDD／TDD | 開發規範 §2–4：有效 Red、Green、Refactor、整合及小切片；不得刪測例降低標準 |
| §六 程式／命名 | [程式組織](../../implementation/code-organization.md)、[契約策略](../../contract-strategy.md)：角色／共用執行／流程／領域／UI 分責、唯一 schema、不建空泛抽象 |
| §七 核心邊界 | [架構路由](../../target-architecture-map.md)、[驗證對照](../../implementation/verification-plan.md)與 T02–T12／T15：來源資格、快照、引用、候選、原生接續、短交易、取消／恢復各驗，不新抄狀態機 |
| §八 真 API／憑證／費用 | 計畫 §3：直連合成、有界自主測試、秘密保護、禁止任意私人外送；明顯高額擴張仍提問 |
| §九 驗證／交付 | 計畫 §5、驗證對照、[介面交付](../../implementation/interface-and-delivery.md)：真 PG／原生 API／故障／UI／長訪談／品質／可重現啟停，不以 mock 或 Dockerfile 代替 |
| §十 文件／問題與報告 | [架構文件規範](../../architecture-discussion-standard.md)、開發規範 §6／8、計畫 §4／5：單一責任、圖實際渲染、問題取捨可追溯、報告不虛構 ROI |
| §十一 Git | 開發規範 §9：不用 codex 前綴、Conventional Commits、本地授權、精確 staged；不 push／merge／PR／tag／外部部署 |
| §十二 自主／提問 | AGENTS、開發規範 §10、計畫 §3／4：效果等價細節自主，重大語意／安全／不可逆／費用衝突提問；不阻塞無關工作 |
| §十三 長任務 | 開發規範 §10、任務 evidence：驗實況、保留下一步、重用有效證據，不每輪全讀歷史、不另建進度權威 |
| §十四 完成／交付回報 | 計畫 §5 保留全部 12 項退出條件及回報要求；任務表依實測勾選，不能把本次文件完成當產品完成 |
| 後續補充 | 計畫 §1：API／Web 不強制命名；可依研究採更好實現，但不能改掉已確認概念與保證 |

修正了有效入口的「尚未施工」、舊 `.env` 全面禁止、T06 重複請示授權及前端 package 舊名。歷史 §1–3 保留當時狀態，未重寫 ADR0077；T01 實測失敗與下一步移入[該任務 evidence](evidence/t01-foundation.md)。沒有變更產品語意或新增外送範圍。

本次實際文件檢查：13 份相關文件（大型索引／決策紀錄只檢查本次入口區塊）、158 個本機連結、29 個錨點、fences／行尾空白均通過；T01–T18 的 27 條圖面依賴與任務 metadata 相符，沒有誤勾完成。`git diff --check` 通過，僅提示既有 Git LF／CRLF 轉換；未追蹤新文件另由上述文字檢查涵蓋。原 Goal 各節與 12 項完成條件逐項對照如上。沒有改 Mermaid 圖內容，未重做渲染；沒有因文件改動重跑產品／付費測試，也沒有 commit／push／修改 Goal 狀態。

## 5. 核心旅程跨層審查（2026-10-01）

**範圍：**`target-rebuild@542dc1f3` 的已實作核心，不是只看該提交的文件差異。按 [Goal §5](README.md#5-整個-goal-的完成條件)、[程式組織](../../implementation/code-organization.md)與[寫法規範](../../implementation/coding-standard.md)，分開審查 A 正式完成／控制、Memory 編排／發布、UI／API 及 PDF。Owner 已決定產品使用 Luna／high；本次不更換模型、Prompt、門檻或重做既有來源品質試驗。

### 5.1 已核對的責任與接線

| 範圍 | 核對結果與證據邊界 |
|---|---|
| A 輸入、候選與完成 | 獨立唯讀審查未發現新阻擋：准入及人工修改共用檔案鎖，active／paused A 阻止新人工修改；起始 context 持久綁定 Memory／訪談邊界，正式答覆、交流資格、候選及歷史採用沿完成交易。取消／失敗不倒轉已完成結果。程式 owner 為 `workflows/interview_inputs.py`、`consultant_completion.py`、`jd_editing.py` 及 `agents/job_consultant/context_binding.py`。 |
| 背景取材與發布 | 主審追線 `memory_consolidation.py`、`memory_supervisor.py`、`memory_batch.py`、`memory_stage_changes.py`、角色 context 與 `candidate_lifecycle.py`：來源上界取已完成 A 的員工序號；在途範圍不擴大；同批候選延續；B2 完成後同交易固定引用、發布 head 與採用角色歷史；下一輪 A 固定讀正式快照。未發現需新增保存系統或 reviewer 的反例。 |
| 組裝與失敗責任 | `bootstrap.py` 只在有模型時啟動 supervisor，共用最外層失敗邊界，先停止 Memory 才釋放共享 leader；task cancellation 不等於產品取消。最終失敗的自動解阻仍有下述既知缺口，不因本輪結構審查而視為完成。 |
| UI／API 與正式 PDF | 第二位獨立唯讀審查未發現新阻擋；主審另抽核 `InterviewComposer.tsx`、`source-api.ts` 及 `jd_export.py`。UI 先核對原命令／current，不把讀取錯誤當閒置；來源 query 在正式稿失效前綴內；PDF 先固定正式修訂、讀取同版資料後離開 session 才渲染，不匯出畫面候選。公開中間訊息按原 execution 回看，不升格為訪談來源。 |

### 5.2 本輪實際驗證

以下在 `apps/api`、既有 `.venv-target` 執行；真 PG 是專用 loopback `55439/caliburn_t01_test`，測例建立並清理自己的隨機 schema，不碰 Demo。模型 I/O 是受控替身，**沒有真模型外送**。

```powershell
$env:CALIBURN_TEST_DATABASE_URL='postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
& ./.venv-target/Scripts/python.exe -X utf8 -B -m pytest tests/integration/test_memory_batch_orchestration.py tests/integration/test_memory_supervisor.py tests/integration/test_memory_parent_roles.py tests/integration/test_memory_candidates.py tests/integration/test_memory_source_windows.py tests/integration/test_consultant_memory_http_journey.py -q --tb=short -p no:cacheprovider
& ./.venv-target/Scripts/python.exe -X utf8 -B -m pytest tests/unit/test_consultant_tools.py tests/unit/test_response_steps.py tests/unit/test_execution_failures.py tests/unit/test_recent_preload.py -q --tb=short -p no:cacheprovider
```

- 真 PG **40 passed／26.10s**：意圖資格、固定上界、合併後續要求、交接恢復、原發布重入及 A→背景→下一輪讀取等。
- 主審核跑離線 **63 passed／1.50s**；獨立 A 審查也另跑同組 63 項，不算兩組不同覆蓋。模型回應完整性、工具／final 配對及失敗收尾等未出現回歸。
- 純審查不是新功能 TDD；不聲稱本輪重跑所有交易競爭、程序強殺、瀏覽器或真模型測試。既有相應證據仍由 T02／T08／T11／T12／T13／T17 管理。

第二位獨立 UI→API 審查者另實跑下列既有離線測試，兩條命令均 **exit code 0**；主審核對其報告並抽查程式，未重跑或冒稱為主審實跑。前端 **24 檔／136 passed**，後端 **18 passed**；不包含真 PostgreSQL、瀏覽器渲染或模型呼叫。

```powershell
# 工作目錄：S:/caliburn/apps/web
node node_modules/vitest/vitest.mjs run src/features/interview src/features/jd-editor src/features/source-viewer src/app/JobFileWorkspace.test.tsx src/shared/api/current-consultant-turn.contract.test.ts src/shared/ui/SafeMarkdown.test.tsx --reporter=dot --no-cache
# 工作目錄：S:/caliburn/apps/api
./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_pdf_renderer.py tests/unit/test_jd_export_projection.py tests/unit/test_turn_jd_markdown.py tests/contracts/test_consultant_turn_contract.py tests/contracts/test_current_consultant_turn_contract.py -q -p no:cacheprovider --tb=short
```

### 5.3 仍保留的缺口與取捨

1. **模型品質：**Luna 的跨輪 JD 來源漏選未解決；未發現 App 丟失來源的新證據，不再以同假說加 Prompt 或付費重試。沿 [T14 來源審閱](evidence/t14-job-analysis-quality.md#2026-10-01來源缺口的獨立收斂審閱)保留品質 gate，不把引用存在或 `needs_recheck=false` 當成語意充分。
2. **容量：**A 輪前 128K 已有正式 runner／PG 接線證據；帳戶回報的 200K 額度使原 272K／512K 驗收受阻。已提出降低門檻的候選，尚未取得 Owner 裁決；不改產品值、不重送同一大請求。沿 [T16](evidence/t16-compaction-continuity.md)接續。
3. **背景重新整理（2026-10-01 已處理）：**原 `release_block` 無 production 呼叫者，最終失敗後不會自動恢復 Memory（[T11 已知限制](evidence/t11-memory-batch.md#任務完成對照2026-09-30-恢復後)）。已改為只看訪談進度：失敗時記下當時前緣，之後正式序號再前進 6（三輪完成）才允許一次新批次；不以通知／重啟／時間解除，也沒有使用者 Memory 控制台。政策待 Owner 核對。

文件檢查：本輪修改的 4 份文件中，188 個本機連結、100 個錨點及程式區塊配對通過；`git diff --check` 通過，僅有既有 LF／CRLF 轉換提示。

本輪校正 `memory-storage.md` 與 T11 evidence 頂端仍寫「尚未接線／未完成」的過時摘要，保留原切片沿革；不複製規格或重寫歷史決策。兩位獨立審查與主審的上述範圍均未發現新的阻擋缺陷，不表示已知限制消失。T14／T16／T17／T18 仍未完成，**本節不是正式切換放行或整個 Goal 完成證明**。後續先承接容量取捨及既有品質反例；沒有新證據時不重跑同一提示詞試驗，不擴寫恢復平台。未改產品程式、圖、依賴或資料；未啟停 Demo、外送模型或推送分支。
