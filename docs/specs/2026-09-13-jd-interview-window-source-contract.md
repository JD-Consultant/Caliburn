# 完成訪談窗口 source port：介面契約與固定情境

2026-09-13；JD-R002／OI-01、OI-02。[採用映射 §6 第1項](2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)與[審查紀錄 F4](evidence/2026-09-13-jd-b1-b2-adoption-review.md)要求的第一項交付。基準 `a60f4e82`／tag `jd-consultant-adoption-mapping-review-20260913`。

**本稿只定契約與固定情境，沒有實作、沒有測試執行、沒有 provider 呼叫，也沒有新增資料表。**舊程式證據一律以 `git show 4f94fbfb:experiments/analysis-agent/...` 讀固定來源，不用 checkout 最新檔。

## 1. 為什麼只加窗口切分接不上

新 App 已有的來源能力是**本輪**用的，不是壞掉，而是刻意只做一件事：

| 新 App 現況 | 實際語意 |
|---|---|
| `ConversationSourceService.capture(document_id, run_id)` | 經 `_selected` 只回「前一則可見 AI ＋ 本輪 Human」，且要求該 Human 是訊息串最後一則 Human |
| `_SourcePosition` | `purpose="source"`，`last` 必須等於 `run_id`，namespace 限 `""` 或 `consultant:*` |
| `MemorySourceReader.read` | 回 `SourceExcerpt(source_ref, messages)`，沒有分頁、沒有逐輪狀態、沒有省略類型 |

B1 要的是**輸入→答覆**的已完成回合，而且跨輪；現有投影是**問→輸入**，方向相反，而且 `last == run_id` 讓跨輪範圍無法表達。所以缺的不是一個切窗函式，是一組新的、與現有 C 來源並存的窗口能力。

**現有 C／只讀工具的 source port 不動。**它已在 H2–H3 驗過，本稿不改其投影、驗證或錯誤分流。

## 2. 責任切分

| 權威 | 誰保存 | 本 port 的關係 |
|---|---|---|
| 原始對話 | 既有 Saver（root／consultant checkpoint 鏈） | 只讀固定祖先位置，不建第二原話庫 |
| 已整併覆蓋游標 | publication head 的 `processed_source` | **只比較，不另存一份游標** |
| B1 工作進度／剩餘預算 | B1 自己的 Saver checkpoint（原生續作） | 不由本 port 保存 |
| 背景准入狀態 | 尚未決定，屬[映射 §3.3](2026-09-13-jd-consultant-b1-b2-adoption-mapping.md) | **不在本稿決定，也不在此預先排除** |

因此本 port 自身**不需要新增持久狀態**——這是從上表推導的結果，不是「不准新增表」的規則。

## 3. 引用模型

### 3.1 新增一個 purpose，不另造 parser

窗口引用沿用既有 `ConversationSourceCodec` 的同一簽章與 dataset／document scope，新增 `purpose="window"`；**不引入舊的無簽章 `parse_reference`，也不發一套繞過驗證的引用**。

`_WindowPosition` 相對 `_SourcePosition` 的必要差異：

| 欄位 | `source`（現有，不動） | `window`（新增） |
|---|---|---|
| `last` | 必須 `== run_id` | 窗口最後一則訊息 id，**不綁 run_id** |
| `run_id` | 本輪身分 | 不適用；改記 `first_run_id`／`last_run_id` 作逐輪核對起訖 |
| namespace | `""` 或 `consultant:*` | 固定 `""`：窗口是 root 鏈上的範圍，不掛任一輪的 consultant 子圖 |
| `root_checkpoint_id` | 該輪 root 位置 | 發出窗口時的固定 root 位置；之後一律以此位置讀，不回退到 latest |

`format_version` 從 1 起算，`purpose` 不可互換：以 `source` 引用呼叫窗口讀取、或反之，一律拒絕。

### 3.2 驗證與解碼

- `validate_window_reference(ref, document_id)`：只驗簽章、格式與 scope，不做儲存 I/O，語意與現有 `validate_reference` 一致。
- 實際讀取時再核固定位置上的 `first`／`last` 確實存在且順序正確；對不上即 `invalid_ref`，**不回退到別的 checkpoint**（沿現有 `read` 已驗行為）。

## 4. 讀取契約

`read_window(ref, offset=0)` 回一頁，欄位沿已驗的舊形狀，語意逐項重新定義在新 App 的證據上：

| 欄位 | 契約 |
|---|---|
| `reference` | 原引用原樣回傳 |
| `segments` | `{message_id, role, text, text_offset}`；單頁可見文字上限沿舊值 3000 字元 |
| `turns` | `{input_id, status, answer_succeeded}`，逐輪，見 §5 |
| `omitted_content_types` | 已排序的省略種類；工具、媒體、不可見區塊是 canonical 但不是員工原話 |
| `next_offset` | 還有內容時給下一頁 offset，讀完為 `None` |

`offset` 必須是非負整數且由前一頁回傳；超過總長度即錯誤，不靜默截斷。**分頁只切可見文字，不切回合**：`turns` 每頁都完整列出該窗口涵蓋的回合，讓呼叫者不必湊頁才知道終局。

這個分頁讀取是**新增**的，不取代 `MemorySourceReader.read`——後者服務 C 與四個只讀工具，維持現狀。

## 5. 逐輪終局與 `answer_succeeded`

**安全終局的權威改用新 App 的 run record**，不移植舊 `closed_turns`／`_turn_status` 推斷分支：

- 安全終局 = 該輪 `record.status != "running"` **且** `observed.closed`。它由 `_settle` 核完 JD receipt 與 C 結果後才寫入，比舊 boundary 嚴格。
- `status` 投影自 run record：`completed`／`failed`／`cancelled`。
- `answer_succeeded = (status == "completed")`。

三件事必須分開，不可互推：

1. **安全結束**（可以被 B1 讀）
2. **答覆成功**（`answer_succeeded`）
3. **已請求整理**（§6）

已安全收尾的 `failed`／`cancelled` 回合**仍保留員工原話**，照樣進窗口，只是 `answer_succeeded=false`；B1 的 prompt 已驗會據此不補寫答案。

**逐輪核對，不從最新終局推定歷史。**窗口涵蓋的每一輪都要在同一條固定祖先鏈上各自確認終局；只看最新 run record 就放行整段歷史是不允許的。

## 6. 整理請求辨識

沿已驗的純通知語意（`request_memory_consolidation` 無參數、回 `content + artifact{kind}`，不執行 B、不寫 Memory、不宣稱完成）。

`has_saved_consolidation_request(messages)` 的辨識規則沿舊 `has_saved_request`：

- 必須有**一組真實且不歧義**的原 call／result 配對：call 的 `name` 相符且有 `id`，該 `id` 在全部 call 中唯一
- 對應的 ToolMessage 恰好一則、位置在 call 之後、`name` 相符、`status == "success"`、`artifact` 完全等於約定的 kind
- 純文字、孤立 call、不匹配的 result **都不算請求**

**終局不等於請求。**把安全終局直接當成整理請求會變成每輪整理，偏離已驗節奏；反之，沒有請求且沒有明示啟用的字數後備條件時不啟動新批次。

## 7. 窗口規劃、覆蓋與 admission

### 7.1 待整併清單

`pending_windows(after_reference=None)`：沿固定祖先鏈，回**安全收尾且帶有效整理請求**的回合。`after_reference` 為 publication head 的 `processed_source`（見 §7.2），不是本 port 自存的游標。

### 7.2 覆蓋與順序

- `covered(reference)`／`follows(reference, previous)`：以**實際原話順序**（固定鏈上的訊息位置）比較，不用 UUID 或時間戳排序。
- `previous` 一律取自 publication head 的 `processed_source`；本 port 不保存第二份游標，也不寫入 publication。
- B1 admission 沿舊 `require_new_source_after` 的兩條：新範圍必須**在**前一個已處理範圍之後，且**連續**——不得跳過中間的員工回合。

### 7.3 窗口切分

沿已驗 `extraction_windows`／`extraction_batch`／`validate_saved_window` 的語意：

- `max_chars`／`context_chars` 預算；消歧前綴必須包含**必要的前一個問題與其間的答覆**，不能只取舊問題或最後一則 Human
- 消歧內容超出 `context_chars` 或總預算時**明示失敗**，要求提高預算，不省略也不截斷
- `max_windows` 上限沿 B1 角色配置（見[映射 §4](2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)，`max_windows=16`；這不是 A／B2 的 16 模型步／15 工具呼叫）
- 重抽（`reextract`）必須回到**已保存的原窗口**，不得改用最新本輪輸入，也不推進正常 B1 輸入位置

## 8. 失敗模式：一律明示，不靜默降級

| 情形 | 必須 |
|---|---|
| 來源讀取失敗 | 明示無法取得完整來源；不以部分內容當完整 |
| 超過目前 256 祖先查找界線 | 明示受限，沿 OI-05 處理；不當成「沒有原回合」 |
| 祖先鏈缺鏈 | 明示失敗；不跳過缺口繼續拼窗口 |
| 消歧內容超預算 | 明示失敗（§7.3）；不截斷後宣稱完整 |
| 窗口內有未安全收尾的回合 | 不跳過該輪、不把後面的回合提前納入；窗口止於最後一個安全收尾處 |
| 引用 purpose 不符／簽章無效／位置對不上 | `invalid_ref`；不回退到其他 checkpoint |
| publication 游標讀取失敗 | 停止 admission；**不重設游標**、不假設未處理 |

## 9. 固定情境（實作必須滿足）

零 provider、固定回覆。編號供後續結果稿引用。

| 編號 | 情境 | 期望 |
|---|---|---|
| W-01 | 三輪皆 `completed`，無整理請求 | `pending_windows` 為空；不啟動批次 |
| W-02 | 三輪皆 `completed`，第2輪有有效請求配對 | `pending_windows` 涵蓋到第2輪終局；第3輪不因未請求被漏掉，依連續性納入或明確止於安全邊界 |
| W-03 | 第2輪 `cancelled` 但安全收尾，員工原話已存 | 該輪仍進窗口，`answer_succeeded=false`，原話逐字可讀 |
| W-04 | 第2輪仍 `running` | 窗口止於第1輪；不跳過第2輪把第3輪納入 |
| W-05 | 文字長度跨多頁 | 分頁 `next_offset` 可讀完全部；`turns` 每頁完整；`omitted_content_types` 如實列出 |
| W-06 | 消歧前導問題超過 `context_chars` | 明示失敗，不截斷、不改用更舊的問題 |
| W-07 | 以 `purpose="source"` 的引用呼叫 `read_window` | 拒絕 |
| W-08 | 窗口引用的 `first`／`last` 在固定位置對不上 | `invalid_ref`；不回退 latest |
| W-09 | 新範圍與 `processed_source` 重疊或更早 | admission 拒絕 |
| W-10 | 新範圍跳過中間員工回合 | admission 拒絕 |
| W-11 | 孤立 call、純文字、`status="error"` 的 result | 不算整理請求 |
| W-12 | 同一 call id 出現兩次 | 不算整理請求（歧義） |
| W-13 | 重抽已保存窗口 | 讀回原窗口內容；正常 B1 輸入位置不前進 |
| W-14 | 祖先鏈缺鏈／超過 256 祖先 | 明示受限，不當成沒有原回合 |

## 10. 界線與未決

1. 本稿是契約與情境，**沒有任何實作或測試**；W-01–W-14 是待建立的案例，不是已通過的結果。
2. `_WindowPosition` 的確切欄位名與 codec salt 在實作時定案；本稿只約束**必要語意差異**（`last` 不綁 run_id、namespace 固定 root、purpose 不可互換）。
3. 背景准入狀態的持久落點**不在本稿決定**；本 port 自身不需要新增持久狀態是推導結果，不延伸成對背景的禁令。
4. 256 祖先上限與長歷史策略沿 OI-05，本稿只要求明示失敗，不在此重寫。
5. B1／B2 的 prompt、輸出欄位與角色配置一律不動（[映射 §4](2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)）。
6. 契約成立不等於 H4 完成；零 provider 固定完整旅程與自然品質（OI-09）仍未開始。
