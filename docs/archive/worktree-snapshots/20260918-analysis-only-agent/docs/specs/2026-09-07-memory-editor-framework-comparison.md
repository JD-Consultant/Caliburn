# CT10：Memory 編輯器官方底層局部比較

2026-09-07 · LLM-Q019／CT10 · **G5 比較完成 → G3 接入方式待審；產品未改**。

**最新入口：**Owner 要求進一步追查「官方如何處理三個失敗」。本頁下方 [現行底層追查與 context 補測](#現行底層追查與-context-補測) 補上 Codex／SDK 差異、完整定位與研究修正。先前偏向呈現修法只是未核准建議；目前建議改為試接官方 patch 完整流程，尚未施工、尚未宣稱 Luna 成功率。

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

## 現行底層追查與 context 補測

2026-09-07 · 同一 CT10／G2→G5 補證據，G3 接入仍待審。不是新增 Memory 架構議題。

### 三個為何成功：不是自創模糊比對

**Official fact＋已重播：**SDK `apply_diff` 先將換行整理為可解析的行序列，再解析帶刪除／新增／保留行的 diff；`_find_context_core` 先試完整行序列相等，再忽略行尾空白，最後忽略兩端空白。CT09 三個失敗輸入都在舊文字行首多帶兩個空白，故 exact editor 拒絕，而 SDK 的最後一層匹配能定位。此處容錯由官方函式提供，本案未修改它；不是把整份 Memory 先 `strip()` 再存回。[SDK 固定原碼](https://github.com/openai/openai-agents-python/blob/18de65134083ee8cbdb84ae30a34c1f30ef4cb86/src/agents/apply_diff.py)。#45 仍是 no-op，不能算多完成一次知識修正。

SDK 把保留行用來定位，真正套用的 chunk 只含增刪部分；本次 LF fixture 即使定位用的 context 空白有差，原 context 縮排仍保持。**不得擴大成任意檔案逐 byte 保證**：SDK 仍會處理換行形式；本 app 生成的 Memory 本來即以 LF 保存，不觸及 canonical 原始訪談。

### 不能把「OpenAI」三種介面混為一談

| 已實讀的官方實作 | 空白與字元匹配 | 區塊定位／錯誤 | 本輪證據邊界 |
|---|---|---|---|
| Python Agents SDK 0.22.0 `apply_diff` | exact → 行尾空白 → 兩端空白；不正規化智慧引號 | 單個 `@@` 找不到可繼續；多個 stacked anchor 要命中；實際 context 不符則 `Invalid Context` | 本機純函式實跑；不是模型／原生工具成功率 |
| Codex Rust `apply-patch`，查詢時 main 固定 commit `0df39752cbc4b88d0194ec62bdb0d56fbda4b014` | 上述三層之外還有部分 Unicode 標點／空白正規化 | `change_context` 找不到即錯誤；不是 SDK 單一 advisory anchor 行為。換行有 normalize／preserve 模式 | 原碼檢查，未編譯或執行 Rust／Codex CLI |
| Responses 原生 `apply_patch` | 模型產生 operation，應用選擇 harness 實際套用 | 每個 call 回 completed／failed 與結果；可據錯誤繼續 | 官方 API 契約，不等於我們的普通 LangChain function tool 已原生接線 |

直接來源：[Codex matching](https://github.com/openai/codex/blob/0df39752cbc4b88d0194ec62bdb0d56fbda4b014/codex-rs/apply-patch/src/seek_sequence.rs)、[Codex file update](https://github.com/openai/codex/blob/0df39752cbc4b88d0194ec62bdb0d56fbda4b014/codex-rs/apply-patch/src/file_update.rs)、[Codex grammar](https://github.com/openai/codex/blob/0df39752cbc4b88d0194ec62bdb0d56fbda4b014/codex-rs/apply-patch/src/parser.rs)、[Responses／SDK 官方指南](https://developers.openai.com/api/docs/guides/tools-apply-patch)。SDK 是指南明列的參考實作，**不需要自行移植 Codex Rust matcher 來假裝兩者一致**。

**來源修正：**搜尋曾找到「預設前後三行、不足加定位」的舊獨立提示；追提交發現它已在 [8d637ae／Remove unused apply_patch prompt fallback](https://github.com/openai/codex/commit/8d637ae3980fdae79044e638c93c7e579de3c62e) 刪除，理由為 unused fallback。不可把該舊檔當成目前強制規則，也不可反推 Codex 已不要上下文。現行指南直接支持清楚檔案內容、探索工具、小範圍 diff、套用及測試後回傳結果，不指定本案固定三行政策。

### 完整流程與補測結論

官方公開流程是：**先提供或讀取相關檔案內容 → 模型產生局部 patch（可帶實際 context／定位）→ harness 在 workspace 套用 → 明確回傳成功／失敗 → 模型按需重讀、修正 → 分享檢查結果**。SDK 可作用在記憶體中的文字；檔案地址限制、scratch／備份與發布原子性由應用安排。這些不是 parser 自動處理的。[流程／錯誤／安全](https://developers.openai.com/api/docs/guides/tools-apply-patch)。本案既有 private staging、format／reference validation、revision publication 可保留；不再發明第二個 parser 或新增 LLM verifier。

- [補測腳本](../../experiments/analysis-agent/scripts/probe_patch_context.py)／[完整 fixture 與結果](evidence/2026-09-07-memory-editor-context-followup.json)。10 項特徵觀察：4 個完整定位／context 保留情境正確套用、4 個內容／定位缺失被拒、另保留 2 個反例（合法但選錯 A 的 context 會改 A；不存在的單一 advisory anchor 未必拒絕）。**10 個觀察符合預期不等於 10/10 產品安全通過**。
- A/B 重複段落帶實際 B 標題與來源 context 後，正確修改 B；同時允許已重現的行首空白誤差。補測不依賴固定三行或額外自創 guard。
- 先前省略／填錯定位的反例仍有效，但不能拿它們推論完整 OpenAI 方式較差、不能用，或 Luna 更易誤改。反過來，手工補 context 成功也不能保證 Luna 都會填對。
- Anthropic 最新文字編輯契約仍要求 `old_str` 連空白／縮排精確一致；DeepAgents 維護者也明說這是刻意選擇。因此「各家都使用同一個寬鬆 matcher」**不是共識**；共同可學的是有內容可讀、局部修改、失敗回饋與再檢查。[Anthropic](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool#str_replace)、[DeepAgents](https://github.com/langchain-ai/deepagents/issues/403#issuecomment-3997938843)。

### 更新的建議與停止研究點

**Caliburn mapping／待核准：優先局部試接官方 SDK patch 完整流程，不只繼續加「不要抄行號空白」提示。**它直接覆蓋這次反覆發生的空白差異，且有 Python 公開純函式，可用現有 LangChain 工具與虛擬 Memory 儲存承接；不用複製 Rust、另換 Agent 或新寫 fuzzy matcher。既有 exact 方案仍是可回退比較基準，不宣稱已證明 patch 整體較佳。

試接需連同閱讀／定位說明、工具結果與局部檢查一起做；保留分頁與 Context 上限。DeepAgents `BackendProtocol.read → ReadResult.file_data` 原本回未格式化內容，顯示行號是下游 `FilesystemMiddleware` 加的，不能誤以為覆寫 backend 的 read 就已改到 LLM 呈現。現有 B2 `StateBackend` 暫存與 C `RepairWorkflow` 路徑不同，也不能只換 B2 函式就說兩條都修好。

本次改動只有實驗／研究紀錄；0 模型請求、US$0、0 DB 寫入。沒有切換 provider、增加產品限制／新工具／新依賴。**Next gate：Owner 確認局部 SDK patch 試接 → 原失敗案例接線回歸 → 小量 Luna／medium 確認模型能讀、產生、修正 patch；通過才接續 CT09 長訪談，不再重開 Memory 分層。**CT10-E01 的匹配契約差異保留為採用取捨，不能說已消失。未知只剩真正模型與現有流程接線效果，不需為此繼續廣泛搜尋。

本次驗證：補測以 `--verify` 重跑與新封存 JSON 一致；原 CT10 比較亦重跑完成；產品碼／依賴與 HEAD 無差異，改動無 whitespace error。獨立唯讀 review 核對新文案、fixture、SDK／腳本 hash，無需修正 finding；該 review 未重跑 SDK 或執行 Rust。失敗時顯示原 source 只是探針呈現，不是資料庫 rollback／原子性驗證。
