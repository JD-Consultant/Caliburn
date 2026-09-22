# JD-R002／MEM-L001／A-R001：跨顧問、Memory 與 JD 的模型安全證據契約

- 日期：2026-09-20
- Stage：G7 分段施工中；A layered read／private artifact／C read proof（Task 0–2）、Working State（Task 3）、JD adapter（Task 4）與 compaction 後 active evidence catalog 重投影（Task 5）已完成；完整 App／自然 Luna／production authority 仍待後續 gate
- 作用：統一「模型如何看、選、回查及使用來源」；不重做 canonical conversation、分層 Memory、relational JD、publication 或 compaction
- 施工計畫：[A 證據與 JD 來源接線](../plans/2026-09-20-a-evidence-and-jd-source-alignment.md)

## 0. Preflight

### 已固定的產品效果

完整資料鏈是：

```text
canonical 原始訪談
        ↓
B1 可反覆修正的完整案例／任務／事件
        ↓
B2 可反覆修正的穩定工作理解
        ↓
A 依 JD 方法訪談並使用共用 App 業務工具編輯 current JD
```

每層都可沿引用逐層回查；同一來源可支持多個案例，同一工作理解可由多個案例支持。人與 LLM 編輯 JD 時共用相同 service、validator、transaction 與真實結果。Working State 只保存尚待訪談處理的暫時工作面，continuity compaction 只保存對話延續，不成為事實來源。

### 本稿只解一個問題

現行 B1／B2 已讓模型選 Runtime 發出的短 `evidence_key`，但 A 的分層讀取、Working State 與 JD 工具仍會把長期 signed source reference 送給模型，再要求模型原樣回填。這讓同一產品內出現兩種相反的參數責任，也讓來源 token、offset 與已讀證明容易被混淆。

本稿把所有**模型可見的 conversation evidence**統一為短 key；正式 artifact、Memory、JD source link 與 source owner 仍保存既有 signed reference。JD 自己的 current-revision target refs 繼續存在，因它們是模型必須選擇的編輯目標，不是 conversation evidence address。

### 已完整核對的責任文件

- [產品核心目標](../product-notes.md)
- [分層案例與工作理解 Memory](2026-09-16-layered-case-and-work-understanding-memory-alignment.md)
- [B1／B2 模型與 Runtime 參數權責](2026-09-17-model-runtime-parameter-ownership-review.md)
- [主顧問 Working State](2026-09-16-consultant-interview-working-state-design.md)
- [App-side continuation compaction](2026-09-16-openrouter-continuation-compaction-design.md)
- [A 固定 Memory 讀取](2026-09-13-jd-memory-read-integration-slice.md)
- [當輪來源接合](2026-09-13-jd-consultant-source-integration-slice.md)
- [relational JD Agent 工具](2026-09-12-jd-relational-agent-tool-contract.md)
- [ADR 0075 relational JD authority](../adr/0075-relational-jd-authority-and-structured-editor.md)

### 明確不做

- 不新增 Agent、資料表、queue、RAG、第二份來源庫或第二套 Memory。
- 不改 B1／B2／C 的產品語意、publication manifest、CAS／receipt、背景通知或 stale recovery。
- 不把 continuity summary、Working State、案例或工作理解冒充 canonical 原話。
- 不把 JD 撤回擴大成對話、案例、工作理解或 Working State 撤回。
- 不改 provider、credential、Prompt、Skills 或正式 production authority。
- 不藉本稿擴張完整 JD 歷史、通用 undo、全文腳註或每句自動引用。

## 1. 同一產品內的六種身分不能混用

| 名稱 | 作用 | 誰可看／填 | 是否持久 authority |
|---|---|---|---|
| canonical conversation | 員工與公開顧問訊息的原始事實 | source owner／Runtime；模型按 context 或受控讀取看正文 | 是，唯一原話來源 |
| signed `source_reference` | 固定 document、checkpoint、message range 與 purpose 的正式 locator | Runtime、source owner、Memory artifact、JD source link | 是；模型不看、不填 |
| `evidence_key` | 模型在本次工作中選一筆已提供證據的短代號 | Runtime 發出；模型只能選既有 key | 否；不能寫進正式 Memory／JD citation |
| Memory stable ID／binding | 案例與工作理解的目前身分及多對多關係 | Runtime 提供合法集合；模型作語意選擇 | 是，屬 publication bundle |
| JD target／field／container ref | 定位 current JD 某項可讀或可寫目標 | App 發出；模型選擇 | 只在綁定 revision 內有效；不是來源 citation |
| Memory revision／JD head／operation ID／cursor | 固定資料版本、交易、重播與分頁 | Runtime 產生及驗證；只有既有 JD read cursor 會讓模型原樣帶回，模型不計算或改寫 | 視各 owner 而定；不是模型產生的身分 |

`evidence_key` 不是 signed reference 的新名稱，也不是資料庫主鍵。它是 model-view handle：模型只決定「這筆證據支持哪個內容」，Runtime 才把它解析成真正來源並完成 scope、版本、讀取與排序驗證。

## 2. 官方依據、共同原則與本案取捨

查閱日為 2026-09-20。

### 官方事實

- OpenAI Function Calling 建議工具名稱／參數清楚、避免不可能或互相矛盾的狀態，且由應用已知的參數應由程式帶入，不再要求模型填寫。[OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling)
- Anthropic Citations 由應用先提供有順序的 content blocks，模型回傳對已提供 block 的位置引用；應用擁有證據單位與順序。[Anthropic Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- LangChain `ToolMessage.artifact` 用來保存不應送給模型的完整工具產物；`BaseTool(response_format="content_and_artifact")` 可同時返回 model-visible content 與 private artifact。[LangChain ToolMessage](https://reference.langchain.com/python/langchain-core/messages/tool/ToolMessage)、[LangChain BaseTool](https://reference.langchain.com/python/langchain-core/tools/base/BaseTool)

### 本機鎖定版本的已核事實

目前 App 鎖定 LangChain 1.4.0、langchain-core 1.6.3、LangGraph 1.2.11 與 langchain-openrouter 0.2.7。離線 transport probe 已確認：

1. `ToolMessage.content` 會進 OpenRouter model request；
2. `ToolMessage.artifact` 不會進 model request；
3. 同一訊息經 LangChain message dict serialization／deserialization 後，artifact 仍能保留 Runtime-private signed reference；2026-09-21 的精確 PostgreSQL Saver／Store＋graph reopen 回歸亦已證明 A 的 layered case／evidence artifacts 可完整恢復。這仍只證明本機鎖定版本與此接線，不代稱 provider、自然模型或完整 App 通過。

精確版本、安裝原碼位置、探針輸入／輸出與限制保存於[ToolMessage private artifact 固定實證](evidence/2026-09-20-toolmessage-private-artifact-probe.md)。

### 跨來源共同原則

應用擁有資料 scope、身分、順序、版本、分頁與保存；模型只做必要的語意選擇。schema 合法不表示語意正確，App 仍須 fail closed 驗證。

### Caliburn 的取捨

`evidence_key`、其名稱、生命週期與 case binding 是 Caliburn 對上述原則的最小映射，不宣稱 OpenAI、Anthropic 或 LangChain 規定必須採這個 schema。

## 3. 模型、Runtime 與程式的完整參數權責

### 3.1 先分清楚四種動作

「工具 payload 裡出現一個值」不代表該值由模型擁有。第一版明確分成四類：

| 類型 | 定義 | 例子 |
|---|---|---|
| 模型撰寫 | 必須依語意產生的新內容或判斷 | 訪談問題、案例正文／diff、工作理解正文／diff、JD 文案、rework reason |
| 模型選擇 | Runtime 已把合法選項放進 context／工具結果；模型只選或原樣帶回，不得製造 | `evidence_key`、既有 case／understanding ID、JD target ref、既有 JD cursor、strict enum |
| Runtime 注入／配發 | App 已知且不需要模型判斷；不進 model schema，或只作不可編輯 context | document／run／attempt scope、base revision、new IDs、signed refs、cursor state、operation identity |
| 程式確定性處理 | 能以規則計算、驗證或原子保存，不能交給模型猜 | scope／版本檢查、排序、去重、ID／position、read proof、CAS、transaction、receipt、`changed/no_op` |

因此，「模型不能填 ID」的精確說法是：**模型不能產生或推算權威身分；需要作語意選擇時，可以從 Runtime 已發出的合法 handle 中選一個。**同理，既有 JD cursor 可以被模型原樣帶回以表示「繼續同一頁面」，但 cursor 的值、綁定版本及下一頁位置仍完全由 App 擁有。B1／B2 evidence paging 已有更窄接口，模型連 cursor 都不看，只呼叫 key-based read-more。

### 3.2 全域禁止模型產生的欄位

下列值不得要求模型自行填寫、計算、更新或宣稱成功：

| 類別 | Runtime／程式擁有的值 |
|---|---|
| scope 與執行身分 | `dataset_id`、`document_id`、thread／run／attempt／job／operation／tool-call／message identity |
| 版本與並行 | Memory publication revision／version、JD head／base revision、checkpoint identity、CAS expected version、stale refresh result |
| 正式來源 | signed `source_reference`、lineage、purpose、canonical order、source digest、正式 path |
| 讀取進度 | B1／B2／A evidence offset、next offset、read-complete proof；JD read cursor 由 App 發出，模型只能原樣續用 |
| 儲存結構 | 新 case／understanding／JD item ID、SQL ID／FK、position、junction rows、replacement IDs、時間戳 |
| 保存結果 | `changed/no_op`、publication／transaction 成功、receipt、operation/change ref、applied head、實際 diff |
| 執行政策 | provider／model route、credential、timeout、retry／correction count、token／cost budget、compaction threshold／boundary、取消狀態 |

這些值即使出現在 checkpoint、private artifact 或 App context，也不是可讓模型修改的工具參數。`strict` schema 只攔形狀；Runtime 仍須拒絕未知 handle、跨 scope、過期版本及語意上不合法的組合。

### 3.3 A 主顧問與 Working State

| 動作 | 模型撰寫／選擇 | Runtime 注入／程式處理 |
|---|---|---|
| 日常訪談與回答 | 問題、回述、澄清、最終答覆；依既有 Prompt 判斷是否使用工具 | 送入 canonical employee input、必要對話尾段、Skills、安全規則與停止狀態 |
| Memory 導覽／正文 | 從 guide 選既有 `case_id`／`understanding_id` | 固定本回合 Memory 基準，驗 ID 屬於該版本；不讓一般讀取追 `latest` |
| 原話回查 | 只選本 run 已發出的 `evidence_key` | 解析 signed ref、保存 cursor／read proof、按 canonical order 回頁；模型不填 reference／offset |
| 舊兩檔 Memory 歷史程式 | 不向正式顧問暴露；模型沒有第二套讀取契約 | 依 2026-09-17 退役決策只保留歷史 helper／測試證據，不做 migration、雙寫或 fallback；正式 layered Memory 拒絕 generic `ls/grep/read_file` 繞過 typed reads |
| 背景整理通知 | 呼叫零參數 `request_memory_consolidation()` | 保存可信 call/result；安全回合結束後才由 admission／dispatcher 決定是否建立工作，模型不填 job 或理由 |
| Working State create | `subject`、`known_and_open`、`information_needed`；有實質內容才給 `why_it_matters`、非預設 priority、source evidence keys、related handles | 配 `item_id`、預設 `open`／`normal`、scope、Memory basis、時間與 checkpoint state |
| Working State revise | 選既有 `item_id`，只送真的改變的語意 patch；可建議 focus | 保留未提欄位，驗 ID／scope／handle，更新 focus 及 state；不得把漏傳當刪除 |
| park／reopen／mark-captured | 選既有 `item_id`，由工具名稱表達唯一 transition | 程式套狀態；不再收另一個可衝突的 `status` 欄位 |
| remove | 選 item 及一個既定 reason；依 reason 選已讀 Memory handle、canonical evidence 或 replacement item | 驗版本、read proof、replacement 存在及原子移除；publication 前進本身不等於已對帳 |

Working State 已依上表建立最小正式介面：`update_interview_working_state` 提供批次 create／patch／lifecycle／remove／focus，`read_interview_working_item` 依 Runtime-issued item ID 讀取未展開內容；完整 stored object、scope、正式 refs、Memory version、時間與 receipt 都不交模型重填。Working State 不保存全域 Memory basis，也沒有整體對帳訊號；A 的固定 Memory 版本由既有 Runtime session 擁有。背景新版只在與目前訪談工作相關時，經 guide 與按需讀取影響個別 item；以 `memory_reconciled` 移除時仍要求相關最新版內容的 read proof。

### 3.4 B1 案例整理 Agent

| 工具／動作 | 模型提供 | Runtime／程式提供 |
|---|---|---|
| `read_case` | 從 guide 選既有 `case_id` | 讀固定 base 的正文與 owner-ordered evidence keys，登記已讀集合 |
| `browse_interview_history` | 零參數決定繼續找相關舊訪談 | 依 checkpoint cursor 取下一頁、配 keys、維持 canonical order |
| `read_more_evidence` | 選一個已展示 `evidence_key` | 沿該 key 的 private cursor 續讀；模型不填 offset |
| `create_case` | 完整 `content`、`route_note`、真正支持它的完整 `evidence_keys` | 配新 case ID／path，解析 refs、排序、去重及驗至少一筆來源 |
| `revise_case` | 選既有 case；`diff`／route patch；add/remove evidence keys | 未提引用保持、拒絕矛盾差異、套 patch 並重算 artifact |
| `split_case` | 選既有 case；每個 replacement 的完整正文／route／evidence keys；未分配來源的語意理由 | 配 replacement IDs，驗所有引用分配與完整性，不把舊來源自動複製到每個 replacement |
| `merge_cases` | 選既有 cases；完整正文／route；對既有來源聯集的 add/remove 差異 | 建立聯集、解析 refs、canonicalize、配新 ID |
| retire／route／finish | 選既有 case、必要 route；finish 零參數 | 驗 read-before-write／guide；計算 `changed/no_op`，完成 stage 而不發布 |

B1 模型不接觸 document、base publication、source reference、window cursor、attempt state、新 ID、digest、path、publication 或 receipt。`ToolRuntime` 由 LangChain 注入，不是模型 schema 欄位。

### 3.5 B2 工作理解 Agent

| 工具／動作 | 模型提供 | Runtime／程式提供 |
|---|---|---|
| 讀案例／理解 | 從 guides 選既有 `case_id`／`understanding_id` | 驗 fixed B1 candidate／base scope，回正文、bindings 與 case-bound keys |
| `read_case_source` | 選已展示且屬該 case 的 `evidence_key` | 解析 exact source 與 private cursor，續頁並保存 read proof |
| `request_case_rework` | 已讀 key＋具體 `reason` | 解析正式 case/source，形成不可發布的結構化 rework result；B2 不直接改案例 |
| create | 完整 understanding content、完整 `supporting_case_ids`、route note | 配新 ID，驗 cases 已讀且 current，綁 exact case digest |
| revise／revalidate | 選既有 understanding；diff（revalidate 無 diff）、完整 supporting case IDs、必要 route | 驗 required impact、保留 stable identity、刷新 binding digest |
| split／merge | 選既有 understanding IDs；replacement／合併後的完整正文、supports、route | 配新 IDs、驗所有 supports 已讀並處理 supersession |
| retire／route／finish | 選既有 understanding、必要 route；finish 零參數 | 驗 required cases／understandings 已處理；計算 outcome，stage 不自行發布 |

B2 可以按需深入原話，但只能沿已讀案例發出的 case-bound key；它沒有任意掃描整份訪談、填 signed ref／offset 或越權修改 B1 的接口。

### 3.6 C 即時 Memory 修補

| 模型提供 | Runtime／程式提供 |
|---|---|
| 選已讀 `case_id`；`case_diff`、可空 route note、要移除的已讀 evidence keys | 修改前刷新到一個明確 latest publication；解析 key→source 並保護本輪更正來源不可被移除 |
| 對每個直接受影響理解選 `understanding_id`、`revise/revalidate`、必要 diff、完整 `supporting_case_ids`、可空 route | 從 manifest 算出必須對帳的完整 understanding 集合；少一筆或多一筆都拒絕 |
| 根據原話與已讀案例作語意更正 | 配 operation、base、path、digest、request；完整 bundle 驗證後以 CAS 原子發布，回真實 applied／stale／failed 結果 |

C 不讓模型填 base revision、Memory version、source reference、operation ID、publication head 或保存結果。stale 後必須重新讀新版並重評，不能替舊 patch 換版本號。

### 3.7 JD 的十個模型工具

`restore_revision` 與 `undo_ai_turn` 是人工專用業務操作，不提供給模型。A 的模型工具維持八個 mutation＋兩個 read：

| 工具 | 模型撰寫／選擇 | Runtime／程式提供 |
|---|---|---|
| `jd_read` | 選 `current/item/section/history`、App-issued target；需要續頁時原樣帶回 issued cursor | 注入 document，materialize 同一 revision，產 refs／cursor；驗 target、view 與 stale |
| `jd_change_read` | 選 issued `change_ref`；需要續頁時原樣帶回 issued cursor | 綁原 operation/result，回不可寫歷史差異，不追 current head |
| `jd_set_text` | 選 field ref、撰寫完整 replacement text、選 basis evidence keys | 解析 evidence、驗 target／final item、保存 source links |
| `jd_insert_item` | 選 typed variant、container／after refs，撰寫語意內容、選 evidence keys | 配 ID／position，驗 kind、container、final item、relation |
| `jd_delete_item` | 選 item ref；只有既定 duty 情境可附有界 content changes | 程式決定 ownership effects，保留 tasks、驗 dependent items、原子保存 |
| `jd_move_item` | 選 target／destination／after refs；必要時附受限內容更正 | 解 FK／position／sibling，驗同文件及有界影響，不刪後重建 |
| `jd_set_task_capability` | 選 task／capability refs、`link/unlink`、link evidence | 驗 kind／同文件／relation；unlink 要求空 evidence，不刪共用能力 |
| `jd_replace_selection` | 選 App-issued selection、撰寫 replacement text、選 evidence keys | selection 綁定欄位與 base；程式組完整候選，拒絕 stale／offset 猜測 |
| `jd_create_task` | 選 container／after、撰寫目前已知 task／details，選既有 capability refs 與各自 evidence | 一次配 task/detail/relation IDs 與 positions，整組驗證及保存 |
| `jd_revise_work` | 選 typed semantic changes、既有 targets／anchors、文字、mode 與 evidence keys | 驗同 base、重複／衝突、final candidate、關係及上限；全成或全拒絕 |

模型不填 JD document、revision、operation、SQL IDs、FK 或 position，也不能引用本次尚未保存的新 ID。success、no-change、actual diff 與 change refs 只能來自共同 domain／transaction／receipt。`basis_evidence_keys` 是 successor 的 model adapter 欄位；解析後的 domain command 仍使用 canonical refs，人與 LLM 不分叉業務邏輯。

### 3.8 Compaction、模型限制與恢復

主 A／B1／B2 模型不呼叫 compaction tool，也不提交 threshold、token count、safe boundary 或 summary state。只有受限 summary model 撰寫 `summary_text`；Runtime 選取已完成安全 wave、提供舊 summary＋增量 canonical prefix，產生 `covered_through_message_id`／digest，驗未截斷／未取消後才與成功主模型 step 一起保存。

Runtime 另擁有 role profile、主輸出預留、模型／工具 call ceiling、timeout、SDK retry、provider route、credential、usage 觀察、停止與恢復。summary 不取得 JD／Memory／背景工具，不形成 evidence、Working State、Memory 或 JD basis；canonical messages 與 private artifacts 不因 request-only compaction 改寫。

### 3.9 現況與本切片不能混稱完成

- B1／B2 上述 key、private cursor、stage 與 Runtime 驗證已實作並有離線回歸。
- C 已有 strict model intent 與 Runtime binding／CAS；本切片只改它取得 A read proof 的方式，不重做 repair workflow。
- A 的 layered read 結果已於 2026-09-21 完成 model content／private artifact 分工，Memory revision／signed refs／offset 不再進 model-visible read 結果；JD mutation 仍叫 `basis_refs`，是下一施工單位的待解缺口。不得把 A 讀取切片完成混稱為 JD／Working State 或完整 compaction 接線完成。
- Working State 核心工具與 projection 已於 2026-09-21 依本節施工；model schema 只收語意 patch、既有 item ID、evidence keys 與已發出的 related handles，Runtime-private ToolMessage artifact／checkpoint 保存 resolved refs 與更新 digest。Owner 已裁決不增加全域 Memory basis／整體對帳訊號；Task 3 的這項語意已結案。
- JD 既有 issued target／change／cursor 契約是刻意保留的模型選擇介面；本切片只把 conversation source address 換成 evidence key，不順便重設 JD pagination。

## 4. 一份共同語意，各角色使用自己的既有 state owner

| 角色／範圍 | key 生命週期 | Runtime-private owner | 正式保存 |
|---|---|---|---|
| A 主顧問 | 一個 employee-input child run；resume 後同一 key 不漂移 | 已有 checkpoint 中 App 產生的可信 ToolMessage artifacts／等價 private projection | Working State、Memory、JD 各自只保存 resolved refs／IDs，不保存 key |
| B1 案例整理 | 一個 B1 attempt | 已完成的 `CaseMaintenanceStage` registry | Case artifact 保存 canonical signed refs |
| B2 工作理解 | 一個 B2 attempt；key 綁 case＋source | 已完成的 B2 stage registry | Understanding 只保存 case ID＋digest binding；不越層保存原話 key |
| C 即時修補 | 沿 A 本回合已讀 registry，不另配第四套 key | A checkpoint／read proof | 完整 layered bundle 一次 CAS 發布 |
| JD 寫入 | 使用 A 本回合可用且符合讀取條件的 keys | A registry 解析後進既有 JD operation binding | `jd_source_link` 保存 signed ref＋basis digest |

這是**共同契約，不是共同資料表或共同基底類別**。B1／B2 已驗 stage 不為了外觀一致而改寫；A 與 JD 只補目前缺少的 model-view 隔離。

## 5. A 的 context 與按需讀取

### 5.1 Runtime 在模型前提供的資料

- 既有顧問 Prompt、Skills 與安全規則；
- canonical current employee input 及必要公開對話尾段；
- 本回合目前的 Memory 讀取基準、案例 guide、工作理解 guide；
- current JD revision 的輕量導覽與 App-issued targets；完整內容仍由 `jd_read` 按需取得；
- Working State current view；
- 本回合 active evidence catalog：短 key、來源角色概況、所屬 scope、是否已完整讀取，不含 signed reference、offset、checkpoint 或資料庫 ID；
- 既有受控背景 availability／結果通知。背景 publication 不偷偷改本回合 Memory 基準。

Memory revision、JD head／base 與 document scope 都由 Runtime 提供。模型不能從 key 推算版本，也不能以較新的背景通知自行升格基準。

### 5.2 A 的讀取路徑

```text
guide／JD map
    ↓
案例、工作理解或 JD 相關正文
    ↓
需要核對細節時，選 Runtime 發出的 evidence_key
    ↓
read_evidence(evidence_key)
    ↓
Runtime 依同一固定來源逐頁返回 role＋原文，並保存 cursor／完整讀取證明
```

`read_case` 不再把 signed reference、Memory version 或 offset 放進 model-visible content；它返回案例正文、owner-ordered evidence blocks 與 keys。`read_work_understanding` 返回正文與 supporting case IDs，case digest 留在 Runtime-private publication artifact；需要原話時先讀案例，再沿該案例的 key 回查。

A 的 model-facing `read_conversation(reference, offset, part)` 由 `read_evidence(evidence_key)` 取代。底層仍重用同一 source owner 與分頁能力，不建立第二個 reader。工具數是一進一退，不藉此擴張 A 的通用檔案或來源工具面。

### 5.3 key 的 scope

- 同一 run、同一 access scope 與同一 source 重複出現時重用同一 key。
- 同一 source 支持兩個不同案例時，配置兩個 case-bound keys；讀過 case A 的來源不能冒充已讀 case B。
- current-turn key 綁本輪已保存原話；因原 Human／必要 AI 上下文已在 request 中，Runtime 可標為 `visible`。
- Working State 及舊案例帶入的來源只先標為 `available`；完整原話需經 `read_evidence` 連續讀完才標為 `read_complete`。
- key 格式不承擔順序；ordered array 才是前後關係。key 不跨 run 持久，下一回合可重新發配。

## 6. Working State 的來源參數

Working State 的持久 item 可繼續保存 canonical `source_refs`，因它們屬 Runtime-private checkpoint state；但 model-view 與更新工具不再顯示／接收 raw refs。

- model-view 將可回查來源投影成 `evidence_keys`；沒有來源的純未知仍可為空。
- create／revise／`no_longer_relevant` 等需要引用原話時，模型提交 `source_evidence_keys`；Runtime 解析成 refs、驗 scope 與實際可見／已讀狀態後保存。
- `related_refs` 仍可使用 Runtime-issued case／understanding／JD handles，因它們是模型要選的語意目標，不是 signed conversation address。
- compaction summary 不能自行新增 Working State source；只有 canonical message 或受控 evidence read 能形成來源。

這只改 model-facing input／projection，不新增 Working State 歷史、Agenda、planner 或 Memory writer。

## 7. JD 的完整接合

### 7.1 JD 讀取與定位維持原權責

`jd_read` 仍由 App 在同一 current revision 產生 item／field／container／selection refs；模型需要選哪個 JD 目標，所以這些 refs 繼續 model-visible。revision、document、position、operation、SQL IDs 及保存結果仍由 Runtime／App 管理。

JD read／change read 中的來源資訊改投影為：

- `evidence_key`；
- `basis_status`（例如 current／needs_recheck）；
- readability／是否已完整讀取；
- 必要的人類可理解角色與順序提示。

model-view 不返回 signed `source_ref`。人類 UI 或 App 內部查回可沿既有 owner 使用正式 locator，本稿不刪除 source UI 能力。

### 7.2 JD 寫入只接收 evidence keys

現行各模型 mutation 的 `basis_refs` 在 successor generated model contract 改為 `basis_evidence_keys`。既有產品語意保持：

- 空陣列表示這次不新增／刷新來源，原 target 未被明示移除的既有 links 保留；
- 非空只表示模型選擇本回合已提供且符合讀取條件的 evidence；
- 模型不能輸入 signed ref、checkpoint、offset、revision 或 operation ID；
- Runtime 在 domain command 前解析 keys，驗 document、scope、read proof、去重與 canonical order；
- operation digest 使用解析後的 canonical refs，不使用短 key 文字；
- 既有 domain service、source resolver、`jd_source_link`、basis digest、交易、receipt 與當輪差異不變。

current-turn evidence 因原文已在 request 可直接作 basis；較早 Working State／案例 evidence 必須至少經 `read_evidence` 完整讀取後才能附到 JD。只讀案例／理解正文不足以自動把其所有原話附到 JD，Runtime 不替模型猜來源。

### 7.3 人與 LLM 仍共用同一業務邏輯

模型 key 只是一層 model adapter。解析後仍呼叫與人工入口相同的 domain command、validator、transaction 與 receipt owner。不能在 Agent middleware 另做第二套 JD 規則，也不能讓 UI 重算 relation／版本不變量。

JD 當輪撤回只形成新的補償性 JD 寫入；canonical conversation、Working State、案例、工作理解、來源、checkpoint 與原操作結果不倒退。

## 8. Private artifact 與可信 read proof

A 的 evidence-producing tool 使用 LangChain 原生 `content_and_artifact` 分工：

```text
ToolMessage.content  → 給模型：key、role、正文頁、has_more、狀態
ToolMessage.artifact → 給 Runtime：格式版、document/run、Memory basis、
                       scope、case／working item、signed ref、canonical order、
                       cursor、read-complete proof
```

artifact 只有在下列條件同時成立時才可信：由 composition root 注入的正式工具實例產生、tool call/result identity 匹配、屬同一 document／run checkpoint，且格式與 digest 通過驗證。模型文字、compaction summary、偽造 ToolMessage 或外部同名工具都不能建立 read proof。

現有 `layered_read_proof` 應從這些可信 artifacts／等價 checkpoint-private records 重建，不再從 model-visible signed refs 推導。這不是新資料庫 registry；checkpoint 已是 A run 的既有持久 owner。

## 9. Compaction 與恢復

request-only compaction 只改下一次模型 request 的可見對話，不修改 canonical messages、checkpoint artifacts、Working State、Memory 或 JD。

1. 已完成舊工具 wave 可被 continuity summary 取代；尚未完整處理的 B1 訪談來源仍逐字保留，沿既有規則不變。
2. evidence catalog 由 Runtime 從 checkpoint-private records 重新投影；summary 不負責保存、重建或改寫 key→source mapping。
3. summary 可以記「已分析到哪裡」，但不能成為 source、read proof 或 JD basis。
4. 若原文已離開當前 request，模型對細節不確定時沿同一 key 再讀；Runtime 使用既有 cursor／完成狀態，不 fallback latest。
5. 同一 run resume 後 key、scope、cursor 與 read proof 不漂移；新 employee input 是新 run，重新發配 keys，但持久 Working State／Memory／JD 中的正式 refs 不變。

這樣 compaction 不會切斷引用，也不會把非權威摘要升格成員工原話。

## 10. 版本與發布規則保持一致

- A 的 Memory 基準由 Runtime 在回合開始固定；一般回查不追背景 latest。C 前才按既有規則刷新到明確最新版，成功後推到實際 applied head。
- B1／B2 各自在固定 attempt base 工作；正式 artifact 只保存 canonical refs／case bindings，publication 仍一次 CAS 完整 bundle。
- JD mutation 必須基於 current `jd_read` 發出的同版 targets；stale 後重讀 current，再形成新 operation。evidence key 不授權越過 JD revision check。
- source ref 自身固定 conversation range；Memory 或 JD 版本前進不改寫歷史來源。
- 同一次操作不可混用不同 document、不同 A run、不同 B1／B2 attempt 或不同 JD base 的 handles。

## 11. 失敗與有限恢復

下列情況一律在任何 stage／JD transaction 前 fail closed：

- 未知、過期、跨 document／run／attempt 的 key；
- key 與 case／Working State scope 不符；
- 模型提交 signed ref、A／B1／B2 evidence offset／cursor 或其他 Runtime-only 欄位；既有 JD read 只接受 App 已發出的同 view cursor 原樣續用；
- 必須完整讀取但仍有 `has_more`；
- artifact 缺失、格式錯誤、call/result 不匹配或 mapping 漂移；
- Memory base／JD base stale；
- key 解析後出現重複、錯序、purpose／lineage 不符或來源已不可讀。

可修正的模型參數錯誤沿既有 A correction episode 有界處理；source／DB／checkpoint 故障不叫模型改參數修基礎設施。`outcome_unknown` 仍只對帳原 operation，不配置新 key 或新 operation 重做。任何失敗不得留下部分 Working State、Memory stage 或 JD 寫入。

## 12. 代表性驗收情境

| 情境 | 必須成立 |
|---|---|
| 本輪員工回答後直接改 JD | 原 Human 仍在 request；Runtime 發 current-turn key；模型用 key，JD 最終只保存 resolved signed ref |
| A 從案例深入舊原話 | `read_case` 只顯示 case-bound keys；`read_evidence` 逐頁讀完後才可作 C／JD basis |
| 同一來源支持兩案例 | 兩個 keys 各自綁 case；讀 A 不可滿足 B 的 read proof；正式 artifacts 可保存同一 signed ref |
| Working State 跨回合恢復 | checkpoint 內保存正式 refs；新回合重新投影 keys，模型看不到舊 signed token |
| compaction 發生在讀取與寫入之間 | canonical／artifact 不變；Runtime 重新投影 active catalog；summary 不能自行產生 evidence |
| JD head 在模型規劃後改變 | evidence 仍可查，但舊 JD targets 失效；整批零寫入並要求 `jd_read current` |
| C 即時更正 | 只接受 A 在最新 Memory 基準實際讀完的 case-bound evidence；C 不另建 registry |
| B1 split／merge、B2 重整 | 既有 attempt registry、owner order、引用分配、case binding 與 publication 規則保持原驗收 |
| 模型嘗試回填 raw source token | model schema 或 Runtime 預檢拒絕，無 stage／JD 效果 |
| resume 後同 key 指向不同來源 | 明確失敗；不能靜默重配、fallback latest 或只換版本號 |

## 13. 精確施工邊界

第一個施工單位只改 A model-view 與 JD／Working State adapter：

1. 先用紅燈固定「raw source 不進 model request」「resume 不換 key」「case scope 隔離」「JD 只保存 resolved refs」。
2. 將 A `read_case` 的 model content／private artifact 分離；新增 `read_evidence(evidence_key)`，取代 model-facing raw-reference `read_conversation`。
3. 讓 Working State model projection／tool input 使用 evidence keys，持久 state 仍保存 refs。
4. 更新 generated JD model contract：`basis_refs` → `basis_evidence_keys`；只在 model adapter 解析，domain／DB schema 不改。
5. 將 A／C read proof 改由可信 artifacts 建立，補 request-only compaction 與 checkpoint resume 回歸。
6. 重跑受影響的 A、Working State、JD tools、Memory context、C repair、compaction 與 transport contract；不無差別重跑已結案的 B1／B2 設計實驗。

若實作證明鎖定框架無法在正式 checkpointer／OpenRouter 路徑可靠保存 private artifact，停止本切片並帶回可重現反例；不得退回「模型回填 raw token」或另建資料庫 registry 作默認補救。

## 14. 完成條件

只有下列全部成立，才能把本稿從「設計收斂」標成 G7 接線完成：

- A 的正式 model request 不含 conversation signed refs、offset、checkpoint 或 Memory/JD Runtime IDs；
- A 能由 guide→正文→evidence 完成按需回查，且 checkpoint resume 後 mapping 穩定；
- Working State、C 與 JD 各自取得正確 resolved refs，不把 key 持久化；
- JD current revision／業務工具／transaction／receipt 與當輪撤回語意完全沿用；
- compaction 前後 read proof、key catalog 與 canonical source 不遺失、不混 scope；
- B1／B2 現有 evidence contract 與完整 publication 回歸未退化；
- 失敗情境皆零部分效果，沒有 fallback latest、模型自造來源或第二套 authority。

自然 Luna 是否會正確選 key、完整 App 瀏覽器旅程及 production authority 仍是後續獨立 gate，不由離線接線測試代替。
