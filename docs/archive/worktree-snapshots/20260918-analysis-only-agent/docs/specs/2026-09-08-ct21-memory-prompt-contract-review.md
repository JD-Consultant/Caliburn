# CT21：完整 Memory 提示契約對照（施工前）

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **Owner同意CT20方向；G4候選待審，未施工、未真測，G8 OPEN。**

## 1. 先看結論與邊界

這次有一份能逐字比對的候選，不只是「再把提示寫清楚」。變更僅涉及既有提示的位置、重複條件及工具使用／回傳說明。**沒有證明這樣能修好漏選工具；不以官方指引冒充效果保證。**

- 完整[目前system＋6工具定義](evidence/2026-09-08-ct21-memory-prompt-current.json)。
- 完整[候選A1 system＋6工具定義](evidence/2026-09-08-ct21-memory-prompt-candidate.json)。兩份皆為審查文件，程式不會讀入。
- 已研究的官方事實與差異只見[CT20](2026-09-08-ct20-official-memory-tool-prompt-audit.md)；上次失败的實際diff／trace保持在[CT19](2026-09-08-ct19-routing-regression.md)。不重研ABC或取得新付費授權。

本輪唯一問題：**這份A1是否比CT19多了值得驗證的實質差異，同時不破壞舊保護？**產出是完整候選供Owner審核，不是改架構、模型或測試容量。下一步通過審核才施工；模型驗證費用範圍另確認。

## 2. 對照如何取得，不是假裝捕捉原CT19

基準`b5b78ba6`。以現有`test_live_memory.h`的`httpx.MockTransport`、記憶體Saver／Store與SQLite，在`build_conversation`中加入真正`SkillsMiddleware`和`MemorySession`，只讓合成provider回傳一次固定答案；沒有外部生成。主顧問文字以AST取得`api.open_service`傳給`AnalysisService`的完整literal，未手抄或執行`open_service`、未讀key。

捕捉到一則system、3個文字block及6個完整tool schema。只把合成的導覽正文、版本、當輪來源地址正規化為兩份一致的`{{...}}`標記。**不是要求模型填標記，也不是CTX總量／舊CT19 HTTP重現。**既有對話、opaque compaction／reasoning、後續tool results繼續依原流程提供，不從這份文件重建或改寫。

實際service還有`BackgroundAvailability`條件注入：只有儲存的notice非空時才附上背景可用性文字。JSON另列完整固定文字、條件與可選target reference行，不假裝它出現在這次正常mock input。`CooperativeStop`與預算／錯誤處理不新增system內容，本輪不修改。這層也不能為了讓提示看起來簡短而刪掉。

## 3. 改動地圖：保留／移動／修正

| 位置 | 候選處理 | 和CT19的關係／依據 |
|---|---|---|
| `api.py`顧問提示 | 工作理解、自然追問、未知、案例邊界、收尾、不做JD等全部保留；最後重述B通知的兩句移到下方Memory actions，不另加第二份判準 | **新增差異**：CT19未改主顧問入口；去重不刪真正完成條件 [O1] |
| `MemorySession`的system | 先列本輪Memory動作，再列讀取版本規則、按需讀取方法、原有動態導覽／来源地址。把B工具裡的實質資訊與通知時機集中到這裡 | **新增差異**：讀写條件在同一处比較，不藏在不同工具說明互相指向。這是本案映射，非框架強制路由 [O1][O2] |
| C工具`repair_memory`說明 | 第一段直接說是修補已讀的核實過時事實；其後保留參數／原子性，明說導覽的事實與路由都要修正 | **新增差異**：CT19未改C工具description；對齊WHEN／WHAT／HOW [A1] |
| C工具的錯誤契約 | `applied`即已發布，不重做；`invalid_edit`／`stale`且`retryable=true`按detail/read_paths修正；`no_memory`交B初始化；**失敗且**不可重試／repair_limit才走B補救，通知回執仍不是已保存 | **新增差異**：CT19第一次可重試失敗的靜態風險現已具體處理；完全依現有`RepairWorkflow`／`MemorySession._command`回傳，沒有另造狀態 |
| B工具`request_memory_consolidation` | 只保留適用邊界、無參數、收到請求≠整理完成、不等待；職務資訊選擇及通知時機移到system | **新增差異**：CT19是在原長說明上換幾句，這次是分離使用政策與工具契約 |
| 共享讀取停止句 | 足夠回答就停止多餘查找，但不取消必要Memory動作；其餘逐層檢索、原文回查、未知及案例邊界不變 | **與CT19重疊**，不當成新假設。獨立唯讀reader仍沒有寫入義務或C/B工具 |

整體目的是減少相互競爭的判準，**不是再新增強制工具、每輪分類器或Agent**。同輪仍可有C修補加上其他新工作資訊的B通知；「已修補不重通知」只針對同一已保存更正，不吞掉同輪其他進展。

## 4. 必須逐字／逐結構不動的部分

- 6個工具名稱、每個工具schema及參數：保持完全相等。C仍只有`edits[{path,diff}]`；B仍空參數；不加LLM填寫的ID、理由、驗證欄位或Skill ID。
- C附帶的整段`PATCH_GUIDANCE`＋`MEMORY_EDIT_GUIDANCE`：逐字相等，包括V4A格式、read_file顯示行號、定位歧義、重讀修正、原子失敗、保留未被更正的工作細節及引用。**不因OpenAI說可刪無效範例，就刪掉既有patch格式例子。**本輪沒有加新的路由few-shot。
- 4個讀取工具說明、完整Skills清單與指引：逐字相等。不新增工具、不強制每輪讀所有Skills或Memory。
- 初始讀取版本與當輪C回饋的優先規則：原文保留，歷史tool feedback不得壓過新回合初始視圖；動態data block位置仍在Memory段末。
- 背景可用性提示、原始對話、opaque reasoning／compaction、引用解析、工具實作、失敗／重試上限、B1/B2提示、發布規則：不改。

草稿自審另修正過一個文字問題：不能單看`retryable=false`就通知B，因為成功`applied`也會帶false；候選現在限定**失敗的repair**。這是尚未執行的設計修正，不是發生過的產品BUG。

## 5. 文字與成本，不誇大精簡效果

以兩份正規化審查JSON的system文字及tool description計算（不含schema、動態資料、歷史、背景可用性及metadata）：

| | 目前 | 候選 |
|---|---:|---:|
| system文字字元 | 4,002 | 4,617 |
| tool description字元 | 5,518 | 5,576 |
| 合計 | 9,520 | 10,193 |

**多673字元，約7.1%，不是更短的prompt。**初稿更長，已去掉重複措辭；保留新增WHEN及真實錯誤分支的明確性。中文／英文混合，字元不是token，更不是費用；沒有證據可承諾省錢。兩份schema相同、沒有增加固定模型輪次；實際修補需要工具後續生成，與「零工具就結束」比較必然要另外量成本及正確性。

若Owner覺得這份差異不足以抵銷再試成本，可不採用；不以「用了官方原則」硬推。這輪不拿高字數當成功，也不再擴大研究。

## 6. 通過審核後的最小驗證與停止點

1. 先確認施工後實際system＋tools與此候選一致，保留原prompt及CT19反例；不能只測文字常數存在。
2. 既有離線安全網核對：成功applied不走B、首次可重試失敗不直接跳B、no_memory、stale、不可重試失敗、同輪C成功＋其他新資訊仍可B；工具參數／patch／原文引用／初始視圖不回歸。這驗框架接線，不代替模型判斷。
3. 確認付費範圍後，再用Luna／medium小測自然新更正、對話已改但Memory未改的重述、已保存純重述；保留其他案例，未知不變沒有。不在員工話中提示工具名或正確路由。
4. 若仍出現相同漏選反例，就封存停止，不逐句加提示重跑。只有局部語意回歸通過，才回到長訪談驗收；不先宣稱整份工作已可穩定理解。

**本輪僅完成完整對照設計與靜態檢查，未執行上述施工／語意驗收。**

2026-09-08落盤後再核對：兩份JSON可解析；6個工具除description外完全相等；4個讀取工具、Skills block、C的V4A＋細節保留指引、背景可用性文字與request settings逐字／逐結構相等。字元數由落盤JSON重算，與§5一致；本稿所有本地連結可解析。`src`／`tests`對HEAD無diff，沒有為文件審查重跑付費或整套回歸。CT19 evidence的SHA-256仍是`7fa37de0ae37638f5f74ddd272789272b4fcec4e611da340f76d6053c4fb740c`，原失敗未覆寫。這些只能證明候選邊界與檔案一致，不能證明模型會正確選工具。

獨立只讀設計審查（Lorentz，2026-09-08）：未發現阻礙交Owner的文件矛盾；已核對C結果分支、同輪C/B邊界、舊保護及成本表述。評定僅為「可交Owner審候選」，不是批准施工或宣稱修好。實際路由仍須施工後接線驗證及自然模型小測；A1與CT19在效果上仍可能重疊，保留§6的停止條件。

## 7. 來源、效力與退出

- [O1：OpenAI GPT-5.6提示精簡](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#simplify-prompts-first)：本輪重新fetch；刪無效重複但保留路由／完成條件，不承諾改prompt必定有效。
- [O2：OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)：system描述何時／何時不用、工具描述真實參數與輸出，推理模型範例可能傷害表現。細讀與live-update官方SDK證據承接CT20§2／§5，不重新推測內部實作。
- [A1：Anthropic Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#best-practices-for-tool-definitions)：WHEN、參數和限制要清楚；不把其專用Memory API自動提示視為Luna已取得。
- 目前實作對照：[主顧問入口](../../experiments/analysis-agent/src/analysis_agent/api.py#L150)、[Skills](../../experiments/analysis-agent/src/analysis_agent/skills.py#L66)、[Memory提示與結果接線](../../experiments/analysis-agent/src/analysis_agent/live_memory.py#L38)、[B工具](../../experiments/analysis-agent/src/analysis_agent/consolidation_request.py#L15)、[背景通知](../../experiments/analysis-agent/src/analysis_agent/scheduling.py#L195)、[修補結果](../../experiments/analysis-agent/src/analysis_agent/repair.py#L34)。實際固定點以本稿基準commit及JSON為準；行號日後可能變。

Decision：Owner同意把CT20方向展開為完整候選；Status：G4待審。Reason：有可對照的新位置／工具契約差異，也明列與CT19重疊，不把結構整理當語意保證。Affected：本稿、兩份審查JSON、register入口；產品無變更。Reopen：Owner不接受差異／成本或審查發現丟失既有保護。Next gate：Owner審閱後才進隔離局部施工與另行核准的真測。
