# OpenRouter／Luna 新 JD App 真實工具路徑驗收

- 日期：2026-09-22
- 範圍：新 `experiments/jd-relational-app` 正式 App 組裝；A 主顧問、既有 JD tools、PostgreSQL、Saver、managed host 與 Chat API
- 資料：隔離 PostgreSQL fixture、合成職務訪談；沒有正式 JD、Memory、對話或員工資料
- Provider：OpenRouter，OpenAI-only，`openai/gpt-5.6-luna`
- Credential：由舊 `apps/api/.env` 的既有 OpenRouter key 一次性寫入新 App 的 Windows Credential Manager `Caliburn JD/openrouter`；值沒有輸出、沒有寫入 repo／DB／診斷檔

## 結論

**本文件的首輪 400 結果與後續「JD 已保存但 final 缺失」歷史證據均保留；後續離線修正已找出並修好通知接線缺口，最新真實 Luna 受控測試已確認 notification→final，以及 JD mutation、自然收尾與本輪撤回的 HTTP／DB 往返。因此目前一般 tool/read、notification→final、JD mutation/final 與 manual undo 均可標 PASS；來源實際旅程與瀏覽器完整畫面仍 OPEN。**

後續重測在同一隔離 PostgreSQL fixture、同一新 App 正式 runtime 與 OpenAI-only Luna 路徑執行：5 次實際 provider request 全部 HTTP `200`，實際模型為 `openai/gpt-5.6-luna`，provider metadata 為 `OpenAI`，觀察到的 usage cost 合計 **US$0.01429579**。自然模型實際完成 `jd_read`、`read_evidence`、`jd_insert_item` 與 `request_memory_consolidation` 工具路徑；其中 JD insert 已有 confirmed committed receipt，JD revision 也已保存。

但歷史第二回合在成功保存 JD 後沒有保存 assistant 收尾訊息：查回狀態為 `run_status=failed`、`input_state=saved`、`jd_effects.state=settled`，且 committed result 的 `receipt_durability=confirmed`。根因與後續離線修正記於計畫 §24；修正後 follow-up 的模型沒有選通知工具，故不能把一般 final 證據當成通知路徑證據。因此目前狀態應分類為：

```text
A Provider/Wire acceptance       PASS
B Model tool generation         PASS（實際工具路徑已跑通）
C JD persistence／receipt       PASS
C natural final response        PASS（修正後一般 tool/read follow-up 已保存 final）
修正後 notification→final      PASS（最新受控測試已確認 durable ToolMessage／receipt／final）
JD mutation／自然 final          PASS（8 次 HTTP 200；JD receipt 與 assistant final 已查回）
本輪 JD undo（HTTP／DB）          PASS（manual undo receipt committed；對話保留）
來源實際旅程／完整 UI             OPEN
```

### 最新真實 JD mutation／final／undo 驗收

在同一隔離 PostgreSQL fixture、同一新 JD App 正式 runtime 與 OpenAI-only Luna 路徑，以合成訪談明確要求「讀取目前 JD → 建立一項最小工作責任 → 通知背景整理 → 用繁中收尾」。共 8 次 provider request，全部 HTTP `200`；實際模型為 `openai/gpt-5.6-luna`、provider metadata 為 `OpenAI`，usage cost 合計 **US$0.01797905**，沒有 hidden retry 或 fallback。

真實查回結果：

```text
run_status=completed
input_state=saved
response_message_id=<non-null>
JD operation=confirmed／committed
captured_operation_count=1
manual undo_ai_turn=committed
conversation messages before/after undo=2/2
```

JD 內容在模型回合後確實包含新增工作責任；接著使用既有 employee-only `undo_ai_turn`，以該回合的 `result_revision_ref` 作為條件，撤回後 JD 回到本輪前的內容。撤回沒有刪除原始訪談或 assistant 回覆，沒有重送模型回合，也沒有新增第二套 receipt／conversation。

這個 probe 的模型新增 task 使用空的 `basis_refs`，所以該 run change 沒有 source ref；這表示本次**沒有覆蓋來源查看資料**，不能把來源畫面標成 PASS 或 FAIL。來源 endpoint 與 source owner 的離線／HTTP 回歸仍沿用；下一個真實來源 gate 必須由模型在已有 Runtime 驗證的 evidence key 上產生附著來源的 JD 變更，再驗收改動入口能讀回正確原話。不手動塞入偽造 source ref。

隔離服務已正常關閉，沒有正式文件、Memory、對話資料或未確認的 provider 請求留下。

### 新架構瀏覽器殼層續驗

以新 `experiments/jd-relational-app` Web（`127.0.0.1:3002`）連回隔離 API，瀏覽器先正確顯示既有暫存建立操作的「尚待確認」狀態；透過既有查回入口後成功進入文件頁。頁面可見聊天顧問、訪談輸入區、六章 JD 導覽與六章編輯區，確認瀏覽器載入的是新 JD App，不是舊 `apps/api`／`apps/web`。

這次只驗證瀏覽器殼層、查回建立操作與文件頁載入，沒有在瀏覽器重送另一個真實 Luna 回合；因此不能把瀏覽器內的「訪談送出 → 模型回答 → 本輪改動 → 來源查看 → 撤回」標成通過。API／DB 層的 mutation、final 與 undo 證據已在上一節獨立通過，瀏覽器完整 journey 仍 OPEN。隔離服務已正常關閉。

### 最新修正後 notification→final 驗收

在同一隔離 PostgreSQL fixture、同一新 JD App 正式 runtime 與 OpenAI-only Luna 路徑，以明確要求通知工具的合成訪談執行受控測試。共 6 次 provider request，全部 HTTP `200`；實際模型為 `openai/gpt-5.6-luna`，provider metadata 為 `OpenAI`，觀察費用為 **US$0.00573776**，沒有 hidden retry 或 fallback。

同一 run 的 durable checkpoint 已逐項確認：

```text
Human
  → AI tool call: request_memory_consolidation
  → success ToolMessage: artifact=memory_consolidation_requested
  → AI final: 已送出背景整理通知；背景整理尚未完成。
```

Run record 為 `completed`、checkpoint `closed=true`，最後 assistant message 已保存。ToolMessage 也明確表示背景尚未執行、Memory 尚未更新；同一隔離資料庫的 `jd_memory_admission` 查回為 `idle`、target/source 為空、`recovery_count=0`，沒有啟動 B1／B2。這證明前景只完成通知 receipt，沒有等待或執行背景整理；「修正後 notification→final」由 `UNVERIFIED` 更新為 `PASS`。

測試期間第一次立即查詢 active run 曾收到一次 `503 service_unavailable`，稍後以同一 run 查回 durable `completed`；沒有資料遺失、重送或副作用重做。此現象先分類為 status-observation finding，不當成 provider／通知／final 失敗，也不在本次切片猜測修改 API。

### 較早的修正後一般 tool/read follow-up（歷史證據）

修正後先以同一隔離 App／Luna 路徑做了一次有界 follow-up：4 次 provider request 均 HTTP `200`，保存了 assistant final，且沒有 hidden retry／fallback。這一輪自然模型只走一般 JD read／evidence 查詢後收尾，沒有選 `request_memory_consolidation`，也沒有產生 JD mutation；當時因此只能證明一般 tool／read 收尾，不能取代後來的 notification→final 驗收。最新受控通知驗收已另列於上方。

這不是 JD 資料遺失，也不是可以重送同一回合的理由。前端現有行為是顯示「原話已保存，回覆未完成」、列出已保存的 JD 修改並提供實際改動查看；canonical conversation 不偽造一則 assistant 回覆。最後收尾失敗的具體 provider／framework 原因仍未由本次非敏感 metadata 證明，不能猜測成 schema、Prompt 或 Memory 問題。

已確認：新 App 能建立文件、讀取目前 JD、組裝正式顧問 runtime，並實際送出帶 JD tools 的 OpenRouter request。首輪三次 400 仍保留作為歷史首敗；後續重測已取得完整 HTTP 200、model/provider、usage/cost metadata，並實際走過工具與 JD 保存。

後續重測仍遵守 hidden retry=0、OpenAI-only、無 fallback 與合成隔離資料；完成目標後停止，沒有為湊次數繼續送出請求。

## 實際流程與證據

1. 首輪建立文件與 JD read 成功，但三次帶工具 request 回 HTTP `400`；原始首敗證據保留於本文件後續歷史說明。
2. 受控重測建立／讀取隔離文件成功，並送出 5 次實際 `/api/v1/chat/completions` request。
3. 5 次 request 均 HTTP `200`，模型為 `openai/gpt-5.6-luna`、provider 為 `OpenAI`；總 usage cost 為 `US$0.01429579`，無 request ID metadata。
4. 首個回合自然完成追問，沒有修改 JD；第二個回合依序實際呼叫 `jd_read`、`read_evidence`、`jd_insert_item`、`request_memory_consolidation`。
5. `jd_insert_item` 的結果為 confirmed committed，查回 JD revision 已包含新增內容；同一 run 的 effects 為 settled。
6. 第二個 run 沒有保存 assistant final message，查回為 `run_status=failed`、`input_state=saved`、`response_message_id=null`；沒有重送或重做已成功 JD 操作。
7. SDK／App hidden retry 維持 0；測試服務正常關閉，managed host 與 runtime close 均確認。

本輪仍沒有完成：

- 自然模型產生可保存的 assistant 收尾文字
- 透過瀏覽器畫面完成查看來源
- 透過瀏覽器畫面完成撤回本輪 JD 變更
- B1／B2 背景處理

## 與既有文件的對照

- 既有無工具 Luna smoke 已證明 OpenRouter 的 OpenAI route 可以收到基本模型回覆；那不是帶工具的正式 App 路徑。
- 新 App 的離線工具、JD、evidence-key、Saver 與完整 domain 回歸仍可沿用；它們證明客戶端與本地業務接線，不證明 OpenRouter 服務端自然工具迴圈。
- 角色模型文件已明確把「完整工具／Memory／JD 旅程」列為後續真實 gate；本次正好重現該未完成範圍。

## 最新決策與停止界線

1. 不修改 Prompt、Skills、Memory、B1／B2、JD domain、工具 schema、`strict`、平行工具設定、provider routing 或錯誤語意來掩蓋首輪 400；目前 wire／工具路徑已有真實 200 證據。
2. 不把「JD 已保存但 final 缺失」改成重送同一回合，也不新增第二套 receipt、conversation 或 fallback assistant artifact。
3. 若要處理收尾 UX，先確認是否只需沿用目前的固定 App 狀態／改動查看，或是否真的要變更既有「不偽造 assistant 歷史」決策；在此裁決前不改 production。
4. 本輪已證明 provider 接受工具路徑與 JD 保存，但沒有來源查看、撤回及完整瀏覽器旅程證據，不能宣稱完整 App 可用。

暫存真實測試紀錄在本機 `.research-tmp`，沒有納入產品程式或正式資料。

受控 mutation／undo 驗收的非敏感結果摘要保存在本機：
`S:\caliburn\.research-tmp\jd-ui-gate-20260922000000000000000000000002\real_luna_mutation_evidence_summary.json`。
原始 `real_luna_evidence.json` 後來因同一 fixture 的零請求瀏覽器殼層重啟而被覆蓋；因此本文件只引用已觀察且封存於摘要的結果，不把現存檔案誤稱為完整 raw ledger。
