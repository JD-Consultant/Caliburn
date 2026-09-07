# CT19：路由提示局部校準與舊問題回歸

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **局部候選失敗並撤回；帳本closed，G8 OPEN**

## 1. 唯一範圍與依據

Owner核准[CT18§4](2026-09-08-ct18-live-repair-selection-diagnosis.md#4-下一個局部候選待確認未施工)，並提醒修改可能帶回舊BUG。本輪只整理一組讀取／C即時修補／B背景通知的路由及完成條件。不新增Agent、欄位、強制tool choice、字串分類器或排程；不改JD／production。保留[CT17](2026-09-08-ct17-correction-persistence-calibration.md)原失敗與封存。

本題目前register持續更新於[主repo入口](../../../../docs/current-decisions.md)，不是worktree內歷史快照；本輪也在worktree登記頁加上閱讀路由，避免誤讀成未記錄。

研究承接CT18§2完整證據，不重研ABC。主要依據：[OpenAI提示精簡](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#simplify-prompts-first)強調移除衝突／重複但保留完成條件；[Anthropic工具排錯](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use#claude-calls-the-wrong-tool)要求清楚區分何時使用不同工具；[OpenAI Memory](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)及CT18核對的官方SDK同輪修補指令提供政策先例。這些支持候選方向，不證明模型必然選對。共享讀取規則只停止多餘查找，不替唯讀reader加寫入義務。

## 2. 檢查順序與停止條件

1. 先用封存CT17第一輪確認「說對5日≠Memory已改5日」仍是失敗；不付費重製已存在baseline。
2. 修正三處既有提示的歧義，其他產品碼不動。
3. 離線重跑工具框架／精確patch／原子失敗／保留未改案例／新版本壓過舊工具回饋／通知去重／引用與原文回查；不能把prompt字串出現當語意成功。
4. 真測用同一CT16歷史資料的全新DB副本，Luna／medium，最多24次／US$0.10（含背景及重試）；沿真正服務入口，不強制工具，不在員工文字暗示repair_memory。測漏存後重述、新明確更正、已保存純重述，核對知識及導覽、其他資料、Q/A原文及引用。
5. 若路由仍錯，保留反例、停止本候選；不在同帳本不斷改prompt。測試限額不是產品限制。技術completed也不是完整職務理解驗收。

## 3. 結果

**候選未修好漏存，不採用。** 首個與CT17相同的更正、相同起始Memory，仍只有回答改5日，正文／導覽維持10日。已撤回本輪三處提示到施工前版本，未改其他程式或原資料。

證據：[完整去敏請求、回應、原始Q/A audit、候選diff及來源hash](evidence/2026-09-08-ct19-routing-regression.json) · [可見逐字稿](evidence/2026-09-08-ct19-routing-regression.transcript.md)。JSON SHA256 `7fa37de0ae37638f5f74ddd272789272b4fcec4e611da340f76d6053c4fb740c`；原CT17保持closed且未變。

| 檢查 | 結果／限制 |
|---|---|
| 原失敗斷言 | 封存CT17第一輪預期5日失敗，第二輪預期7日通過；不是只查prompt文字。允許日期空白，不把格式差異當語意失敗 |
| 自然更正 | Luna／medium，1次HTTP200/completed、0工具；可見回答5日，Memory仍10日、rev3，背景idle。沒有patch或DB錯誤可供重試 |
| 實際入模資料 | 含本輪讀取停止／C指令、guide10日、本轮更正5日；工具名稱包含C/B。未記錄完整wire schema／tool_choice，不宣稱知道opaque推理內容 |
| 原文及引用 | 原42則可見Q/A＋本輪2則全等；4份詳記的source/context分頁全部與canonical原文切片全等；Memory正文／導覽逐字未變 |
| 舊BUG安全網 | **583 passed、0 skipped、94.12s、1既有Starlette警告**，含本地專用PostgreSQL。涵蓋真框架工具接線、官方patch結尾／定位／原子回退、保留其他案例、stale刷新、新guide不被舊C覆蓋、通知去重、原文回查等。使用合成provider，不能當自然語意通過 |
| 費用 | 1／24次；usage估 **US$0.00253030**，非帳單保證。停止後沒有加碼或改模型 |
| 未執行情境 | 新更正5→7、已保存重述7：首個正例已失敗，依停止條件未再付費；不能算通過或失敗 |

最初離線52 passed／15 setup errors為Windows暫存權限；重新授權執行後542 passed／41 skipped（尚未配置DB），最後接專用DB完成上述583項。封存腳本第一次誤比較整個snapshot（包含新增訊息數），斷言失敗且尚未封存；改為比較knowledge／guide／revision／processed_source／background，原文新增另由逐字audit檢查。此為測試脚本修正，不是產品修正或回填模型失敗。

## 4. 獨立審核與處置

Reviewer重看實際input、程式與結果後確認不能promote，也未發現可證明的接線回歸。另指出候選的B fallback「允許次數內確實失敗」可能讓模型第一次可重試失敗便轉B；核對`MemorySession._command`確有首次`retryable=True`，因此列為**靜態風險**，不是本次零工具trace已發生的錯誤。整組候選已撤回，未追加第四組prompt修改。撤回後三個產品檔與HEAD的git diff為空，另跑live-memory／memory-patch／consolidation-request共**52 passed／8.24s**；這是還原後接線確認，不把候選的583項算成撤回後重新執行。

583技術測試不能證明先前案例混淆、未知變沒有、自然動作選擇已修好；本次沒有Memory寫入，所以「其他細節未變」也不證明下次修改一定能保留。CT15既有品質OPEN仍按原記錄追蹤。本輪只消除了「這三處提示整理足以修好」這個候選，不否定ABC或官方Memory概念。

下一唯一gate：就漏選動作的實際反例另提有官方依據的局部選項，經Owner討論後再改；不直接新增完成檢查Agent、forced-tool分類器、timer或其他新機制。未重跑整份長訪談，未宣告可上線。

## 5. 執行安全與來源

真測安全檢查：第一次執行遭auto-review拒絕，擔心歷史員工敏感資料外傳，尚未送出模型請求。已唯讀追溯：CT19複製CT16，CT16複製CT15資料庫`q019_ct15_b67f0995de`；CT15 runner從空白建立「CT15 合成售後營運專員／整份職務長訪談」，[CT15逐字稿](evidence/2026-09-08-ct15-full.transcript.md)明示「合成案例，非真實員工」。本輪完整讀取CT16中21則員工測試輸入，皆為雲杉／海鷗／石橋／青禾的合成小家電售後情境及後續測試更正；本輪沒有production匯入或真實員工資料。依這項可查證的來源說明再申請同一動作，未繞過拒絕或更換目的地。預定目的地仍為已核准模型測試的OpenAI Responses，金鑰只用授權header，不進payload／紀錄。
