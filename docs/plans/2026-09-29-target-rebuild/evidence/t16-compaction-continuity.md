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
