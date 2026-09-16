# B1／B2 模型與 Runtime 參數權責審核

- 日期：2026-09-17
- Topic：`JD-R002 / MEM-L001`
- Stage：G4 設計收斂／G7 前置審核
- 範圍：B1／B2 訪談證據選擇、來源讀取與語意工具；不改 Memory 分層、publication、Prompt 分工或 provider

**2026-09-17 施工狀態：**下列目標契約不變。引用施工 Tasks 1–4 已完成 source owner／port／adapter、B1 checkpoint registry 與 B1 evidence 分配；§3.2 中 B1 的第 1 項與 B1 finish 已修正。B2 exact-source keys、B2 rework／finish、bundle owner-order 再驗證及 provider request strict 證據仍待 Task 5／6。

## 1. 結論

產品需要的是「引用按 canonical 訪談先後顯示，模型能選對完整問答，而且正式資料不會因模型抄錯地址、順序或分頁位置而損壞」。這個效果**不要求建立持久的全域 `turn_sequence` 欄位**。

第一版採下列契約：

1. source owner 仍以現有已簽名 `purpose="source"` reference 固定及讀取完整訪談交換，並以 canonical conversation 自身的 message order 提供 ordered source list／order proof。
2. Runtime 將本 attempt 已提供或已讀的來源組成**明示 `oldest_to_newest` 的 ordered evidence blocks**，每筆配置短、attempt-scoped 的 `evidence_key`（例如 `E1`、`E2`）。
3. `evidence_key` 只是本 attempt 的模型選擇代號，不是全域輪次、時間、持久 citation 或排序 authority；對照表必須進同一 checkpoint，resume 後不能換號或指向別的來源。
4. 模型只能從已展示的 `evidence_key` 做「哪些來源支持哪個案例」的語意選擇；Runtime 將 key 解析為真正 `source_reference`，驗證文件、lineage、purpose、已提供／已讀、去重及 canonical order。
5. 正式 `CaseArtifact`／manifest 仍只保存已驗證的 signed references；展示或再次送模時由 source owner 重新按 canonical order 解析，不能相信模型傳入順序，也不保存 `E1` 之類暫時 key。
6. 分頁 offset／cursor 由 Runtime checkpoint 保存。模型只要求「讀這筆 evidence」或「繼續讀」，不填數字 offset，也不回傳 long signed reference。

這撤回先前把 `turn_sequence` 寫成必要產品欄位的過早結論。若實作內部為排序或測試使用 ordinal，它仍是 owner／Runtime 私有推導值，不成為模型參數、持久引用格式或跨版本身分。

## 2. 官方資料能支持到哪裡

查閱日皆為 2026-09-17。

### 2.1 共同原則

- OpenAI Function Calling 要求工具可預測、避免可互相矛盾的參數，並明確建議「已由應用知道的參數不要再要求模型填，由程式帶入」。`strict` 可以保證呼叫符合 JSON Schema，但不替應用驗證資料範圍與業務語意。[OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling)
- OpenAI Structured Outputs 明示：即使輸出符合 schema，內容仍可能出錯；應改善指令／例子、拆小任務並在應用端驗證，不能把 schema 合法等同語意正確。[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- Anthropic 同樣要求清楚描述工具與每個參數、為複雜輸入提供例子，並減少容易混淆的工具選擇；strict tool use 只保證名稱與輸入符合 schema。[Anthropic Define Tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)、[Strict Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)
- Anthropic 對 transcript／custom content 的 citation 讓應用先決定 ordered content blocks，模型回傳 block index；這支持「應用擁有證據單位與順序，模型只選已提供項目」，但不要求 Caliburn 持久保存全域輪次。[Anthropic Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- OpenAI Responses 的 input-items list 將 item ID、cursor 與 `asc/desc` order 分開表示，支持「身分、分頁與排序是不同責任」，不是以 ID 或時間戳猜順序。[OpenAI List Input Items](https://developers.openai.com/api/reference/java/resources/responses/subresources/input_items/methods/list)

### 2.2 本案取捨，不冒稱廠商固定 schema

大廠共同方向是：應用掌握資料與狀態，模型只做必要的語意選擇；工具 schema 要窄，輸入要可驗證，服務端必須 fail closed。沒有任何官方資料要求「訪談一定要有全域輪次欄位」或指定 `evidence_key` 這個名稱。

因此，ordered blocks＋attempt-scoped key 是 Caliburn 對共同原則的最小映射。它兼顧：

- 不讓模型抄長 signed token、UUID、offset 或時間戳；
- 模型仍可指出同一來源支持多個案例，或把多個來源分配給同一案例；
- ordered array 本身表達前後關係，key 不承擔排序語意；
- checkpoint 能穩定恢復同一模型可見選項；
- artifact 繼續使用既有可驗證 reference，不建立第二套 citation authority。

## 3. 已核對的現況與缺口

### 3.1 已正確由 Runtime 擁有

現有 B1／B2 已把以下資料留在 Runtime：`document_id`、base publication revision／Memory version、new case／understanding ID、路徑、digest、operation identity、checkpoint state、read-before-write、step limit、publication 與 CAS。`parallel_tool_calls=False` 也已在共用 OpenRouter model factory 設定。

### 3.2 缺口與目前施工狀態

1. **B1 已完成：**固定 `window` 不再自動附到 create／revise／split／merge；模型分配真正支持各案例的 source exchanges，Runtime 解析及 canonicalize。
2. **B2 待 Task 5：**`read_case_source(case_id, source_reference, offset)` 仍要模型重填 long signed reference 與數字 offset；這兩項 Runtime 已可從已讀 case 與 checkpoint 知道，不應交模型。
3. **B2 待 Task 5：**`request_case_rework` 仍要求 `case_id＋source_reference`，重複了已讀證據關係；應改用已綁定 case/source 的 `evidence_key`＋語意理由。
4. **B1 已完成、B2 待 Task 5：**B1 finish 已改為零參數並由 Runtime 計算 outcome；B2 仍須做相同責任收斂。
5. 目前 B1／B2 `@tool` 未在這條組裝路徑明示 provider strict binding；Pydantic／Python 端驗證與 `extra="forbid"` 不等於 wire 上已證明 strict tool use。施工時須檢查實際 request；即使 provider strict 可用，也不能移除 Runtime 語意驗證。
6. **port／adapter 已完成、B2 consumer 待 Task 5：**App adapter 已能提供 exact `purpose="source"` paging；B2 仍須改用這個接點，不能只改模型 schema。

## 4. 參數分配準則

判斷一個參數是否應由模型填，只問一件事：**這個值是否必須由模型根據語意作選擇？**

| 類型 | Owner | 原因 |
|---|---|---|
| 要建立、修訂、拆分、合併、淘汰哪個語意項目 | LLM | 這是案例／工作理解判斷 |
| 案例／理解正文、diff、guide route note、rework reason | LLM | 這是語意產物 |
| 哪些已展示證據支持哪個案例、哪些案例支持哪個理解 | LLM | Runtime 不能靠關鍵詞代替專業判斷 |
| 已存在的 `case_id`／`understanding_id` | LLM 從 Runtime 提供集合中選 | Runtime 知道合法集合，但不知道模型要操作哪個語意目標 |
| `document_id`、base version／revision、attempt／job／operation ID | Runtime | 已知 scope／並行控制，不是語意決策 |
| 新 case／understanding ID、路徑、digest、時間 | Runtime | 身分與儲存不變量 |
| signed source reference、lineage、purpose、canonical order | Runtime／source owner | 不可由模型製造或推測 |
| offset、cursor、下一頁位置、已讀集合 | Runtime checkpoint | 程式狀態；要求模型重填只會增加錯誤 |
| 去重、排序、集合差異、CAS、publication receipt | Runtime | 可確定計算與原子保存 |
| `changed/no_op` | Runtime | 可由 stage 差異計算；模型只需表示「完成」 |

## 5. 目標工具契約

下列是施工責任，不要求一次重寫所有工具名稱；效果與參數 owner 不得反轉。

### 5.1 B1

| 動作 | 模型提供 | Runtime 提供／處理 |
|---|---|---|
| 讀案例 | 從 guide 選 `case_id` | 回正文與 ordered evidence blocks；登記可選 keys |
| 瀏覽訪談 | 呼叫無 offset 的受控讀取動作 | 從 checkpoint cursor 回下一頁 ordered blocks；保存 key→reference 對照 |
| create | `content`、`route_note`、完整 `evidence_keys` | 配新 ID、解析／排序 references |
| revise | `case_id`、`diff`、可空 route note、`add_evidence_keys`／`remove_evidence_keys` | 未提及引用保持不變；拒絕同時 add/remove 同一 key、空結果或範圍外 key |
| split | `case_id`、每個 replacement 的完整正文／route／evidence keys | 配新 IDs；驗證每個 replacement 至少一筆來源，不把舊來源自動複製到全部子案例 |
| merge | `case_ids`、正文／route、對既有來源聯集的 add/remove 語意差異 | 先建立已讀案例來源聯集，再套用差異、驗證並 canonicalize；避免模型重抄整組而漏掉來源 |
| retire／route | 語意目標及必要 route 文字 | 不要求來源、版本或新 ID |
| finish | 零參數完成動作 | 自行計算 `changed/no_op`，檢查 guide／證據／必讀集合後完成 stage |

split 不能使用 merge 的「聯集保留」捷徑，因為拆分時每筆來源屬於哪個 replacement 本身就是語意決策。若舊來源沒有分配到任何 replacement，工具須要求模型明示捨棄並給出原因，不能因漏填而靜默遺失；精確欄位在紅燈測試中以最少必填方式決定。

### 5.2 B2

| 動作 | 模型提供 | Runtime 提供／處理 |
|---|---|---|
| 讀案例／理解 | `case_id` 或 `understanding_id` | 驗證 candidate/current/read scope，回正文與 bindings |
| 讀案例原話 | 已展示的 `evidence_key` | key 已綁 case＋source；Runtime 使用 checkpoint cursor 分頁，不收 `source_reference`／`offset` |
| request B1 rework | `evidence_key`＋具體 `reason` | 從 key 取得 case/source，驗證確實已讀並保存正式 issue |
| create 理解 | `content`、完整 `supporting_case_ids`、`route_note` | 配新 ID、驗證每個 case 已讀且 current |
| revise／revalidate | 語意目標、必要正文 diff、support add/remove 差異、可空 route note | 未提及支持案例保持；正文未改可只重驗／調整 bindings，精確 digest 由 Runtime 更新 |
| split | 每個 replacement 的完整 content／supporting cases／route | 配新 IDs 並驗證所有 supporting cases 已讀 |
| merge | 目標 IDs、正文／route、對既有 supports 聯集的 add/remove 差異 | 保留未移除支持，解析 exact case digests |
| retire／route | 語意目標及必要 route 文字 | 不讓模型填版本、digest 或 replacement ID |
| finish | 零參數完成動作 | 自行計算 outcome 並驗證 required cases／understandings 已處理 |

## 6. 「基本上不允許失敗」的工程定義

不能誠實承諾機率模型永遠不會做錯語意判斷；strict schema 也只保證形狀。此處的可驗收標準是：

1. **零靜默破壞：**未知 key、跨文件、未讀 evidence、重複／矛盾差異、無來源案例、dangling binding、stale base 或錯序都不能進 stage completion／publication。
2. **錯誤不產生部分效果：**工具失敗時 stage 不變；不先套一半再要求模型補救。
3. **模型不管理可確定資料：**能由 Runtime 推導的值不進 schema，減少「格式合法但內容抄錯」。
4. **語意錯誤有第二層攔截：**B2 必須能沿案例 evidence 回查；發現會影響工作理解的 B1 錯誤時走既有有界 `case_rework_required`，不繞過上游發布。
5. **不確定就不發布：**有界修正後仍無法滿足契約，結果是 blocked／failed 且正式 head 不變，不採猜測、fallback latest 或強制覆蓋。
6. **以反例驗收，不以 schema 全綠代替：**至少覆蓋 key 調包、resume 後 key 漂移、跨 case 共用來源、split 漏配、merge 遺失、錯 cursor、來源順序顛倒、原話與案例不一致及 provider 未實際 strict 的情況。

## 7. 下一步

來源 owner／port／adapter 與 B1 工具已完成。下一步直接依[引用施工計畫](../plans/2026-09-17-interview-evidence-citations.md) Task 5 修改 bundle 與 B2 exact-source read／rework／finish，再做 Task 6 收尾驗證；不重做 Tasks 1–4。此切片仍不接 publication、dispatcher、C、compaction、JD writer、UI 或付費模型。
