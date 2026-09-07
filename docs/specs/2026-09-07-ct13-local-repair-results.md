# CT13：局部修復結果與剩餘品質驗證

2026-09-07 · LLM-Q019 · **isolated G7 通過；語意品質／長訪談 G8 仍 OPEN**。

入口：[current decisions](../../../../docs/current-decisions.md) → 本結果 → [施工計畫](../plans/2026-09-07-ct13-local-quality-and-source-repair.md)。問題／方案見 [CT13 研究](2026-09-07-ct12-quality-and-retrieval-remedy-research.md)，底層責任與固定官方原碼見 [A3 source trace](2026-09-07-source-read-runtime-resolution-trace.md)。不重新從歷史長稿推定現在設計。

## 1. 做了什麼，哪些沒有做

| 切片 | 本次實作 | 驗收界線 |
|---|---|---|
| A1 提示保真 | B1 候選可精簡但不改事實範圍／條件；B2 在不一致、限制不明或準備改邊界時讀相關詳記；主顧問與 reader 不跨案例套頻率、工具、禁令，也不把顧問回述當員工確認 | 提示已校準，**尚未真模型複測**；不宣稱已解決 CT12 語意失真 |
| A2 收尾 | 主顧問指令加入整份工作範圍與深度核對，按需使用既有 Skills；保留未知、不重問答不出的外部規則、可自然休息續談 | 未加固定輪數、評分／Gap 表、問卷、新 Skill 或新 agent；自主收尾效果待驗 |
| A3 原文回查 | 既有 `read_conversation` 可接受詳記地址，程式代取已保存的原文 reference；可選本段或前置脈絡；保留 direct C 來源與分頁 | 真工具／Store／Saver 接線已驗；模型仍須選對詳記，不能保證零錯誤或所有歷史皆有 header |
| A4 完成判定 | 新獨立回查測試直接用產品 `build_conversation＋memory_access`；讀取成功後若最後答案 incomplete，仍必須失敗 | 沒有新增 validator／factory／重試；下一次真測必須沿此接法或服務，舊 CT12 trace 不改 |

不換 ABC／框架／provider／Memory 分層，不改來源內容或舊詳記，不接 JD／Web／production，不增加模型呼叫或調高上限。**本輪付費請求 0／US$0，沒有讀取模型金鑰。**

## 2. 原文怎麼找到：精確而非語意猜測

模型入口仍為同一個工具，參數為 `reference`、`offset`、`part`。`ToolRuntime` 不在模型 schema。

```text
AI 選已知詳記地址 /interviews/<runtime id>/summary.md
→ MemoryArtifacts.source_window：從檔首固定 metadata 讀保存的 source/context reference
→ ConversationReader.read：按指定 document／checkpoint／訊息範圍取可見問答
→ 原有每頁 3000 字與 next_offset
```

- `part="source"` 預設讀本段，`part="context"` 按需讀另存的前置問答；不一次自動載入兩份。
- 回傳保留原有來源／role／turns／omitted block kinds／分頁資訊，加 `summary_path`、`part`、`context_available` 幫助區分。
- 未保存前置脈絡：明確回 `context_available=false`、空 segments、無下一頁及說明。**不是宣稱歷史上沒有前文。** 不猜「附近」的訊息。
- C 還未產生詳記時，既有 `conversation:` 直接引用仍可用；`part=context` 不能用於這種直接地址，不推測相鄰範圍。
- 純來源查詢不依賴 candidates；重抽 `extraction_window` 仍要求配對 candidates。只是拆開職責，未刪防線。
- 固定 header、canonical path、文件隔離與 exact snapshot 檢查不變。錯 checkpoint／缺檔／無明確 header 回現有 `ToolException`，不是回最新內容；正文冒出的 Source 字樣不能取代 metadata。
- 這仍可能先載入完整 snapshot 再限制回傳，不宣稱 DB 分頁或延遲改善已測量。來源長碼仍留作 runtime locator／direct C 路徑，不宣稱全產品不再有識別碼。

這是**沿官方 primitives 實現的應用介面**，不是 Codex 原生就有相同的摘要回查函式。OpenAI 實際 runtime 寫來源路徑、模型沿路徑讀取的 producer/consumer、Anthropic client handler、DeepAgents key lookup 及 LangGraph exact snapshot 已在 [A3 §2–4](2026-09-07-source-read-runtime-resolution-trace.md#2-openai-實際做法路徑由程式寫入模型沿路徑查)逐項核對。

## 3. 官方依據及本案取捨

- [OpenAI GPT-5.6 prompting guidance](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)，本輪再次取得全文：精簡重複規則、保留事實／限制、寫明成功及停止條件；本案只改已見失真位置，不套用其內部效益數字到 Luna。
- [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)：已知參數交給程式；[Anthropic tools](https://www.anthropic.com/engineering/writing-tools-for-agents)：清楚、可用、有界的工具資訊。**不能由此推論所有產品都用本案參數。**
- [LangChain ToolRuntime](https://docs.langchain.com/oss/python/langchain/tools#access-context)、[DeepAgents BackendProtocol](https://docs.langchain.com/oss/python/deepagents/backends#custom-backends)、[LangGraph get_state](https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state)：既有 namespace／工具執行／精確 snapshot 能承接，不另建來源庫。
- [OpenAI reasoning output](https://developers.openai.com/api/docs/guides/reasoning#allocating-space-for-reasoning)：output 包含推理，incomplete 不能當成功。本案重用既有 `TurnValidation`，不是這輪才在產品修到這條規則。
- 職務方法保留／收尾面向來自已核准的[工作案例資訊取捨](../../../../docs/specs/2026-09-07-work-case-and-understanding-information-selection.md)與既有三份 Skills；它們是領域方法，不是外部廠商提供的職務訪談停止算法。

## 4. 實際驗證與遇到的問題

| 驗證 | 結果 |
|---|---|
| 原版來源／重抽基線 | 34 passed／15.37s |
| A1/A2 接線回歸 | 94 passed／13.93s，1項既有上游 warning；不驗證模型語意 |
| A3 red | 修正 fixture 的未關閉前輪後，7 failed／9 passed，7.54s；確認摘要入口／context 選擇尚未實作 |
| A3 green＋來源／重抽／live | 73 passed／16.80s |
| A3/A4 新檔 | 18 passed／9.36s；成功回查＋completed、成功回查＋incomplete 分別驗證 |
| 全部隔離回歸（含真 PG） | **580 passed／0 skipped，118.80s**；1項既有 Starlette/AnyIO deprecation warning |
| Python compileall／diff check | 通過 |
| 獨立唯讀 review | Task1 提示、Task2/3 機制與完成判定均無待修 finding；不是語意驗收 |

完整測試使用專用 `q019_agent_test`／localhost 55433，模型一律 mock；只清理測試自身隨機資料，沒有重啟 Docker 或修改產品資料。命令：

```text
PYTHONUTF8=1, PYTHONPATH=src, Q019_TEST_DATABASE_URL=<專用測試庫，外部提供>
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=.test-tmp/ct13-full-73df --tb=short
```

本輪碰到兩種**測試環境／fixture**問題，未誤修成產品邏輯：

1. Windows 沙箱無法讀 pytest 以限定權限自建的暫存目錄；第一次91通過／3環境錯誤，換工作區路徑仍受限。經工具核准在沙箱外、全新隔離暫存目錄重跑成功，不改系統 ACL、不刪舊目錄。
2. 新 fixture 曾缺前輪正常結束；補齊與現有 source contract 相同的資料。A4 成功 fixture 又重用了兩次相同 response ID，被 message reducer 當同一訊息更新；改為各次不同的合成 response ID 後成功與 incomplete 兩例皆通過。**未改原文儲存／reducer／完成 validator 來遷就測試。**

## 5. Closure／下一步

- **Status：**隔離程式接線可保存；A1/A2 的語意品質、A3 真模型低負擔回查、完整長訪談仍 OPEN。
- **保存：**Task1 為 `ba7b6f9b`；其餘本輪指定程式／測試／文件另存本地 commit/tag。未 merge／push，其他既有 dirty 文件保留。
- **下一 gate：**另有明確小額額度後，用 Luna／medium 分別複測原失真與不同職務變體、自主收尾、原文回查及完整回答，通過後再續整份工作訪談；不為回查無故重跑背景整理。
- **重開條件：**局部校準仍重複產生相同失真，或實際回查有新的來源／成本問題；帶具體 trace 討論，不疊無限提示、不自行加 verifier／換模型。
