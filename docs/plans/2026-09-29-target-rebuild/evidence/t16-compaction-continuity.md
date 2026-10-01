# T16：原生壓縮、再壓縮與接續的有限驗證

- 日期：2026-10-01；基準 `63c0e5d6`；**有限 adapter 驗證已完成，T16／T17 整體未完成**。§1–3 保留執行前限制及首輪停止原因，§4 是實際結果。
- 只補 [T06 §20](t06-agent-execution.md#20-真-compact-協定預檢2026-09-30-恢復後) 未驗的加密 reasoning＋工具結果壓縮、完整 C 接續及含 C 的再次壓縮。T16／T17 仍未完成，不重跑長訪談、不改產品提示或門檻。
- 官方 [standalone compact](https://developers.openai.com/api/docs/guides/compaction#standalone-compact-endpoint)要求送入窗口仍可容納、完整 output 原序續接；[stateless reasoning](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-without-stored-responses)要求保留原生項目。2026-10-01 取得的 [Luna 規格](https://developers.openai.com/api/docs/models/gpt-6-luna)列 input 922,000、context 1,050,000、output 128,000；不是帳戶 TPM 保證，也不把 Astra 範例等同 Luna 實测。

## 1. 授權、資料與停止條件

沿 Goal 有界直連合成測試授權。使用既有 `create_responses_client`／`ResponseRequest`／序列化 adapter，`gpt-6-luna`、medium、`store=false`、`all_turns`、`truncation=disabled`；不使用 previous_response_id 或 server-side 自動壓縮。只由既有安全 loader 讀 `apps/api/.env` 的 OpenAI key；不讀取職務 DB、Demo、私人資料或其他環境設定。

| 限制 | 本批上限 |
|---|---|
| 外送 | 3 次 create、2 次 compact、最多 6 次 count（其中至多一次只為校準合成大視窗長度）；序列執行、零 SDK／應用重試 |
| Token | 大視窗 count 校準目標 128,000–160,000；compact 前必須落在此區間。create input ≤32,000、output ≤2,048；第二次 compact input ≤32,000 |
| 時間／費用 | 每請求 120 秒、整批 600 秒、管理預算 US$1；不是正常產品金額 gate。傳輸錯誤、超量或協定異常立即停止，不以換模型／刪減 C 通過；公開答覆的事實檢查另記，不以字面比對代替代理的逐項語意審讀 |
| 保存 | ignored `.research-tmp/eval/compaction-continuity-20261001.jsonl` 獨占建立；只留安全型別、雜湊、usage、公開合成答覆與判定，不輸出／保存 opaque content 或 key |

資料完全由探針常數建立：合成庫存工作規則＋索引化虛構紀錄。首個小請求產生真工具呼叫，配對本機生成的合成結果；不用偽造 provider call ID、reasoning 或成功產品提交。只在 count 校準階段可調整尚未 compact 的合成紀錄數，不改真模型已返回的項目。

## 2. 檢查內容與不宣稱

1. 記錄原生 R 是否包含加密 reasoning，不把每次必有 reasoning 當有效回應條件；JSON 往返一致，完整工具配對窗口經 exact count 後交給 compact。有實際 reasoning 才計入該項覆蓋，沒有就明示未驗。
2. 完整 compact output 經產品 serializer 往返後直接承接，再追加新的合成頻率更正。讀模型公開答覆，檢查季度頻率、主管核准及當日升級三項，未知／錯誤如實判定。
3. 將 C 加該次 user／原生 R 的完整窗口再 compact；完整返回接下一次查詢，檢查上述三項是否仍成立。
4. 分別記 count、compact、create 的時間與 usage；模型協定接受與保留三個已知事實分開判定。原件不留，使用 hash 確認承接沒有自行裁剪。

這是 adapter 級容量／接續 probe，刻意在隔離腳本中顯式 compact，**不是**產品 128K／272K 自動觸發或完整 A Turn 的試驗；時點、取消與可靠採用沿既有 T06／T12 測例。不以此驗 272K／512K 大視窗、所有細節無損、Memory 分析、引用選擇、PDF 或完整 JD 品質。研究探針沒有新產品行為，不聲稱 TDD 修復。

## 3. 首輪停止與一次補跑界線

首輪 `2026-09-30T18:08:28Z`（本地 10-01）只執行 count 與 create：input 132、output 17、reasoning 0；模型正常產生一個 `function_call`，原生項目 JSON 往返相等。探針錯誤地要求這次簡單工具呼叫必有 encrypted reasoning，故在本機 `ValueError` 停止；未傳工具結果、未 compact、未寫業務資料。這不是產品失敗，也不能宣稱完成 reasoning 覆蓋。

補跑只移除這個過嚴前置條件，改逐次記錄 reasoning 實際出現情況；完整原生 output 仍不刪減。字面事實比對改名 `exact_values_match`，與代理的逐項語意審讀分開。原首輪紀錄保留；因未保留 opaque 原件，補跑是新的生成，不冒充恢復首輪。

**只允許一次新批次**：沿 §1 的單批限額，獨占輸出 `.research-tmp/eval/compaction-continuity-followup-20261001.jsonl`。連首輪計算最多 4 次 create、2 次 compact、7 次 count（13 次 HTTP），管理預算仍共 US$1；補跑協定／容量失敗便停止，不追加第三批。沒有任何產品設定變更。

## 4. 實際結果與重現邊界

補跑於 `2026-09-30T18:12:31Z–18:12:48Z` 結束（本地 10-01），退出碼 0、零重試；連首輪共 13 次 HTTP，未超 manifest。使用 OpenAI SDK `3.20.0`、LangGraph `1.2.12`、Pydantic `2.13.5`；模型仍 `gpt-6-luna`。沒有啟動／修改 Demo、資料庫或正常產品的容量政策。

| 階段 | 實際 input／output tokens | 結果 |
|---|---:|---|
| 首輪與補跑起始 create | 各 132／17 | 正常 function call，reasoning 0；完整原生 output JSON 往返相等 |
| 大視窗 count | 112,703 → 141,878 | 只校準一次：1,500 → 1,889 筆合成例子；全體規則未改 |
| 第一次 compact | 141,777／169 | 4.445 秒；返回 `[message, compaction]` 共 2 項，完整 output 原序承接 |
| C＋新更正後 create | 331／75 | 2.680 秒；`reasoning + message(final_answer)`，加密 reasoning 存在，reasoning tokens 36 |
| 第二次 compact | 307／111 | 2.018 秒；輸入含第一次 C、新 user、真 reasoning 及 message；返回 `[message, message, compaction]` 共 3 項，完整承接 |
| 第二次 C 後 create | 284／37 | 2.200 秒；正常 final_answer，三項事實與前次相同 |

count 使用完整 Responses 請求（含 instructions／tools）；compact 使用原 input window。因此 141,878 與 141,777，以及第二次 count 408 與 compact 307 的差距不是遺失訪談；兩者計量範圍不同。

兩次公開答覆都為：

```json
{
  "cadence": "Inventory is counted quarterly.",
  "approval": "Only the supervisor approves inventory adjustments.",
  "escalation": "Unresolved shortages are escalated the same day."
}
```

**主代理逐項對照合成事實：兩次答覆各 3/3 正確，未經人工或領域專家評分。**季度更正已吸收，原核准責任與當日升級仍保留。探針的 `exact_values_match=false` 是因預期短字串與完整句子的字面不同，不能當作語意失敗，也未事後改 expected 重新付費。這不是一般 JD 品質評分，更不是所有 1,889 筆細節無損；測例本來只要求三項全體規則。

加密 reasoning 的覆蓋只成立於**第二次 compact**：第一次的工具呼叫沒有 reasoning，不捏造原件補入；第二次確實含模型原生 reasoning，未讀取 opaque 內容。兩次 compact output 的 JSON 往返均逐值相等；這證明 App 未自行丟項，不代表壓縮在語意上無損。

所有已回傳 create／compact usage 合計 input **142,963**、output **426**、cache read/write 都為 0。按 repo 既有 `openai-standard-2026-09-30` 短窗口 Standard 單價推算約 **US$0.0145093**；這是已觀測 token 的估算，不是供應商帳單，也不把 count 端點未回傳的帳務資訊當成已確認零費用。

### 原件識別與重現

ignored 探針 `.research-tmp/eval/probe_compaction_continuity.py` SHA-256：`78342e546ddb64df31f0e80e8c81935bc31ecc8cce92148ce2bedbda3d3bd5c6`。instructions JSON 雜湊 `2bab37412877938b0aabe6910de902c822a8b869084cf052c39b20f92ff1ffb6`；tool JSON 雜湊 `a821de664d24a67c72f302b368d65d5d36c1c022a56318c13bc7880df98ec487`。本機保留安全 JSONL，不保存 opaque provider 原件，因此不能憑 response ID 逐位還原原 C；重現是新的有界生成，不保證逐字相同。

探針流程可依 §1–2 重建：零參數合成讀取工具 → 實際 call → 1,889 筆合成庫存例子工具結果 → 完整 compact → 追加季度更正 → 完整 compact → 再問三項規則。原測試 prompt 明示只保留全體規則，不需記每筆例子。以下為本次執行命令，不可覆寫原紀錄；再次執行須另列新批次目的與限額：

```powershell
# apps/api
./.venv-target/Scripts/python.exe -B ../../.research-tmp/eval/probe_compaction_continuity.py --key-file .env --output ../../.research-tmp/eval/compaction-continuity-followup-20261001.jsonl
```

沿本次有限驗收另跑既有 `test_request_capacity.py`、`test_context_compaction.py` 及 [T15 §6 的安全／保留 12 例](t15-capacity-measurements.md#6-t15-完成對照2026-10-01-有界收尾)：**44 passed，4.98s**；`tests/contracts/test_response_serialization.py` **11 passed，0.69s**。本片沒有產品行為修正，不聲稱新 TDD，也不重跑全套。

### 收斂

已補足大工具結果 compact、完整 C 接續，以及 C＋真 reasoning 再 compact 的協定反例；本片到此停止，不為 coverage 再造測試平台。仍未驗 272K／512K 真視窗、實際 A/B 自動觸發下的全旅程及跨主題資訊保留品質；沿原任務判斷必要性，不宣告整體 gate 通過。已知 JD 局部更正來源保留問題仍由 T14／T17 處理，不能由這個合成三事實案例抵銷。

## 5. 共用 Runtime 的 272K／512K 有界補驗

2026-10-01，基準 `de4d0bc8`。前批已關閉，不重跑原 adapter 探針；本批只驗既有 `run_response_loop` 的完整 Step 間 272K 路由，以及 `prepare_context_history` 的 512K 工程配置。2026-10-01 重核本頁列出的官方 compact／Luna 規格：容量仍如前述；完整返回不得裁剪。測試使用同一產品 runtime 和 serializer，**InMemorySaver 僅驗本程序接續，不冒充 PostgreSQL 耐久、取消、A/B 完整旅程或品質 gate**。

### 執行前 manifest

- 全合成常數，沿前批庫存規則與資料生成器，沒有讀取職務 DB、私人訪談或 Demo。安全 loader 只載入 `.env` 中 OpenAI 憑證。模型 Luna、medium、output 2,048；store=false、all_turns、truncation disabled，零 SDK／應用重試。
- 最多 **3 create、2 compact、6 count**，序列；每請求 120 秒、整批 600 秒；管理預算 **US$1**。create input ≤32K；首次工具結果固定 3,800 列、完整 count 必須在 272K–320K；獨立輪前歷史 fixture 為 6,900 列、必須在 512K–570K。超出便停止，不盲目外送 compact。兩者均小於模型硬容量，不能據此推定帳戶 TPM 足夠。
- 首個模型原生工具呼叫 → 合成工具結果 → **Runtime 自動**觸發 compact → 完整 C 重計數 → 模型答覆。再重入已完成 loop，應不新增 HTTP。第二個獨立合成 fixture 沿用真 call 形狀但使用新合成結果，交輪前準備 → count 判門檻 → compact → 同準備重入不新增 HTTP → 追加季度更正 → 回答三項規則；不改前一執行的已存歷史。
- 任一傳輸、限流、協定、容量或本機錯誤立即停整批；不換模型、不縮門檻、不增重試。事實正確與協定接受分開審讀。若 272K 已受阻，不再支付 512K 嘗試。未測帳戶升級、DB 交易、role maps 或 JD。
- ignored 探針 `.research-tmp/eval/probe_runtime_compaction.py`；獨占輸出 `.research-tmp/eval/runtime-compaction-20261001.jsonl`。僅安全 usage、型別、雜湊、公開合成答覆、呼叫數；不保存 opaque 原件、秘密或原始 SDK 錯誤。以下另記實際結果，不回寫前置限制。

### 實際結果：272K 路由成立，遠端壓縮限流而停止

`2026-09-30T19:49:03Z–19:49:10Z`（本地 10-01）執行；退出碼 1、零重試，共 **2 count、1 create、1 compact**。沒有進入 512K 階段，沒有取得 C 或壓後答覆。

| 檢查位置 | 實際觀察 | 判定 |
|---|---|---|
| 原生模型請求 | count 133；create input 133／output 17，完整 function call，JSON 往返相等 | 起始 native call 可用；本次沒有 reasoning |
| 完整 Step | 真 call 與 3,800 列合成工具結果配對；完整 request count **285,204** | 超過272K，仍低於模型硬輸入上限 |
| Runtime 下一請求路由 | 自動進 `run_context_compaction`，未直接發第二次 create | 本次真正驗到共用 Step 間門檻路由，不只是 adapter 手動呼叫 |
| Compact | 約3.008秒後 `RateLimitError`，HTTP **429**，安全分類 `transient_service` | **未通過**大窗口遠端壓縮；按 manifest 立即停整批 |
| 512K、C 重入、壓後更正 | 均未執行 | 不從離線結果或前批142K推定通過 |

這次只保留安全錯誤分類，沒有保存 SDK 原始 body／headers，故無法單憑429判定是每分鐘暫時額度、單請求大於帳戶 TPM 或其他細項。先前任務記過200K帳戶限額，但不能冒充本請求的遠端確認；也不能把模型922K輸入能力等同帳戶可送922K。**不修改已確認272K政策，不以刪歷史、換模型或反覆付費探測解決。**日後確有帳戶容量證據或新失敗診斷需求，再以新 manifest 驗該缺口；本批關閉。

已回報 usage 僅首個 create：input133／output17，按既有本機 Standard 費率估 US$0.0000218。失敗 compact 無 usage、count 無帳務回傳，不把它們當免費或將上述視為完整帳單。原件只存程序內 InMemorySaver，本程序已結束；沒有持久產品保存、DB／Demo 操作或進行中工作。這是驗收受限，不是新增產品錯誤修補。

腳本 SHA-256：`92846b3b4f2c998b6cbcaa6f684ffa14ca531fbee24c00837b821e5888dd79fb`；安全 JSONL `b6f470fe0505e7c9c5a31f114c479eb50e944d764bf31266531cb6eebbd0ebbf`；instructions `6a99e2dfde402a22439c65d18e14654b58dd64293faf9535c9f7c2a4c0defc13`；tool 與 §4 相同。重現須沿本節 manifest 另建獨占輸出，不能覆寫或再次使用本批：

```powershell
# apps/api；下列是已執行命令，不是再次外送授權。
./.venv-target/Scripts/python.exe -X utf8 -B ../../.research-tmp/eval/probe_runtime_compaction.py --key-file .env --output ../../.research-tmp/eval/runtime-compaction-20261001.jsonl
```

受影響既有容量／完整 C／原生序列化回歸：`tests/unit/test_request_capacity.py`、`tests/unit/test_context_compaction.py`、`tests/contracts/test_response_serialization.py` **43 passed，1.43s**（`python -X utf8 -B -m pytest ... -q -p no:cacheprovider --tb=short`）。探針 Ruff E/F/I 通過、import／CLI 說明可載入。沒有產品程式變更，不製造 TDD 宣稱；離線43例不抵銷本次真provider未通過。

## 6. 429 的帳戶容量診斷（2026-10-01）

基準 `d6326bf6`；Owner 已固定產品 Luna。本片不重送 §5 的 285K 請求，只補失敗時沒有保存的限流線索。官方[限流指南](https://developers.openai.com/api/docs/guides/rate-limits)區分模型 context、帳戶／project TPM、長 context 的獨立限流及帳務 429；[HTTP 診斷欄位](https://developers.openai.com/api/reference/overview#debugging-requests)可取得實際 limit／remaining／reset。小請求所得欄位只能代表該次適用額度，不能冒充先前大視窗失敗的完整原因。

**外送前 manifest：**只用不超過 2,000 字元的合成庫存規則，最多 1 次 Luna／high create（output ≤512）及 1 次完整窗口 compact，零 count／重試；每請求 60 秒、整批 120 秒、管理預留 US$0.05。使用現有 direct SDK client／serializer、store=false／all_turns，金鑰只經既有 loader 載入；不讀職務 DB、不外送私人資料。只保存 status、數值限流 headers、安全錯誤分類及 usage，不保存完整 headers、組織 ID、原始錯誤 body 或 opaque 內容。第一個錯誤即停止；沒有欄位就如實記未知，不擴大請求量。ignored `probe_luna_rate_headers.py` 獨占輸出 `luna-rate-headers-20261001.jsonl`，不改產品政策或帳戶設定。

### 結果與下一步

`2026-10-01T00:19:19Z–00:19:23Z`（本地 08:19）完成，退出碼 0。create 及 compact 均 HTTP 200，兩次 headers 一致回報 `x-ratelimit-limit-requests=500`、`x-ratelimit-limit-tokens=200000`；未回 project-token 欄位。沒有重試或重送 §5 大視窗；compact 完整回傳 message＋compaction。usage 合計 input 117、output 83，按既有 Luna Standard 費率估 **US$0.0000532**，非帳單。

**可以確認：**這把金鑰當次小請求適用的 token 限流為 200K，生成與壓縮相同。**不能確認：**先前 285K 失敗的精確細項，以及長 context 是否有另一組可用額度；官方明列長 context 可有獨立限流，小請求 headers 不代替大視窗成功證據。模型硬容量不是帳戶 TPM；不以增加重試、等待或換模型聲稱已解決。

目前 A 輪前 128K、Step 間 272K 與 B 輪前 512K 接線未變。已向 Owner 提出按配額校準候選：A 輪前仍 128K、B1／B2 輪前 128K、Step 間 160K，**待確認／未採用／未驗證**。這是提前使用既定原生 compact，不是裁切歷史或自製摘要；也不能保證任意單次巨大工具結果一定可壓縮。另一選項是保留原政策，由帳戶擁有者確認／調整容量；本代理沒有修改帳戶或擴大費用。

這次取得了新的容量證據，T16 仍未完成；不可把低 token 的 200 當成 272K／512K 通過。其餘品質及交付工作可繼續，不因等待門檻決策重跑相同限流測試。

原件識別：ignored `.research-tmp/eval/probe_luna_rate_headers.py` SHA-256 `99c419aae9d29ee561398963f12f722239d87203cdbd692c9fd31b97d19c9b49`；安全結果 `.research-tmp/eval/luna-rate-headers-20261001.jsonl` SHA-256 `7cd970196c769ebf3a2cc20615d0fa5856d08764274fc05fb3d67d978485b29a`。腳本執行後只有排版調整，Ruff E/F/I 與 format check 通過。沒有模型設定或產品程式變更；本批不重跑，也不將未決門檻校準混同已確認的 Luna 選型。

## 7. 200K 額度下的輪前準備校準（2026-10-01）

基準 `c9a1c55a`。本片不重送 285K／512K，不改產品門檻；只驗共用 `prepare_context_history` 在既有 A 128K（亦為 B 待確認候選）能否接住 160K–180K 完整歷史，保存全部 C，重入不重付壓縮，再追加新資料／更正。Step gate 目前在 `request_capacity.py` 固定 272K，**不 monkeypatch 為160K後宣稱產品接線通過**；中途較低門檻仍待決策與相應實作驗證。

官方依據重核：[限流](https://developers.openai.com/api/docs/guides/rate-limits#how-do-these-rate-limits-work)區分 project TPM 與長 context 配額；[standalone compaction](https://developers.openai.com/api/docs/guides/compaction#user-journey-for-standalone-compaction)要求原窗口適合模型並完整承接返回。200K 不等於任意時間都能送滿200K；本例也不證明並行請求或任意工具回傳大小都適用。

### 執行前 manifest

- 只用合成庫存規則與2,200列生成資料，零職務 DB／Demo／私人資料。Luna／high、store=false／all_turns、直連 SDK，沒有自製摘要、裁歷史或更換 provider。
- 最多 **2 create、3 count、1 compact**，零重試、串行；create input≤32K、output≤8,192，待壓歷史實際 count 必須在160K–180K；不在範圍即停止，不另調資料補跑。單請求120秒、整批420秒、管理預留US$0.25；失敗即停止，不增加次數。
- 真模型產出工具呼叫→合成工具結果→原輪前準備 Graph（門檻128K）→完整 C。以同一準備身分重入，應不新增HTTP；其後精確追加一則合成App資料與一則季度更正，再生成答覆。核對原歷史未改、C完整保留、角色／順序及三項規則（季度、主管核准、當日升級）。不鎖答案逐字或要求模型每次有reasoning。
- 使用 InMemorySaver，只驗同程序Graph保存／重入及真provider接續，不冒充PG耐久、取消恢復、真A/B分析、272K／512K或160K Step自動路由。沒有產品程式變更，不宣稱TDD。
- 輸入夾具止於完整工具往返，沒有前一輪正式 final；本例刻意直接呼叫共用準備函式，**不驗證產品呼叫端只在合格 Turn 交界啟動的資格判斷**，也不能算真實已完成訪談的輪前端到端驗收。
- 探針 `.research-tmp/eval/probe_preparation_quota.py`，獨占輸出 `preparation-quota-20261001.jsonl`；無 `--execute` 只列manifest、不讀金鑰或外送。保存安全usage、類型、雜湊及公開合成答覆，不保存原始錯誤／headers／opaque內容。結果另記，不回寫本節上限。

### 結果與證據界線

`2026-10-01T02:40:39Z–02:40:48Z`（本地10:40）完成，退出碼0。實際2次create、3次count、1次compact，零provider重試；程序已結束，未改產品設定或任何職務資料。

| 檢查 | 實際結果 |
|---|---|
| 完整待壓歷史 | count **165,204 tokens**；原生工具請求與合成工具結果正確配對 |
| 128K準備門檻 | `prepare_context_history` 真正路由compact；約2.514秒取得完整message＋compaction |
| 保存與同身分重入 | 返回完整C與原回傳output相等；重入不新增count／create／compact；原歷史雜湊不變 |
| 新輸入位置 | 完整C後才追加user角色App資料及user角色更正；沒有替換或裁切C |
| 更正後接續 | 新請求count247；模型回覆季度盤點、只有主管核准調整、未解短缺當日升級，三項符合夾具；返回reasoning＋message，含encrypted reasoning，未讀解opaque內容 |

由工程代理直接對照夾具原文審核三項事實，沒有用另一個模型自評，也沒有要求答案逐字相同。這是**少量規則＋大量重複列的機制校準**，不能以165K→247的大小差異推論真訪談也有相同壓縮率／細節保留品質。沒有驗證每列SKU可逐筆回想；該能力本來就不屬本例的三項規則目標。

回報usage合計input **165,486**、output **168**，cache read/write均0；依既有`openai-standard-2026-09-30` Luna Standard費率估 **US$0.0166326**，非實際帳單，count沒有usage帳務回傳。本次成功只證明當時此大小請求可執行，不證明200K配額始終有餘額，也不推導429已被永久解決。

原128K輪前機制得到新的真provider證據；**B輪前128K／Step間160K仍是待確認候選，產品512K／272K未改**。下一個容量gate是依Owner門檻決策驗實際角色接線；不要再次重送本例或285K來堆相同證據。T16不勾完成；T14跨輪JD依據缺口、T17完整品質及T18切換仍分別追蹤，模型維持Luna／high。

識別與重現：

- 探針SHA-256：`04d8b192a23a34f4120bca18b2670901d838624d2d572be75e46589416ccf191`；安全JSONL：`30002ff31cde3cc1f4f815fef8d633b21130be7a47f45426adf19c5d4641a9e0`。
- 匯入夾具`probe_compaction_continuity.py`：`78342e546ddb64df31f0e80e8c81935bc31ecc8cce92148ce2bedbda3d3bd5c6`；`probe_runtime_compaction.py`：`92846b3b4f2c998b6cbcaa6f684ffa14ca531fbee24c00837b821e5888dd79fb`。
- instructions、tool雜湊與§5相同。返回C雜湊`394a71f995d2d2e1bc8625b3db33d1757caeb9f1aae4d770e09092fce4482d6c`；接續請求雜湊`edb658b89599b1d2c5307fa24e10d4cef20927fa83877e5c68eb43e4b200c346`。原C只在本次InMemorySaver，不承諾程序結束後取回。
- apps/api實際執行：`./.venv-target/Scripts/python.exe -X utf8 -B ../../.research-tmp/eval/probe_preparation_quota.py --key-file .env --output ../../.research-tmp/eval/preparation-quota-20261001.jsonl --execute`。這是已執行紀錄，不要求重跑；獨占輸出不可覆寫。
- 探針Ruff E4/E7/E9/F/I、format check與無外送dry run通過。既有`test_request_capacity.py`、`test_context_compaction.py`、`test_response_serialization.py` **43 passed，1.45s**；無產品程式修改，沒有將既有測試冒充本輪TDD。
