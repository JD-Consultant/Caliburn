# CT34：首次更正與舊漏存恢復——兩種未完成，不能算修好

2026-09-08 · **LLM-Q019／Q019-MEM-CADENCE-01／CT15-R07 · G5對照完成／G8 OPEN**。

## 1. 本輪範圍與結論

承接 [CT33追溯](2026-09-08-ct33-compaction-provenance-and-recovery-review.md)，依 Owner 核准的 [CT34計畫](../plans/2026-09-08-ct34-first-correction-and-recovery.md)，測「現行規則遇到首次10→5更正」與「恢復舊漏存」。兩組都未真正更新 Memory，但失敗路徑不同：

| 場景 | 實際行為 | 持久結果 |
|---|---|---|
| first：原38則問答，首次這項更正 | 3次模型／2工具：`grep` → `repair_memory` → final。Patch被拒，回饋已明說未寫入、可重試，仍未續修 | knowledge／guide維持revision3、10日；回答5日 |
| recovery：原42則問答，先前已口頭答5但漏存 | 1次模型／0工具，直接答5日 | 同樣維持revision3、10日 |

共 **4次Luna／medium，估US$0.0080306**；已核准上限20次／US$0.10，帳本closed，不繼續花完額度。不改產品、prompt、工具、reasoning、compaction、B時機或JD。

**證據支持的結論：**漏存至少出現在兩種可觀察路徑：未選動作，以及已選動作但未依失敗結果繼續。不能再只用「沒有呼叫工具」概括全部問題。也不能以格式驗證／錯誤回傳存在，就推論模型一定會重試。

## 2. 對照一致性與正式資料

- 原資料庫 `q019_ct16_capacity_19d4940b52` 未變；兩組各建獨立副本，不重跑完整訪談。
- first取完整保存點 `1f1aae1d-0c59-6fd3-8025-24d6cb524b92`，其38則問答原文／ID與CT16封存前38則相同。revision3的processed_source正是此保存點，Memory與來源時間一致。用 [LangGraph官方fork](https://docs.langchain.com/oss/python/langgraph/use-time-travel) 建立新完成態checkpoint，values完全相同，原歷史仍可讀；不是刪除後四則，也沒有回滾Store或手拼opaque。
- first第一請求的既有可見互動與opaque，和CT16 #16輸入逐項相同；只換成現行規則／導覽與本輪真實來源。recovery與CT28原history請求比對，除新輸入來源reference外相同。
- 兩組當前system規則／Memory導覽與六工具相同；每次wire均驗CT25契約，無forced tool。reasoning=`medium/all_turns`、inline compaction設定與原測試相同；本輪新增的reasoning／工具結果完整延續。
- 重開副本後，兩組knowledge／guide／cursor／B狀態仍與測前一致。first可見38＋2、recovery42＋2；新舊問答、四份詳記引用與回查原文頁逐字核對通過。此次沒有成功C回執，**不宣稱成功修補或成功寫入來源**。

依 [OpenAI inline compaction](https://developers.openai.com/api/docs/guides/compaction#server-side-compaction)，opaque是模型互動延續，不是外部Memory CRUD。本案沒有發現canonical原始訪談被壓縮覆寫。first最後請求另產生新compaction；內容不透明，不能解讀其內容或宣稱壓縮已完全排除。

## 3. first失敗的精確位置

`grep` 已回傳正確的月報段落。模型提交Patch的「待取代舊行」在最後一個詳記連結後**自行多加一個 `。`**，和儲存原文不符；封存斷言證明該舊行差異就是這個句號，並非資料庫少字。

工具回覆 `invalid_edit`、`retryable=true`、`read_paths=[/memory/knowledge.md]`，detail明确寫此patch沒有寫入，要求重讀範圍後修改diff。這份結果已在第3個模型請求中；模型卻直接final回答「已更正」。當時只用3次模型／2工具，未耗盡原服務步數，也不是API／費用上限攔住。

本地接點：[live_memory.py](../../experiments/analysis-agent/src/analysis_agent/live_memory.py) 的 `_command` 把框架回執帶回模型，`wrap_tool_call` 允許既有有限重試；`after_model`核對回應與工具identity，沒有已完成效果的語意檢查。[conversation.py](../../experiments/analysis-agent/src/analysis_agent/conversation.py) 的 completed是技術回應邊界，不能當作Memory修改成功。

**Unknown：**各組只一次；first的先前長訪談也含舊時期規則，並非全場都用CT25的新訪談。因此只能說現行規則接原長對話時發生上述情況；不能宣稱已測出普遍失敗率、模型內部原因，或所有壓縮／舊規則因素都已排除。

## 4. 下一個決策——沿既有官方候選，不再增加同義提醒

本輪重查 [Codex Stop](https://learn.chatgpt.com/docs/hooks#stop)：可回傳block與reason讓任務續做；[Claude prompt-based Stop](https://code.claude.com/docs/en/hooks#prompt-based-hooks)：可用一次模型判斷未完成事項，把不通過理由交回原模型；[LangChain agent jumps](https://docs.langchain.com/oss/python/langchain/middleware/custom#agent-jumps)：有after_model返回模型節點的接點。均在2026-09-08直接讀取對應章節。

這些是**官方可配置的完成檢查／續做機制**，不是已證明兩家預設替Memory逐輪檢查，更不是框架內建漏存判斷器。原比較／代價／來源邊界保留在 [CT30§3–4](2026-09-08-ct30-missed-memory-write-official-controls.md#3-目前程式缺在哪裡以及不能省略的判斷)。

**建議G3：同意先設計一個局部完成檢查對照，不直接上產品。**要分兩件事：已收到未成功工具回執，可核對「這次嘗試未完成」；完全零工具，仍須判斷「是否確有必要寫入」，不能看0工具／版本沒變就強制重寫。兩者可沿相同框架續做接點，但不假裝同一條零成本規則即可包辦。

設計前仍需說清檢查觸發範圍、最小足夠Context、續做上限與成本，以及已正確／新資訊尚未入Memory／含糊更正不誤寫。檢查不能自己改Memory；機器回饋不能冒充員工訊息或來源。**Owner尚未核准完成檢查、新模型呼叫或新prompt，因此本輪停在此gate。**Patch介面與B排程仍停放，不趁此改寫架構。

## 5. 核驗、保存與研究邊界

- [封存證據](evidence/2026-09-08-ct34-first-correction-and-recovery.json)：SHA256 `b6f87844d096a9f47c94cfed9d366ad40ca1a9f2823fc693c857366c1ba1ce69`；包含實際wire可見內容／opaque hash、before／after、回執、原文頁、脚本與其hash。不得覆寫，不保存金鑰或opaque內容。
- 36項相關離線測試通過，另通過既有請求／費用／closed ledger上限測試；Starlette有1項棄用警告。第一次pytest因sandbox暫存目錄ACL失敗，改獨立目錄／權限後重跑；未調整產品測試。
- 原DB最後再以唯讀連線核對：最新checkpoint、42則問答、revision3正文／導覽／來源cursor完全未變。原生Store `get` SQL含TTL更新CTE，遭只讀交易拒絕；核對本機框架實作後，改用官方 `search(namespace, refresh_ttl=False)` 且不提供query，讀同一版本兩檔核驗。僅診斷接法，未變更框架或產品、沒有關閉DB唯讀保護。
- `src/analysis_agent`／產品tests相對CT25沒有變更；本輪只新增診斷／研究／證據。current register只保留結果路由，不複製逐字稿。
- 獨立唯讀審核未提出阻擋：另核對封存hash、11份脚本與24份產品檔案hash、wire／opaque鏈和結論限制。Reviewer沒有重跑API、DB或36項測試，這些由本輪Main實際核驗，不重複宣稱。
- **Closure：G5完成、G8 OPEN；下一gate是完成檢查候選的適用範圍與成本審議。**不重開新一輪泛查Memory設計，也不以這次診斷稱「正常長訪談已穩定」。
