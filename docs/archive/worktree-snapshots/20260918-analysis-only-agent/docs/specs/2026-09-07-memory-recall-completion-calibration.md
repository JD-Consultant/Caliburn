# CT-03：記憶回查完成率與步數校準

2026-09-07 · LLM-Q019 · G5／G7 isolated；回查單樣本完成，讀取提示局部改善，非完整長訪談驗收。

入口：[current decisions](../../../../docs/current-decisions.md)。前置證據：[CT-02](2026-09-07-native-context-normal-interview-results.md)。本稿只處理回查完成率／局部讀取效率，不重選 ABC、Memory 格式或 Provider。

## 1. 本輪有效決定

- Owner 澄清：既有 9-model／8-tool 不是不可更動的產品要求；可以依效果、成本及完成率調整。原實驗 12 次／US$0.10 是該次測試界線，不是永久產品規格。
- Owner 已核准：先沿用既有工具／提示完成最小對照；必要時才局部優化。新試驗 Luna／medium，合計最多 **20 次生成請求、US$0.10 費用預留**，SDK 重試一併計數。達任一界線即停；此數值同樣不是產品限制。
- 不接 JD／production、不重跑背景整理、不重啟 Docker、不換模型；保留原生推理、原文、按需逐層讀取與框架錯誤處理。

## 2. 診斷與直接來源

1. **已觀察事實：**CT-02 的三輪訪談用了 6 次，獨立回查僅剩 6 次；最後呼叫詳記讀取工具後，第 13 次請求被測試帳本擋下，沒有最終答案。不能據此認定模型不會回答或 Memory 遺失。
2. **OpenAI 官方：**[tool-calling flow](https://developers.openai.com/api/docs/guides/function-calling#the-tool-calling-flow)明確分開模型提出工具、應用執行、帶結果再次呼叫模型；可以依任務需要重複，不存在通用 6／8／9 次標準。
3. **框架官方：**[LangChain model/tool limits](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)支援可調的 invocation／thread 上限；用來控制失控與成本，不替產品指定正確數字。隔離程式在每次員工輸入的子圖使用持久 thread counter，因此恢復不重置額度、下一則輸入另算；不是整份文件一生只能 9 次。
4. **Anthropic 官方：**[工具工程](https://www.anthropic.com/engineering/writing-tools-for-agents)建議檢查實際呼叫、結果資訊、token／錯誤，再改善說明與有界回傳；也提醒工具使用策略不是唯一。2025-09-11 工程原則仍公開，不稱它為 2026 新 API。
5. **既有研究：**完整回看 [OpenAI progressive disclosure](../../../../docs/specs/2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md)：小導覽、相關正文、詳記、必要才原文。quick pass 的 4–6 個搜尋步驟不是含回答的總模型上限；本輪不重開該稿歷史候選。
6. **實作核對：**Deep Agents 0.7.13 的 `grep` 是 literal、`read_file` 原生有分頁。沿用既有工具，不拿 `A|B` 冒充批次 regex，不為單一樣本新增檢索器。上次正文 1095 字；連續多次 grep 與 ls 已知目錄是可研究的效率候選，不是已證明的錯誤。

## 3. 最小對照及停止條件

先重用已生成且保留來源的合成 Memory、相同問題、相同 read prompt，fresh model context 不先提供原訪談；獨立給完整回查最多 20-model／19-tool 測試空間。20 不是期望用滿。先看自然完成需要幾步、答案有無串案／漏掉更正／捏造未知；若完成且成本合理，不能因多幾步便強迫改架構。

若有明確繞路，再比較既有工具的讀取指引；不把第一次隨機路徑當必然結論。不得靠把全部原訪談塞 prompt 使測試虛假通過。保留資料、工具結果、usage 及遮除 opaque 後的證據。此 independent reader 不等於完整 API 重開、背景品質或長 context 壓縮验收。

本輪基線：既有 `test_memory_read_path.py`＋`test_native_context_budget.py` **34 passed／4.07s**，零生成；一項既有 Starlette deprecation warning。

## 4. 結果與下一 gate

合成原訪談、真模型答案、工具輸入／結果、usage、腳本與指紋分開保存於[實測證據](evidence/2026-09-07-memory-recall-completion-calibration.json)。真 OpenAI 直連 `gpt-5.6-luna`／medium；三段共用同一 20 次／US$0.10 帳本。沿用 factory-owned 模型，fixture 的 Saver／Store 在記憶體中；沒有重跑 B1／B2、改寫案例內容或把原訪談預塞新 Context。重新建立文件、來源與檔案地址，是同內容對照，非逐 byte 相同的 seeded 實驗。

| 測試 | 模型／工具次數 | 結果 | usage 估算費用 | HTTP 耗時合计 |
|---|---:|---|---:|---:|
| 原讀取提示，放寬測試停止條件 | 9／8 | 完成；A/B、補充、更正及未知回答正確 | US$0.00528078 | 26.10s |
| 新條件式讀取提示，相同廣泛回顧題 | 5／4 | 完成；相同核心資訊保留，沒有串案／編造天數 | US$0.00270576 | 12.91s |
| 新提示，明確要求更正的員工原句 | 4／3 | 找到原句且逐字返回，但多帶下一則員工補充 | US$0.00197861 | 7.80s |

原提示：ls → 正文 → 詳記 → 詳記 → 原文 → 原文 → 詳記 → 原文 → 回答。新提示：grep 三次 → 正文 → 回答。後者依然不是最少理論步數，不為追求兩次而再堆提示。兩個回答都保留：A 單次付款、付款失敗保留資料／手機復原連線驗證；A 無障礙檢測同事出清單、員工修正、同事複查；B 月租／三種角色權限／後端同事備份；兩案不同驗收人、未知驗收天數；搬設備是一次性往事而非目前固定工作。

**推論界線：**本樣本支持先前測試過早停止，以及條件式深讀可能減少無必要往返。單次前後對照不能證明穩定降低 49% 費用；模型路徑、快取、動態地址與時間都可能影響結果。9 次基線也剛好落在現有產品 9-model／8-tool 內，故本輪沒有證據要求立刻更改產品預設；**不是不准提高**，後續真入口若反覆觸頂可用既有 framework 設定調整。

## 5. 實際改動與驗證

只把共同讀取指引抽成一份文字，供 `memory_access` 與真正 A 的 `MemorySession` 共用，避免只改測試 helper。沒有新增 tool、檢索器、summary Agent、LLM 必填欄位或手工 token 裁切。條件式讀取：

- 導覽已在 Context；已知路徑可直接有界讀取，ls 用於未知位置。
- 窄問題可 literal grep；廣泛回顧可有界閱讀正文，命中缺脈絡則開相關段落。
- 正文足夠可回答，不把所有引用當必讀任務。缺細節、爭議或要求核對才往詳記；需要精確原句／問答脈絡且上層不足才查原文。
- 無命中不證明不存在，詳記仍是歷史切片，先看目前理解中的更正；有矛盾核對或詢問，不能自動「越新越真」。C 刷新／版本／来源邊界原樣保留。

這是以官方 progressive-disclosure／工具資訊效率原則，對本案提示做的局部校準，**不是 OpenAI 或 Anthropic 逐字共用的唯一 prompt**。真模型基線作為效率問題重現，前後消費者行為作提示校準；沒有用「原始碼包含某句」冒充行為測試，也沒有新增重複測試。

既有讀取、Live Memory、完整 Context／native 模式回歸 **113 passed／11.59s**；完整 **547 passed／0 skipped／86.84s**含專用 PostgreSQL，模型 HTTP 全合成。compileall、offline lock（83 packages）、diff check 通過。一項既有 Starlette deprecation warning，無新增 failure。獨立唯讀 review 無 Critical／Important，可接受本次局部提示變更；下列單訊息引用的 minor 仍 OPEN，沒有證據歸因於此次變更，不阻擋本切片保存。

合計 **18 次生成／usage 估算 US$0.00996515**；input 56,397、output 2,691 tokens，reasoning 不另外重算。18筆 response 均 HTTP200／completed／default tier，無 counter HTTP。費用依[官方 Standard pricing](https://developers.openai.com/api/docs/pricing)與實際 usage 計算，不宣稱帳單實扣；上限未用滿即停止。

## 6. 剩餘問題與停止點

- **CT03-Q01／minor OPEN：**指定「那一則原話」時，模型雖未改寫且無混入 AI 問句，卻多引下一則員工補充。原文路由有證據；單則選取精準度不能寫成全部通過。後續回答提示校準時處理，不能把它當 Memory 資料遺失或另發明儲存層。
- 新提示尚未以有真 Memory head 的完整 API 訪談驗收；本輪使用與正式隔離入口共用的指引＋實際框架 reader，離線整合驗證 A/C 接線，不冒稱已跑 root API 的同一真測。
- 長訪談原生壓縮、背景整理與多輪回查整體品質仍 OPEN。下一 gate 是將本次已校準提示帶入正常 API 訪談情境，並觀察上限是否真的不足；不回到框架／Memory 選型重複研究。
- 未接 JD／Web／production、未 merge/push、未清除資料或重啟 Docker。本次只保存局部改善，不宣稱整套產品已驗收。
