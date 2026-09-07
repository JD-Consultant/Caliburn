# CT10：Memory 編輯器官方底層局部比較

2026-09-07 · LLM-Q019／CT10 · **G5 比較完成 → G3 接入方式待審；產品未改**。

## 範圍與退出條件

- 承接 [CT09 診斷／封存證據](2026-09-07-long-interview-acceptance.md)，不重開 Memory 分層。
- Owner 核准：比較現有 DeepAgents 精確編輯與 OpenAI SDK 本機 patch 套用；沿用虛擬 Memory／LangChain，先驗原失敗案例與誤改風險，再決定接入。
- 本輪唯一問題：官方 patch 是否能在修復縮排誤差的同時，維持本案所需的局部正確性？
- 測法：離線重播三個真失敗輸入；另測相似段落、正確／錯誤定位、缺失內容、多 hunk 失敗、中文／換行。不呼叫模型、不讀金鑰、不寫資料庫、不變更產品依賴或 parser。
- 限制：由測試將既有 old/new 轉成 patch，只能驗套用器，不能宣稱 Luna 已能正確產生 patch 或訪談已修好。
- Stop：發現會影響採用選擇的誤改風險，記錄並回報；不自行加模糊匹配或默默接受新風險。

## 已核對的官方事實

1. DeepAgents 0.7.13 是查詢日 PyPI 最新版，三個相關安裝檔與官方 wheel 位元組一致。`perform_string_replacement` 精確比對是刻意選擇；維護者指出放寬縮排可能改錯相似區塊。[PyPI](https://pypi.org/project/deepagents/0.7.13/)、[維護者回覆](https://github.com/langchain-ai/deepagents/issues/403#issuecomment-3997938843)。不是已證實由過舊版本或本案魔改 parser 造成。
2. Anthropic Python SDK 的 Memory 參考實作：讀取是行號＋tab＋原文；修改是 exact count，零／多重匹配拒絕，成功回傳改動附近片段。DeepAgents 是行號＋兩個空白，成功回覆替換數；概念相似，不是底層完全一樣。[固定版本原碼](https://github.com/anthropics/anthropic-sdk-python/blob/dffb22d3e75c871f6e89cbdcdc0b03138628c3f4/src/anthropic/lib/tools/_beta_builtin_memory_tool.py)、[Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)。
3. OpenAI `agents.apply_diff` 是本機函式：先 exact 行序列、再 rstrip、再 strip；可用 context／`@@` anchor 定位，不會自行呼叫模型。指南允許 in-memory workspace，由應用套用並回傳 completed／failed。[指南](https://developers.openai.com/api/docs/guides/tools-apply-patch)、[固定原碼](https://github.com/openai/openai-agents-python/blob/18de65134083ee8cbdb84ae30a34c1f30ef4cb86/src/agents/apply_diff.py)。是否符合本案安全需求由離線比較回答，不以官方名義跳過檢查。
4. OpenRouter 支援一般 function tools；本機編輯器不需要 OpenAI key。另有 beta `openrouter:apply_patch`：驗 patch 語法但不替應用改檔案，不等於我們已接線驗證。[工具呼叫](https://openrouter.ai/docs/guides/features/tool-calling)、[apply patch](https://openrouter.ai/docs/guides/features/server-tools/apply-patch)。本機 parser 接普通 LangChain tool 也不等於原生 `apply_patch` 模型契約。
5. 本 app 的 OpenRouter 完整 reasoning／compaction 延續仍未驗收；目前已驗主路徑是 OpenAI direct。生成前精確計數已非預設必需，不能沿用先前 `/input_tokens` 404 斷言 OpenRouter 一律不可用。[OpenRouter Responses](https://openrouter.ai/docs/api_reference/responses/overview)、[reasoning](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)。

## 離線比較結果

- [可重跑腳本](../../experiments/analysis-agent/scripts/compare_memory_editors.py)、[完整輸入／输出／版本／hash](evidence/2026-09-07-memory-editor-framework-comparison.json)。SDK 以 `uv run --no-sync --no-env-file --with openai-agents==0.22.0` 暫時載入；未加入產品 `pyproject.toml`／`uv.lock`，未修改官方原碼。
- 使用 `agents.apply_diff` 公開函式，不取私有 parser；DeepAgents 使用目前實際的 `perform_string_replacement`。模型請求 **0**，模型費用 **US$0**，DB 寫入 **0**。

| 情境 | DeepAgents 精確替換 | OpenAI SDK patch |
|---|---|---|
| CT09 #40、#42、#45 三個原始失敗輸入 | 三次均重現找不到字串 | 三個轉換後的 patch 均套用；未改區域逐字保持 |
| 相同文字分別在 A／B，未提供區塊定位；目標為 B | 多重匹配拒絕 | 選第一個匹配，改到 A；相對測試意圖為誤改 |
| A／B 文字相同但縮排不同，又多帶顯示空白 | 找不到字串，拒絕 | fallback 選第一個匹配，改到 A |
| 同上，但有正確 `@@ # B` 定位 | 此表的 old_string 仍帶錯空白，拒絕 | 正確修改 B |
| 單一 `@@` 指向不存在標題，其他文字仍可匹配 | old_string 帶錯空白，拒絕 | 單一 anchor 不是必須命中；仍可能修改 A |
| 不存在標題放在真正 context 行，而非 advisory anchor | 未另測該 context 組合 | `Invalid Context`，不回傳修改結果 |
| 真正內容不匹配 | 拒絕 | `Invalid Context` |
| 第二個 hunk 失敗 | 不適用多 hunk API | 整次函式失敗，不回傳第一段半成品 |
| 中文、CRLF、無末尾換行 | 本組 old_string 含額外空白，拒絕 | 預期局部修改及原換行成立 |

**判讀限制：**這不是兩個工具的模型成功率 A/B test。patch 由測試腳本製造，不是 Luna 生成；精確替換亦未在每一情境改填對應的充分上下文，因此不能用表中的成功數宣稱哪個總體比較好。#45 套用後其實是 no-op（原內容已是兩個空白），不是新增工作知識。10 個補充案例中有 3 個不符合本案「目標位置正確或拒絕」期待，**無條件替換 parser 的 safety gate 不通過**；不是「SDK 官方測試失敗」，而是本案不能假設兩種匹配契約等價。

上述 first-match、單一 anchor 可未命中而繼續，是實讀／實跑該 SDK 版本的行為，不是本案自行新增的 fallback。正確 context 能定位不代表程式可以從缺失的資訊保證猜對。這正是[DeepAgents 維護者](https://github.com/langchain-ai/deepagents/issues/403#issuecomment-3997938843)所說的取捨。

## 決策建議與下一 gate

**CT10-E01／Important／OPEN：**若直接把現有 exact editor 換成 `apply_diff`，會失去「重複匹配自動拒絕」這個既有行為；本案 Memory 整理是背景發布，沒有每一 patch 的人工審核，不能把字串套用成功當成語意位置正確。既有格式／引用 validator 也不能辨識所有此類誤改。

官方 OpenAI 完整做法包括提供可探索檔案內容、鼓勵小範圍 diff、scratch workspace、套用後驗證、回傳結果／錯誤；不能只抽 parser 就聲稱等同原生工具完整流程。[官方安全與最佳實務](https://developers.openai.com/api/docs/guides/tools-apply-patch#safety-and-robustness)。本案已經有 staging／發布驗證，但這不等同保證語意正確。

兩個局部選項（Caliburn 取捨，不宣稱各家一致最佳）：

1. **建議先做：保留官方 exact matcher，改善修改前原文的呈現。**明確區分行號／顯示分隔與真正文字，維持原分頁、長度上限、錯誤回傳及 scope；參考 Anthropic 官方 tab 分隔／成功片段回覆。不得自行 trim 原檔或 fuzzy matching。這直接針對已重現的 display-copy mismatch，保留重複匹配拒絕；但能否降低 Luna 錯填率仍需短真實測試，不能現在稱修好。具體選用的 framework extension 必須核對官方 API，尚未施工。
2. **仍可選：採官方 patch 完整接線。**把充分上下文定位、改後檢查一起設計，接受它不會無条件拒絕所有多重匹配；仍不自寫 parser。不只是把工具改名為 apply_patch，也不先假設 ordinary function schema 與 provider native tool 效果完全等價。需 Owner 確認取捨後再接。

未自動加新語意 verifier／新 Agent／自創唯一匹配 patch guard，未提高上限、改 provider、再跑 CT09。原 CT09-E02 的 8 步／blocked 恢復仍是後續問題。

**Closure：**離線比較 DONE；接入選擇 OPEN。先向 Owner 說明實測差異、確認上述局部路線，再進工具接線與 Luna／medium 小測；整份工作驗收仍未通過，不重開 Memory 研究。

驗證／審查：離線再次執行，結果與封存 JSON 相同；`git diff --exit-code HEAD -- experiments/analysis-agent/src experiments/analysis-agent/pyproject.toml experiments/analysis-agent/uv.lock` 確認產品碼與依賴未改。獨立唯讀 review 核對原 trace、重建片段與三個定位案例，無新增 finding；review 本身未重跑 SDK，不替代本輪實測。未執行付費 Luna、新一輪訪談或整套產品驗收。
