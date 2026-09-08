# CT37：部分回答被擴成「沒有經驗」的來源追查

2026-09-08 · LLM-Q019 · CT36-R01／原 CT15-R04

**狀態：G5 局部對照完成，G8 OPEN；medium 候選未採用，high 僅有單例正向訊號。** [本輪結果、限制與完整證據](2026-09-08-ct37-prompt-effort-comparison-results.md)。下列§1–4保留診斷與核准時的設計，不是修復成功宣告；0次生成只指診斷階段。Owner核准20次／US$0.10、medium先測，仍失敗考慮high。本輪共9次傳輸嘗試／6次HTTP200完成；未改產品預設。

## 1. 本輪邊界與閱讀路由

- Owner 同意繼續處理 [CT36 §4](2026-09-08-ct36-interview-background-recall-results.md) 的既有語意品質問題。
- 唯一問題：員工只否定其中一個情境，為何 Memory 把另一個未回答情境也寫成無經驗？
- 沿用 [CT35 §5](2026-09-08-ct35-attempted-repair-recovery-review.md)：框架錯誤交回原模型；不新增 final 攔截或驗證 Agent。零工具 C 漏存仍停放，不改背景通知時機。
- 前次完整失敗與問答見 [CT15 結果](2026-09-08-ct15-grounding-and-whole-interview-results.md)、[T3–T4 逐字稿](evidence/2026-09-08-ct15-full.transcript.md)。不重新研究 Memory 架構。
- 本頁持有診斷與候選；最新效力由 [root register](../../../../docs/current-decisions.md) 路由。沒有新核准前，不重開 CT36 已關閉帳本。

## 2. 已確認的資料流，不猜模型內部推理

| 位置 | 實際內容／結果 | 判讀 |
|---|---|---|
| T3 顧問 | 同一句問「客戶不同意等待或退款」**或**「對技師判定有爭議」怎麼處理、誰決定 | 兩個情境，不是一個已成立事實 |
| T4 員工 | 「客戶兩個選項都不接受的情況我還沒有實際處理過，所以後面會怎麼決定我不確定」 | 只明確回答拒絕兩選項的情境；未否定技師爭議經驗 |
| T4 顧問 | 回述只保留「客戶不接受等待或退款」尚未實際處理 | 本句沒有把否定擴到技師爭議 |
| B1 request **8** 入料 | `NEW_SOURCE` 包含 T1–T4 的 **8 則完整員工／顧問文字**，`CONTEXT_ONLY=null` | 本例沒有切掉前題、遺失回答或依賴壓縮摘要 |
| B1 request **8** 詳記 | 保留上述員工否定短句；又在「尚未實際處理的情境」下列出整條雙情境未答追問 | 比候選保留更多差異，但不能稱詳記完全無歧義；標題與重列整題可能引人混讀，尚未證明它是模型犯錯原因 |
| B1 request **8** 候選 | 「客戶兩個選項都不接受**或對技師判定有爭議**……員工尚無實際經驗」 | **本鏈路第一個明確的錯誤否定**；把否定範圍擴大 |
| B2 request **9** 入料 | 已給同批完整詳記與候選，與保存內容核對全等 | 不是缺少 `NEW_DETAILS`、框架漏傳或引用地址失效 |
| B2 request **11** `write_file` | 將上述雙情境「尚無實際經驗」寫進 `/memory/knowledge.md` | 整併沿用了候選錯誤，未利用詳記保留的差異糾正 |
| CT36 前後 | 舊例外處理段落保留同一否定；本批只更新月報／FAQ | 是繼承既有錯誤，不是 CT36 月報更正新引入，也不以此要求每批重算全部 Memory |

**更精確的診斷：部分回答在抽取時被過度合併，候選與詳記的說法不一致；整併沒有化解這個不一致。** 這是可見輸入／輸出的定位，不能聲稱已知道模型注意力或隱藏推理的原因。

另外，request 8 使用的 B1 `INSTRUCTIONS` 與本轮讀取的现行提示逐字一致（正規化檔案 CRLF 後）；其中**早已有**「未答不擴成否定」與「顧問回述不等於員工確認」。所以不能診斷成規則根本沒寫、沒接到，或只重加相同提醒就稱修好。

### 原始證據定位與本輪唯讀核驗

[CT15 JSON](evidence/2026-09-08-ct15-full.json)，SHA256 `90d15e1bdf66b2f4d1ec14a9eea59752d957e01edda4122f70dbfb66bf60737f`：

- `requests[7].input[1].content`：JSON 內 `NEW_SOURCE.segments`，依原始順序共 8 則；第 6–8 則為上表 T3 顧問／T4 員工／T4 顧問。
- `requests[7].output[0].content[0].text`：三欄 JSON，其中 `rollout_summary`／`raw_memory` 可直接對照。
- `requests[8].input[1].content`：`NEW_DETAILS[0].content`、`NEW_CANDIDATES[0].content` 各完整包含前步對應產物；詳記與 `phases[4].latest_extraction.summary` 逐字一致。這兩個欄位是陣列，不是純文字。
- `requests[10].output`：實際 `write_file` arguments，並非從最終報告推測中間步驟。
- [CT36 JSON](evidence/2026-09-08-ct36-interview-background-recall.json) `phases[0].after.knowledge` 已有同一錯句；SHA256 `8c26653a5d056a43921fb05b157dc23cc802dec6edaa301b2c73727db0b9bac4`。

以上是讀封存核驗，沒有生成新模型結果；不能當作新提示的效果測試。

## 3. 官方依據與本案映射

於 **2026-09-08** 重新讀取下列官方內容；網址若為 `main`／現行文件，日後可能更新。本輪未將官方範例整套搬入產品。

| 官方直接資料 | 能支持什麼 | 不支持什麼／本案映射 |
|---|---|---|
| [OpenAI Codex Phase 2 提示](https://raw.githubusercontent.com/openai/codex/main/codex-rs/memories/write/templates/memories/consolidation.md)，`What to write`、`Preserve epistemic status` | 整併保留來源可辨識用語、知識的確定程度；不能把探索性說法升格為事實；候選不清楚時深讀詳記 | 不是職務分析專用規則，沒有保證模型必然判對；本案學習「保留限定條件與原意」，不移植其 Task／偏好 schema |
| [OpenAI GPT-5.6 提示指引](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)，`Simplify prompts first`、`Outcome-first prompts` | 保留證據與成功條件，移除重複／矛盾指令；保留明示值，按代表情境局部比較 | 支持校準既有提示，不支持不停堆同義警告；不能將其 coding 測試成效套成本案效果保證 |
| [Anthropic 減少幻覺](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)，`Basic hallucination minimization strategies` | 可以承認資訊不足，用來源文字支持主張；明示這些方法不能完全消除幻覺 | 本案沿既有問答與詳記核對，不因此要求每項增加 quote 欄位、追加多模型審核或要求輸出內部思考 |

共同可學的是**依據、原意與不確定性不能在整理時消失**；「如何用繁中短例子校準本專案」仍是待測的應用選擇，不冒稱兩家逐字相同的底層實作。

## 4. 已核准的最小候選與停止條件

建議先只處理 B1 的來源解讀，替換相近的既有規則，而非累加整套新提示：

- 保留「員工確實沒有做過」與「員工沒有回答」的差別，並限定在各自情境。
- 同一句顧問提到數件事，員工只回答其中一件時，其他部分仍是未取得回答；不整題套用同一答案。
- 兩份產物及其標題都須維持同一意思；短版不把「印象中／不確定」刪成肯定。用不同職位的簡短對照例說明，不把測試答案放進正式提示。
- 暫不改 B2、schema、儲存、工具、reasoning／compaction 或排程；先看較正確的 B1 產物能否沿原流程形成正確正文。

驗證只涵蓋原 T1–T4、不同職位的部分回答反例、明確否定仍保留，以及後續 B2；同時檢查案例辨識、工作範圍、頻率、權限與舊有效資訊不能退化。不得用提示字串測試或人工改好 Memory 冒充模型已學會。

如局部真測仍失敗，保存失敗並停下討論；不在同一輪擅自加驗證 Agent、更多必填欄位或強制每輪整理。若新提示有效，舊錯誤測試資料的修復另沿既有重新抽取／整併路徑驗證，不覆寫歷史證據。

**核准時 gate（現已完成局部對照）：**B1局部校準及新帳本Luna／medium小測（最多20次／US$0.10，含背景），仍失敗再考慮high。CT36額度未沿用。本輪medium原案例仍有漏記，依停止條件未進B2；high同提示同輸入單例保留關鍵差異，不代表已驗整併。下一唯一gate改為審閱[結果§5](2026-09-08-ct37-prompt-effort-comparison-results.md#5-下一步與不應外推的結論)，不自动調高預設、不堆提示或追加額度。

提示寫法依同一[GPT-5.6官方頁](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)的 `Simplify prompts first`、`Grounding, citations, and retrieval budgets`、`Reasoning effort`，2026-09-08再次讀取：替換相近規則、保留原意與證據約束，先維持effort做對照。high只是一個待驗選項，不是修復語意錯誤的保證。
