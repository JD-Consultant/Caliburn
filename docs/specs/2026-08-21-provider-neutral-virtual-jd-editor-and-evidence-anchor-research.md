# Provider-neutral 虛擬 JD 編輯器與確定性 Evidence Anchor 研究

- 日期：2026-08-21
- 狀態：**設計已與 owner 白話對齊；待 successor ADR 核准後施工**
- 範圍：候選 JD 編輯、Tool 介面、候選／待審／核准邊界、員工原話定位
- 不在本輪：RAG／Reference、能力級別、A、auto-accept、正式品質 eval
- 前置決策：ADR 0060、0061、0062、0063

大方向追溯：[`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md)、[`2026-07-30-professional-consultant-minimal-complete-loop-research.md`](2026-07-30-professional-consultant-minimal-complete-loop-research.md)、[`2026-08-01-opks-design-decisions-research.md`](2026-08-01-opks-design-decisions-research.md) 與 ADR 0060。若本研究的 editor 機制與這些產品行為衝突，應修改本研究，不用舊實作反向改寫產品。

## 0. 結論

ADR 0063 的大方向不翻案：模型必須先在非權威候選區實際編輯、取得 application 結果並修正，最後只發布已驗證的 candidate；員工接受或修改後接受之前，核准 JD 不得改變。

需要取代的是**模型面前的編輯機制**。現行自寫 `job_document_candidate_edit` 把所有可能 payload 壓進同一個 flat required-only business form，再要求模型替未使用欄位填中性值。真實模型先後在 integer sentinel、UUID、linkage、`enabler_list` 與 quote offset 上失敗，說明問題已不是多補一句 prompt，而是 agent-facing editor 介面不自然。

採用下列方案：

1. 用 Deep Agents `FilesystemMiddleware`＋`StateBackend`／`CompositeBackend` 直接提供 provider-neutral 虛擬 workspace；
2. 暴露成熟、通用的 `ls`、`read_file`、`grep`、`write_file`、`edit_file`、`delete`，另保留一個極薄、只讀的 `check_candidate_document` domain check Tool，不再維護自寫候選 mega-form；
3. application 將核准 JD、pending、員工來源與 Skills 投影成有權限邊界的 virtual resources，只有 `/candidate/**` 可寫；
4. model 透過通用 editor 反覆修改，再像 coding agent 跑測試一樣呼叫 `check_candidate_document`；application 解析 typed candidate、回傳可行動問題，final publication 前 fail closed；
5. Evidence 改由模型選 `source／segment＋exact quote`，application 確定性解析並保存 char offsets；模型不再手算 `start／end`；
6. split／merge 不是額外權限或專用 Tool，而是 create／edit／delete 的一組相依變更，員工仍以 atomic review group 裁決；
7. VFS／checkpoint 是可丟棄的工作區，不是第二份文件 authority；只有員工 authority command 能改核准 JD。

## 1. 產品大方向與名詞

這次只改「LLM 怎麼操作 JD 編輯器」，不改產品目的：

- 一位 AI 專業職務顧問，以當前焦點訪談並保存旁支線索；
- Task／Duty／O／P／K／S 可隨訪談雙向調整，員工原話與更正可跨回合記得；
- 所有 LLM 產生的文件內容都必須讓員工接受、修改後接受、拒絕或延後；
- 重大衝突／缺少必要決策時先問員工，一般 Gap 留在待處理清單；
- 不把訪談做成固定 wizard，不因員工關頁而建立 pause／finish 狀態；
- 本輪仍不接 RAG，不產生能力級別與 A。

為避免「提交」混淆，後續文件與 UI 分三層用語：

| 層次 | 白話名稱 | 效力 |
|---|---|---|
| model 內部 | 套用候選編輯 | 只改 run-scoped VFS，可反覆修正 |
| model → 員工 | 發布待審變更 | 建立 durable review bundle，仍非核准 JD |
| 員工 command | 核准寫入 JD | 接受或修改後接受才進唯一 document authority |

員工不需要看到每次 `edit_file` 的 JSON，也不需要替模型草擬過程逐步按同意；員工看到的是最後的 semantic diff 與相依分組。

## 2. 現行診斷

### 2.1 候選 Tool 是 agent-facing business mega-form

`OutputDocumentChange` 每筆都帶 `text_value`、`integer_value`、`uuid_value`、`uuid_values`、`enablers`、`duties`、`tasks`、`opks_items` 等 payload slots。mapper 再依 target／field 選唯一合法 slot，任何其他 slot 非中性值就拒絕：

```text
unused document payload slot <name> carries content
```

這個 shape 是為繞過 provider union／optional 限制而生，對 deterministic application 合理，對 non-deterministic agent 卻要求它同時理解所有欄位並正確清空無關欄位。`enabler_list` 被錯置不是新的職務分析錯誤，而是既有介面的 agent ergonomics 缺陷。

### 2.2 Quote verifier 的事實與過度診斷要分開

現行 `OutputQuoteAnchor` 要模型送 `source_id／start／end／quote`，verifier 檢查：

```python
source.text[anchor.start : anchor.end] == anchor.quote
```

兩次失敗只證明 slice 與 quote 不同；現有安全 log 沒保留原始 payload，因此不能進一步宣稱一定是中文字元本身造成。可能原因包括標點、空白、換行、Unicode 計數慣例或模型單純誤算。但無論是哪一項，字元定位都是 application 能確定完成的機械工作，不應交給 LLM 猜。

### 2.3 Prompt 補 sentinel 已證明只能治症狀

先前 live smoke 把 `integer_value` 中性值明列進 prompt 後，該案例第一次通過；後續仍出現另一個未使用 slot 與 quote offset 錯誤。這表示 prompt 可以修一個觀察到的欄位，卻無法消除 mega-form 的整體認知負擔。

## 3. OpenAI／Anthropic 官方做法

### 3.1 Codex／OpenAI Apply Patch

OpenAI Apply Patch 的核心不是「模型輸出最後文件」，而是：模型提出 create／update／delete diff，harness 套用到 working directory 或 in-memory workspace，將 completed／failed 與可行動錯誤送回模型，模型再繼續編輯。官方也把 path validation、scratch copy、錯誤回報與 all-or-nothing／per-file atomicity 明確留給 harness。

Codex 的 review pane 再把 working-tree diff 與 stage／revert／commit 分開。這證明「模型可先在受控工作區實際修改」與「使用者何時接受結果」是兩個邊界。

### 3.2 Claude Code／Anthropic editor

Anthropic 的 SWE-bench agent 以最小 scaffold（prompt、Bash、Edit）取得當時最佳結果。Edit Tool 使用 `view／create／str_replace／insert／undo`；`old_str` 必須唯一精確命中，否則回可修正錯誤。Claude Code 另在直接 editor edit 前保存 checkpoint，支援 rewind；外部副作用不能靠 checkpoint 回復，因此另設 permission boundary。

Anthropic 的工具設計研究指出：

- 工具不是越多越好，應選少量、高影響且目的清楚的工具；
- 工具可以把多個低階步驟收在 implementation 內；
- 重複 invalid parameter 通常代表描述、範例或 schema 需要改善；
- error 應告訴 agent 下一步如何修，不只回 opaque code；
- agent 對有語意的名稱／handle 通常比任意 UUID 更穩定。

2026 Managed Agents 又把 session、harness、sandbox 拆成穩定介面，稱為 brain／hands／session 分離。Caliburn 對應為：LLM＋LangChain loop 是 brain，Deep Agents VFS tools 是 hands，LangGraph checkpoint／事件是 session；核准 JD 仍是獨立產品 authority。

### 3.3 Anthropic Citations 對 Evidence 的啟示

Anthropic Citations 不是要求模型自己精算位置，而是由 API 解析 citation、抽出 `cited_text` 與 location，並保證 pointer 指向提供的文件。對 transcript／特殊格式可使用 custom content block indices。官方也記載 citations 與 strict Structured Outputs 目前不能同請求併用。

因此 Caliburn 第一版不綁 Anthropic native citation，也不為某 provider 建第二條 Evidence truth；採 provider-neutral exact-quote resolver，未來 native citation 只能經 adapter 正規化成同一內部 anchor。

## 4. 成熟 framework 覆蓋

本 repo 已鎖定 `deepagents==0.7.5`、`langchain==1.3.15`、`langgraph==1.2.11`。現行 Deep Agents 已提供：

- `FilesystemMiddleware`；
- `StateBackend`（存在 LangGraph state、可隨 thread checkpoint）；
- `CompositeBackend` 與自訂 virtual backend；
- `ls／read_file／write_file／edit_file／delete／glob／grep`；
- `tools=` allowlist；
- `FilesystemPermission` read／write path 規則；
- exact `old_string／new_string` editor；
- structured result／error protocol。

所以不自寫 virtual filesystem、通用 read/write/edit schema、pagination、exact replace、路徑正規化或 checkpoint lifecycle。Caliburn 自寫範圍縮到框架不可能知道的政策：

1. approved／pending／candidate／source／Skill 的投影；
2. 哪些 namespace 可讀／可寫；
3. virtual resource → typed JD 的 parser；
4. Task／Duty／OPKS、Evidence、read-set、stale 與 employee authority invariant；
5. semantic diff／atomic subgroup／review bundle；
6. exact quote → source revision offsets 的 resolver；
7. 一個不寫 approved、不改 VFS，只執行上述 parser／verifier 的 `check_candidate_document` Tool。

2026-08-21 以本 repo pinned 0.7.5 實際建立六個 filesystem Tool，經 LangChain `convert_to_openai_tool` 與現行 compact final schema 量測：**7 schemas、77 properties、7 optional parameters、3 union sites、6 tool-level open objects、max depth 3、10,320 bytes**。計畫中的 `check_candidate_document` 使用 forbid-extra 的空 input schema，不增加 optional／union。這低於 Anthropic 目前公開的 20 strict tools、24 optional 與 16 union limits，但 bytes／open objects 沒有對應官方硬門檻，且 OpenRouter／實際 provider 仍可能轉換不同；因此它只證明方案值得施工，不能取代實作後 exact adapter probe。

### 4.1 Framework-first 取代審核

這次用「產品目的是否相同」判斷可否取代，不保留舊元件名稱或 compatibility layer。完整顧問 runtime 的取代帳本如下；粗體列是本 successor ADR 新改的部分：

| 產品目的 | 成熟 framework／primitive | Caliburn 仍需保留的薄政策 | 判定 |
|---|---|---|---|
| 有界 model／tool loop、重試、成本與步數上限 | LangChain `create_agent`、ToolNode、call-limit／retry middleware | profile allowlist、哪些錯可重試、receipt | 已取代 |
| 對話跨關頁續談、狀態恢復與必要員工回答 | LangGraph checkpoint／Postgres Saver、routing、`interrupt`／`Command` | 哪種職務歧義真的必須先問 | 已取代 |
| 動態訪談重點、旁支、缺口、可信進度 | LangGraph typed state／reducers／routing＋deterministic projection | 職務分析 eligibility、reason code、不可用假百分比 | 已取代舊元件生命週期 |
| 記得員工以前說過的話與更正 | LangGraph Store＋stable references；**read-only source VFS backend** | document scope、current validity、correction precedence | 已取代；不等於 RAG |
| Task／Duty／O／P／K／S 方法按需載入 | Deep Agents SkillsMiddleware＋FilesystemMiddleware `read_file` | repo 內研究方法與當輪 Skill eligibility | 已取代巨型 prompt／固定 scheduler |
| **像編輯器一樣讀、增、改、刪候選 JD** | **Deep Agents FilesystemMiddleware＋StateBackend／CompositeBackend** | **namespace、canonical resource、create-only／delete safety、並行衝突** | **本 ADR 取代 mega-form** |
| **候選修改後觀察錯誤再修正** | **framework Tool result／error loop** | **JD parser、diagnostic wording、publication blocker** | **framework 主體＋薄 domain Tool** |
| 員工接受／修改後接受／拒絕／延後 | LangGraph checkpointed review state＋typed Command | 哪些 action 相依、誰有 authority、stale/read-set | 通用生命週期已取代；職務政策保留 |
| 核准文件唯一真相與直接編輯 | LangGraph typed authority channel＋command/checkpoint | 文件 invariant、只有員工可寫 | 已取代舊 writer；不可交給 VFS |
| **來源引用與 char anchor** | **framework VFS retrieval；未來可選 provider-native citations adapter** | **exact quote、來源可信度、更正 precedence、原文 offsets** | **沒有成熟 provider-neutral 元件能決定本產品證據語意；只保留必要薄層** |
| JSON／型別／欄位驗證 | Pydantic | Task／Duty／OPKS linkage 與合法性 | framework＋必要 domain schema |
| semantic diff、atomic subgroup、匯出合法性 | 無能理解 Caliburn JD 語意的通用 agent framework | deterministic domain policy | 必須保留；不可讓 LLM／VFS 猜 |

因此「用了 VFS」不代表保留舊 candidate workspace；舊 flat wire、舊 Tool、sentinel 與 model-facing payload 都退出。反過來，「仍有 Evidence verifier／JD parser」也不表示拒絕 framework，而是現有 framework 只能承接 retrieval、schema、loop 與 workspace，不能替 Caliburn 決定員工原話是否足以支持某個 O／P／K／S。

## 5. 方案比較

| 方案 | 效果 | 維護與風險 | 決定 |
|---|---|---|---|
| 保留 flat required-only mega-form，再補 prompt | 改碼最少；已知案例可逐一補洞 | 新 slot／新模型仍會重演；與 agent editor 主流相反 | 否決 |
| 每個 business verb 一個 Tool | 每個 schema 小 | Tool 數、重疊選擇與跨 Tool atomicity 增加；split／merge 變成假權限 | 否決 |
| 自寫一個 patch DSL／VFS | 可做得精簡 | 重寫 framework 已有 editor、backend、permission 與 checkpoint | 否決 |
| **Deep Agents 受限 VFS＋typed publication gate** | 使用成熟 editor；可讀真實 after-state、修正錯誤、自然組合跨實體變更 | 需設計 canonical resources 與 application parser；candidate VFS 必須嚴格與 authority 分開 | **採用** |
| provider-native Apply Patch／Claude editor 直接成為唯一介面 | 各 provider 可能有最佳工具訓練 | OpenRouter／模型替換能力下降，協定與行為不一致 | 第一版否決；日後只可作 adapter optimization |

## 6. 目標設計

### 6.1 Virtual namespace

以 `CompositeBackend`／受限 backend 投影：

```text
/skills/**       只讀：Task／Duty／O／P／K／S 方法
/sources/**      只讀：immutable 員工原話、source／segment metadata、更正鏈
/approved/**     只讀：本輪核准 JD baseline
/pending/**      只讀：明示未核准、deferred／stale／rejected memory；不得默認併入 baseline
/candidate/**    可讀寫：本輪虛擬 JD 工作區
```

不使用 host `FilesystemBackend`、shell 或 `execute`。application 只投影當前 document scope，VFS 沒有跨文件查詢能力與 approved write edge。

第一版 filesystem allowlist 為 `ls／read_file／grep／write_file／edit_file／delete`：前三者讀取投影，後三者只能寫本輪 `/candidate/<run_id>/**`。它們取代三個自寫 employee-source read Tool 與 `job_document_candidate_edit`；Skill 仍由同一 `read_file` 按需載入。另有一個 application-owned `check_candidate_document` Tool，只讀取目前 candidate、執行 domain check 並回 receipt，不新增內容、也沒有 approved write edge。不得另外暴露 `add_task／split_task／merge_duty／revise_opks`。

安全邊界不能只依賴 prompt，也不應依賴 pinned `FilesystemMiddleware` 的 private `_permissions` constructor argument。依 Deep Agents 官方 backend policy hook 作法，`CompositeBackend` route 與 application 的 `BackendProtocol` wrapper 是 hard boundary：只讀 routes 對 `write／edit／delete` 一律回 structured denial，candidate route 再驗 exact run prefix、resource type 與 mutation policy。若目前組裝層可經 public API 使用 `FilesystemPermission`，可再加 declarative deny 作 defense in depth，但不能取代 backend enforcement。

Deep Agents 0.7.5 的 `FilesystemMiddleware` 預設會把大型 Tool result 與大型 human message offload 到 `/large_tool_results/**`、`/conversation_history/**`。這兩個額外可讀寫 namespace 會複製檢查結果或員工原話，與五 namespace／單一來源 truth 衝突；本產品必須明設 `tool_token_limit_before_evict=None`、`human_message_token_limit_before_evict=None`。source／check Tool result 改由 application 限量、排序並回 omitted count；超過上限要求模型縮小查詢或分批修正，不讓 framework 悄悄建立第六、第七個儲存面。

`StateBackend` 的 files 會隨 conversation thread checkpoint；因此 candidate 路徑必須帶 `run_id`，backend 對 `/candidate` 的 `ls／read／grep` 也只能看目前 run，舊 run 即使仍在 checkpoint history 也不可列出、讀取或發布。成功 publication 時，建立 durable review bundle 與清除 active candidate files 必須在同一 semantic transition；失敗只供同一 run retry，開始新一般 run 時舊 scratch 須 deterministic 清除，除非員工明確選擇指定 pending bundle 繼續修。這避免 hidden scratch 跨回合成為 baseline，也避免 active checkpoint 無限累積舊 candidate files。歷史 checkpoint 的 retention 沿用既有 Saver policy，不另建 archive store。`/sources/**` 與 `/approved/**` 是對既有 Store／authority 的 lazy read-only projection，不複製成另一份真相。

現行三個 `employee_source_*` Tool 實際能力是「依 stable ID 讀原文」、「讀 oldest-to-newest 更正鏈」與「只查 current source 的 lexical search」；production 並未由這三個 Tool 暴露 semantic search。因此來源 backend 必須保留同等語意，而不是只把一包 transcript 複製進 state：

```text
/sources/current/<source-handle>.txt                 immutable 原始文字
/sources/current/<source-handle>.json                speaker／kind／timestamp／validity／correction handles
/sources/lineages/<lineage-handle>/<revision>.txt    明示 historical revision
/sources/lineages/<lineage-handle>/<revision>.json   oldest-to-newest 更正關係
```

`ls／read_file` 取代 get／lineage，`grep` 只搜尋 current `.txt` projection 並由 backend 保留既有 document scope、排序與結果上限；historical revision 不得混入一般搜尋結果。這個 backend 實作 `BackendProtocol` 的 async `als／aread／agrep`，直接 lazy-read 既有 employee-source Store，不在 worker thread 包同步 DB 呼叫，也不把 source copy 或 framework checkpoint 當新的 Evidence truth。日後接 RAG／semantic retrieval 要另作決策，不偷塞進這次替換。

### 6.2 Candidate resources

候選區使用 application 產生的 canonical、固定欄位順序、pretty-printed JSON resources，一個 entity 一個 resource；模型不重送整份文件：

```text
/candidate/<run_id>/header.json
/candidate/<run_id>/duties/<local-handle>.json
/candidate/<run_id>/tasks/<local-handle>.json
/candidate/<run_id>/opks/{o,p,k,s}/<local-handle>.json
/candidate/<run_id>/review-groups.json
```

既有 entity 用 application 提供的短 local handle 對應 stable ID；新增 entity 只取 local handle，正式 UUID 與最終位置碼由 application 配置。local handle 不得偽裝成 iCAP／export position code。

`edit_file` 只允許 exact unique replacement，`replace_all=true` 第一版拒絕；`write_file` 只建立新 resource，若路徑已存在必須改用 `edit_file`；`delete` 只允許刪除合法 entity resource，不允許遞迴刪整個 candidate namespace。這些是包在 framework Tool 外的薄權限／安全 policy，不重寫 editor。模型可以在候選區暫時留下「尚未完整」但可繼續編輯的中間狀態，像 coding agent 暫時讓測試紅燈；未通過 publication gate 就永遠不會成為 review bundle。

這層薄 policy 不是可省略的重複實作：本 repo 鎖定的 Deep Agents 0.7.5 `StateBackend.write()` 會覆寫既有 resource，而 `delete()` 可遞迴刪除 prefix；Caliburn 必須把它們收窄成 create-only 與 entity-file-only。LangGraph `ToolNode` 也會平行執行同一 AI message 內的多個 Tool calls；讀取可平行，寫入不同 resource 可合併，但 middleware 必須拒絕同一路徑或 ancestor／descendant 路徑的競爭 mutation，並要求模型順序重試。`check_candidate_document` 不得與任何 mutation 出現在同一 Tool wave，必須在 mutation results 回到模型後的下一步單獨執行；否則可能檢查到 wave 開始前的 snapshot。不能讓 nondeterministic completion order 決定候選真相。

### 6.3 Edit → check → observation → repair

Deep Agents 在每次 candidate write／edit／delete 後立即回 path、permission、exact-match 或 backend 結果。薄 middleware 可對本次變動 resource 做 JSON syntax check；跨 resource 的 JD／Evidence 驗證不塞進 filesystem Tool。模型完成一組編輯後呼叫 `check_candidate_document`，application：

1. 從目前 `run_id` namespace 取得 framework 真實 after-state；
2. 解析 canonical resources；
3. 回傳 syntax、path、unknown handle、linkage、Evidence 與 document invariant diagnostics；
4. 若可投影，計算 candidate revision／digest、semantic diff、action handles 與 atomic subgroup；
5. 把 completed／failed receipt 作為 Tool observation 送回模型。

editor-level 錯誤（path 越界、exact replace 不唯一、非法 JSON）回具體修復提示。暫時 completeness／linkage 缺口可留在 scratch，`check_candidate_document` 回 issue，讓模型用後續 edit 修正並重跑 check；final publication 必須引用最後一次成功 check receipt。這個 Tool 不接受文件 payload，也不寫 candidate／review／approved，只做框架不知道的 JD domain check。

final Structured Output 不重送候選內容，只明確表示要發布的最後 revision／digest／完整且有序 action handles。成功 check 後若又有任何 candidate mutation，receipt 立即 stale；unknown、失敗、stale、未引用、action 缺漏／重排或被後續 edit supersede 的 candidate 一律不得進 review queue。

### 6.4 Split／merge 與員工部分決策

Task／Duty／OPKS 都使用相同 editor。例：拆分 Task 是建立兩個 Task resources、調整 Duty／OPKS references、刪除舊 Task；不是呼叫 `split_task` 權限。

application 從 final semantic diff、entity references 與 `/candidate/<run_id>/review-groups.json` 驗證相依群組。不可分割的重組整組接受／修改／拒絕／延後；互不相依的變更可逐項裁決。員工決策後以「核准 baseline＋接受內容＋員工修改」重建並重驗；拒絕或延後一筆獨立 O 不會讓其他獨立 Task 消失，但若它破壞同 group invariant，該 group 不得部分寫入。defer 只保留 durable pending 狀態，不改 approved JD。

### 6.5 Evidence anchor

模型面前的 Evidence reference 只含：

- source 或 segment handle；
- exact quote；
- 只有同一 segment 內 exact quote 重複時才提供的 1-based occurrence；
- Skill／分析依據 references。

application resolver：

1. 在 immutable source revision／segment 原文做 exact match；
2. 唯一命中時產生並保存 `start／end／quote／source_revision`；
3. 零命中時回「quote 不存在」與可重讀來源；
4. 多命中時不得猜，要求更長 quote、較細 segment 或明確 occurrence；
5. 不為成功率偷偷改寫員工原話、標點或 Unicode normalization；若日後需要 normalized search，必須能確定映回原始 indices。

Deep Agents `read_file` 對文字 observation 加上的行號／continuation gutter 只是顯示資訊，不屬於 backend raw content。Tool 說明必須要求模型在 Evidence quote 排除 gutter；若先用 `grep` 找到線索，再以 `read_file` 讀相鄰原文後引用。resolver 永遠對 Store 中的 raw source revision 驗證，不能對格式化 Tool output 算 offsets。

deterministic verifier 與來源可信度政策保留；只移除模型手算 offset 的責任。

### 6.6 Pending 與跨回合

- 員工未審：核准 JD 不變，durable review bundle 保持 pending；
- 下次一般訪談：context 同時提供 approved baseline 與明示 pending，不把 pending 當事實；
- 員工要求繼續修待審稿：application 才把指定 pending bundle 投影成新 candidate base，並記錄 dependency／supersession；
- reject／edit-accept／direct edit 後：重驗下游 candidate，必要時標 stale；被拒絕內容不能由 framework merge 偷偷復活。

## 7. 最小驗證，不建立正式 eval 平台

施工採 TDD 並先保留目前失敗作回歸案例：

1. framework schema／tool surface：確認只出現六個 filesystem verbs＋一個無文件 payload 的 check Tool，無 host path／execute；量測 framework Tool optional／union 與 compact final output 的 provider 合併 grammar，不把 ADR 0061 的 final contract 放寬，也不假設成熟 Tool schema 必然通過；
2. permission：`/candidate/**` 可寫，其餘 namespace 寫入必拒絕，且無跨 document 資料；
3. editor：exact replace 零／多命中會回 actionable error，模型可在同 run 修正；
4. concurrency：平行 read 可通過、不同 entity mutation 可確定合併；同路徑或 ancestor／descendant mutation 必須整波拒絕並順序重試；check 與 mutation 同 wave 必須拒絕；
5. projection：create／edit／delete 後由 check Tool 形成 typed Duty／Task／OPKS；split／merge 由一般操作組合，成功 check 後再 edit 會使 receipt stale；
6. publication：candidate 未通過、未引用或 stale 時 review queue 為零；
7. lifecycle：成功發布與清除 active candidate 同 transition；同 run failure 可 retry；新一般 run 看不到／列不到／不能發布舊 scratch；
8. authority：接受／修改後接受／拒絕／延後與 atomic subgroup 行為不變；defer 不改 approved JD；
9. Evidence：中文、換行、重複 quote、錯 source、source correction、誤含 read-file gutter 都由 resolver 確定處理；模型 wire 無 `start／end`；
10. source parity：stable-ID read、更正鏈、只查 current source 的 lexical search、async Store access 與 document scope 都不能因 VFS 化而退化；
11. budget／offload：初始八次 model-step hard ceiling 能完成兩波 lookup＋edit＋check＋一次 repair＋recheck＋final，第九次拒絕；兩個 eviction threshold 均為 `None`，backend 不出現 `/large_tool_results`／`/conversation_history`；
12. 真模型 smoke：用 GPT-5.6 Luna 的互動基線驗證 edit→diagnostic→repair→publish，再以 owner 指定 profile 做一次窄 probe；只記效果、成本與問題，不提前建立正式品質 eval；
13. Browser：員工只看到 semantic diff／接受／修改／拒絕／延後，不看到 VFS JSON 或每次 tool call；accessible name 與鍵盤操作通過。

每完成 editor、Evidence、publication、review UI 任一獨立切片，都回看產品北極星，不等 Big-bang 最後才檢查偏移。

## 8. 風險與護欄

| 風險 | 護欄 |
|---|---|
| VFS 被誤當第二份 JD | run-scoped StateBackend；只有 final publication 建 review bundle，只有 employee command 寫 approved |
| 舊 run scratch 被列出、誤發布或拖大 active checkpoint | backend 只投影 current run；publish 原子清除；新一般 run deterministic 丟棄舊 scratch；歷史 retention 沿用 Saver policy |
| 模型寫任意路徑或讀其他文件 | CompositeBackend document scope＋BackendProtocol policy wrapper 為 hard boundary；public permission rule只作加強；tools allowlist＋無 host backend |
| 暫時 invalid candidate 汙染真實資料 | invalid 可留在 scratch 供修正，但 publication fail closed；不寫 review／authority |
| 文字檔格式取代 domain invariant | 每次 edit 後 Pydantic projection；final domain／Evidence／read-set verifier 完整保留 |
| 工具數比現行多 | 移除四個自寫來源／候選 Tool，以六個成熟、互斥 filesystem verbs＋一個無 payload 的 domain check 取代；實測合併 schema，不用臆測 |
| native provider 功能造成 lock-in | 第一版只用 Deep Agents provider-neutral tools；native editor 僅允許日後 adapter，內部 candidate contract 不變 |
| framework 新版本改介面 | 鎖版、characterization tests；`deepagents` backend／tool schema 不滲入 public API 或 authority model |
| 平行 Tool call 競爭寫同一 resource／check 讀到 wave 前狀態 | 平行 read／不同 entity write 可保留；重疊 path mutation 整波拒絕；check 與 mutation 不得同 wave，回 actionable sequential-retry error |
| VFS 取代來源 Tool 後遺失更正鏈 | source backend 明示 current／lineage projection；一般 grep 排除 historical revision；source parity tests |
| framework 自動 offload 形成隱藏 namespace／原話副本 | 關閉兩個 eviction threshold；source／check result application-bounded並帶 omitted count；characterization test 凍結無隱藏 route |
| 新 edit／check 拓撲超過舊五步上限 | successor ADR 明確取代初始五步 profile；八步 hard ceiling＋總 Tool／token／cost／elapsed／recursion budget＋成功／耗盡測試 |

## 9. 來源與採用理由

- [OpenAI — Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch) — model diff、harness application、in-memory workspace、result feedback、atomicity。
- [OpenAI — Codex code review](https://learn.chatgpt.com/docs/code-review) — working-tree diff 與 stage／revert／commit 分界。
- [OpenAI — Codex environments](https://learn.chatgpt.com/docs/environments/modes) — worktree isolation。
- [Anthropic — Raising the bar on SWE-bench Verified](https://www.anthropic.com/engineering/swe-bench-sonnet) — 最小 scaffold、exact string editor、actionable retry。
- [Anthropic — How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) — session、worktree、checkpoint、permission 與可恢復編輯。
- [Anthropic — Checkpointing](https://code.claude.com/docs/en/checkpointing) — editor changes 與 session-level rewind。
- [Anthropic — Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — 少量高影響 Tool、schema／error ergonomics、meaningful handles。
- [Anthropic — Managed Agents](https://www.anthropic.com/engineering/managed-agents) — brain／hands／session 解耦與穩定 interface。
- [Anthropic — Citations](https://platform.claude.com/docs/en/build-with-claude/citations) — API-derived valid pointers、transcript block indices、Structured Outputs 相容限制。
- [Anthropic — Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — strict tools＋JSON output 合併計算的 20 tools／24 optional／16 union 公開上限與內部 grammar 限制。
- [Deep Agents — Backends](https://docs.langchain.com/oss/python/deepagents/backends) — State／Store／Composite backend、virtual filesystem 與 backend protocol。
- [Deep Agents — Permissions](https://docs.langchain.com/oss/python/deepagents/permissions) — built-in filesystem tools 的 read／write path policy。
- [Deep Agents — Context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering) — filesystem tool prompts、offloading 與按需讀取。
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) — checkpointed pause／resume 與 durable human input。
- [LangChain — Tools](https://docs.langchain.com/oss/python/langchain/tools) — ToolNode 平行執行、state update 與 error handling。
