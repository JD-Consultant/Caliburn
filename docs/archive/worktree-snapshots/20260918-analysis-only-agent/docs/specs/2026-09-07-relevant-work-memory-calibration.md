# CT-06：保留工作資訊、正常訪談與記憶回查

2026-09-07 · LLM-Q019 · isolated G5/G7 · **局部內容驗收通過，背景操作效率仍OPEN；付費已停止。**

入口：[current decisions](../../../../docs/current-decisions.md)；目的／資訊取捨／職務分析來源由[研究](../../../../docs/specs/2026-09-07-work-case-and-understanding-information-selection.md)持有，施工由[短計畫](../plans/2026-09-07-relevant-work-memory-calibration.md)持有；[完整實驗證據](evidence/2026-09-07-relevant-work-memory-calibration.json)保存合成訪談、請求、工具結果、實際記憶及費用。此頁不複製整份舊研究。

## 1. 核准與改動

Owner核准：保留的是工作案例中用來理解實際工作、本人責任、頻率、條件、成果／判準等資訊，不是所有聊天瑣事。新帳本最多24次Luna／medium、US$0.10，包含背景與重試，不接JD／production。

- **B1抽取**：沿用三個文字欄位；明示工作相關資訊取捨、頻率／觸發、低頻與案例範圍。個案日期／耗時不推成通則，不因同時提及就加因果；系統紀錄日期與員工工作時段分清。
- **B2整併**：沿用現有增量維護，依目的／行動／成果／責任歸納，保留案例的重要差異；無關瑣事可以省，舊工作不能因本輪未提及而撤銷。
- **C及B2共用編輯提示**：保留未變的工作相關內容與引用；已核對並補入官方read_file顯示行號／分隔空白不是原文縮排的說明。
- **主顧問**：簡短回述、優先追問會影響理解的一項未知，避免重問、逐欄問卷和未經支持的因果／通則。

三份分析Skill已符合方法方向，本輪不改。沒有新增Memory層、schema欄位、tool、Agent或語意verifier；未改原始對話、reasoning／compaction、發布／併發規則或產品上限。

## 2. 直接依據與適用邊界

- [OpenAI GPT-5.6 prompting guidance](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)：依trace做小範圍調整，明示成果與需保留的事實；不整套重寫。**本案資訊清單是職務分析映射，不是各廠逐字共識。**
- [Codex Phase1](https://raw.githubusercontent.com/openai/codex/main/codex-rs/memories/write/templates/memories/stage_one_system.md)、[Consolidation](https://raw.githubusercontent.com/openai/codex/main/codex-rs/memories/write/templates/memories/consolidation.md)與[Anthropic memory提示](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance)：承接既有研究的資訊選擇、詳細脈絡、增量保留與組織目的，不複製coding專用欄位或淘汰政策。
- **新發現另核對框架底層**：[Deep Agents filesystem公開原始碼](https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/deepagents/middleware/filesystem.py)，`_READ_FILE_TOOL_DESCRIPTION_TEMPLATE`／edit說明；本機deepagents **0.7.13** 的 `backends/utils.py::format_content_with_line_numbers` 實際回傳「行號＋兩空白＋原文」，`perform_string_replacement` 仍是精確匹配。解法先補工具使用提示，不偷改原文縮排、不加模糊匹配。
- [LangChain ModelCallLimitMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/model_call_limit/ModelCallLimitMiddleware)：thread_limit與error停止是框架的成本控制；不能把達界線當作完成。此次透過既有constructor只把兩次**診斷**恢復上限改為12，保存的呼叫計數未歸零，產品預設8不改。

2026-09-07核對；公開main可能變動，本機版本列明。API Reference搜尋可讀，但頁面直接抓取回報markdown content-type不支援，因此限制語意並交叉檢查本機框架／既有接線；不假稱完整讀到未取得頁面。

## 3. 實際驗證，不混淆回答、保存與發布

| 階段 | 新帳本請求 | 結果 |
|---|---|---|
| CT05既有恢復點 | 0 | B1已完成，B2仍停consolidate，current revision3。未重抽舊來源。 |
| 接續CT05更正 | 1–4 | 前3次又讀正文、改導覽、可選預檢，達產品8步。僅診斷放到12後再1次完成，發布revision4；此B2跨兩帳本共9步，計数未重置。C週五至少兩晚／平日一晚正確，A/B舊內容保留，舊導覽錯誤路由已修。 |
| 正常API新增D案例 | 5 | 1次模型／0tool，正常完成。分清每月第一工作日維護、每年一次搬移、某週五一次兩小時；追問每月測試是否還需主管正式確認，未重問已知事項。本輪模型**未通知背景**，不能稱排程全自動驗收。 |
| D抽取與整併 | 6–17 | 診斷程式將已保存未處理範圍交給既有B1/B2，非新增每輪強制整理政策。B1一次成功。B2有4次帶入顯示空白的精確匹配失敗，框架回錯後模型修正；8步未完成，診斷放到12，最終11步／發布revision5。不是改資料庫或跳過最終驗證。 |
| 獨立Memory回查 | 18–22 | 全新reader，不帶近期訪談，僅導覽＋問題＋既有工具；3次grep、1次read_file、1次回答。A/B/C/D責任、不同逾時欄位、頻率與更正可找回；D每次維護耗時未知，未拿單次兩小時代替。共同工作可歸納，未把四客戶當四固定職位。 |
| 空白指引微測 | 23–24 | **未完成編輯，不能稱指引有效。**23已讀正確正文，診斷程式卻把FileData字串當行陣列判讀。修正診斷後，24重用真讀取結果，但模型先讀導覽；兩次都未編輯。此微測是短暫StateBackend，不改已發布記憶；未重播opaque reasoning，不用它證明推理延續。達24次停止。 |

**內容與引用核對：**D詳記／候選保留前後端責任、每月檢查做法、測試資料交接、年度搬移與不能刪正式資料的界線；少見工作未丟掉。午餐品項／牆色未進詳記與正文，原始來源仍保留；詳記末句說明已排除閒聊屬非必要贅語，不算工作事實。新增D後，已發布A/B/C原有文字全部仍在（本次fixture檢查，不要求產品永遠字面不變）。7份正文引用皆實際讀回詳記及來源。未知保存為問題，不當已確認事實。

**費用：**24次皆HTTP200，估 **US$0.02428753**，input159,608／output7,258tokens；所有呼叫合計，不是單輪訪談成本。依[官方standard定價](https://developers.openai.com/api/docs/pricing)：每百萬Luna input0.20／cached0.02／cache-write0.25／output1.20美元及實際usage估算，非帳單。新帳本已關閉；未自動追加。

## 4. 安全網、問題與下一步

基線92passed；提示修改後完整547passed。補官方顯示／編輯边界測試：帶錯空白回錯，正確子句替換成功，真正巢狀縮排仍在；**這是實際工具契約驗證，不是假模型已學會新提示**。最後完整回歸 **548passed／0skipped，72.59秒**，含專用PostgreSQL；compileall及diff check通過，僅既有Starlette／AnyIO deprecation warning。獨立審核主diff與最後增量未發現Critical／Important；文件時態已釐清。審閱者將72.59秒誤讀為72skipped的建議已依實際pytest輸出拒絕，不覆寫真實計數；review不代替模型語意驗收。

- **CT05-Q01 CLOSED（限定發布驗收）**：既有C更正已完成並可從獨立Memory回查；閉環成立，但靠診斷12步完成，不能推成預設8步足夠。
- **CT06-Q01 OPEN／下一個唯一優化問題**：B2讀寫效率／步數適配。本輪已定位顯示空白混入、重複讀取與可選預檢；新空白提示的語意效果未驗成。下一輪先用本次保存的工具結果作最小讀改對照，核對框架官方tool description是否足夠，**不再重跑整套訪談、不直接放寬精確匹配、不只拉高次數掩蓋繞路**。若需改工具呈現／產品上限，依結果討論，不改成每輪整理。
- **Minor OPEN**：回查把C「日期／房型仍在」說成「仍然有效／仍在」，多了來源未支持的有效性語意；正文未添加此判準。正文新增案例後保留「兩案」的舊稱，有歧義可後續局部整理。這些不是資料層漏存，不能宣稱零幻覺。

尚未驗任意長訪談實際觸發native compaction、多工作領域、持續多輪自然觸發背景之穩定性、JD／UI。原生reasoning設定仍為medium／all_turns，不把設定存在或小測通過當成永久完整記憶保證。未merge/push、未接production；這次是可保存的局部進展，不是整個顧問產品驗收完成。
