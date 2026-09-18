# CT41：新鮮讀取與一致更新的局部優化／訪談回歸

2026-09-09 · LLM-Q019 / CT40-Q01 · G4→G5→G7→G8（隔離 app）

## 本輪 preflight 與授權

- 目標：背景已更新後，A 的修補使用目前受影響正文，確認已回答內容不再留為未知，不新增同義段落。
- Owner 最新授權：持續優化與測試，局部可自行決定；重大改變才詢問。可比較 high／xhigh／max，但先不全面升級。
- 已讀：[CT40完整結果與時間線](../specs/2026-09-09-ct40-normal-interview-results.md)、現行 MemorySession／共用讀寫提示、既有接線測試、root current register／decision-process。
- 範圍外：JD、production、Memory架構、全域新驗證器、原話保存、重開CT35停放的專用final攔截。
- 實驗總護欄：Luna最多160次生成／US$0.75（局部最多60／0.25，服務續訪最多100／0.50），不是產品限制；保留失敗、未知費用，不重開舊帳本。

## 直接官方依據與映射

1. [OpenAI GPT-5.6 prompting](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#tool-routing)，本日全文核讀：正確性依賴取回資料時，明確寫先決條件；指定成功標準，逐一小改並重跑原失敗。先校準路由與驗證，再以代表情境選effort。不是所有情境都加high，也不宣稱官方保證正確。
2. [Anthropic Memory prompting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance)：先查看Memory，維護內容最新、一致；必要時強化提示而非重複全部規則。[編輯回饋](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#str_replace)可含修改片段，但它不是本案patch引擎。本輪先沿現有read_file驗證，不增加另一套編輯器。
3. [LangChain context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)：現行MemorySession已在官方middleware組裝system／tools。這輪只改此處提示，不改checkpoint歷史或自行修改opaque reasoning。

**本案映射，不冒稱官方逐字規定：**舊工具輸出是讀取當時的快照；本輪修補前先讀当前受影響正文，再就地更新原議題；只有真正新主題才新增。成功代表目前正文／導覽一致、其他有效細節仍在；以最小範圍回讀確認，不每次讀全Memory。

## 執行與退出條件

- [x] 完成baseline與合成舊快照／實際訪談對照；同主題新舊未知並存確實重現，原失敗保留。
- [x] 局部改live repair提示，保留工具schema。原「B提示不變」範圍由下方實測診斷擴為B2一致性及既有工具選擇校準，沒有新model欄位／新Agent。
- [x] 同情境high兩次、未核實／已正確及兩案例反例已完成；不將接線測試當模型必然遵守。
- [x] medium／high均有保留的失敗；停止單純加effort，改核對既有工具路由。未使用xhigh／max。
- [x] 最後556離線＋41真PG通過；11輪原訪談、3輪新職位、独立回查與原生compaction均有證據。原11輪失敗後的恢復不能算新長訪談通過。
- [x] [結果／來源／限制](../specs/2026-09-09-ct41-memory-edit-freshness-results.md)及機器證據、逐輪問答已封存；226次估US$0.30844346，三帳本closed。整體G8仍OPEN；最後版全新長訪談另記CT42。

本輪不擴張架構；程式只在既有隔離worktree改提示。測試腳本是實验工具，不接產品。

## 執行中修正（仍屬局部授權）

- 合成高推理兩次主要結果通過，但都先誤改、收到錯誤才讀正文；審核CT41-R01要求分開記錄，不能宣稱freshness已修好。未核實案例的新不確定說法可以更新，原「必須no-write」實驗斷言不成立，保留原失敗再附人工判讀。
- 真API前3輪：A/B1/B2 high。B2第三批反覆格式／原文不符，8次上限中斷。改為A high／B1 high／B2 medium，使用既有LangGraph resume，**保留原累積計數**，僅該失敗批測試上限8→12→16→20；第18次完成。不是重新抽取，也不是每次重置計數；產品8次上限未改。此測試不能用來宣稱medium單独使該批恢復。
- 為避免將A提高時連B2成本一起提高，在既有SDK binding增加獨立B2 effort，預設medium，沿既有extraction_model注入形狀；沒有新agent／fallback loop。已補預設／非法設定的RED→GREEN回歸。
- 第4輪A修補失敗後如實表示背景尚未完成，再由自然B以5次B2呼叫發布更正；接續正常訪談，不重跑前4輪。
- 直接依據：[LangChain官方call limit](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)的thread_limit是同thread累積，不是每次resume重置；上限是成本保護，不是品質保證。SDK原文不匹配不做模糊替換。

## 完整訪談後的局部收斂（同一 CT40-Q01，2026-09-09）

- 11輪真訪談完成，空近期Context讀者發現「雲岸部署已確認／仍未知」並存；B2已讀完整舊正文，故不是Context缺失。只替換B2兩句：更新同一事實在共同模式、案例及待確認的各個出現處；保留真正不同的未知。原B1重播以medium 5次完成，尚不當作新長訪談通過。
- 經既有重新抽取／整併維護路徑套回測試DB，B2因導覽複製長引用抄錯，再次撞8次上限。保留該失敗、沿原checkpoint續跑，test-only cap14；未改產品預設8、未手動填入Memory。局部probe已closed28次；續測服務請求上限132→192，**合計220次／US$0.75總費用上限不變**，事先向Owner說明，依其局部自主授權執行。
- 小型導覽局部校準依據：本日核讀[Codex consolidation](https://raw.githubusercontent.com/openai/codex/main/codex-rs/memories/write/templates/memories/consolidation.md)的density objective與What's in Memory。官方把詳情／provenance留在正文／詳記，導覽用高訊號路由、可直接搜尋的關鍵詞，避免重複。它允許重要直接連結；**不是官方禁止任何導覽引用**。
- 本案映射：保留正文完整引用鏈；導覽不再逐批追加所有詳記地址，改以主題、案例別名、正文可搜詞及何時讀取指引。只替換現有兩句導覽提示，不改Store、path、validator或工具schema。以真SDK接線RED→GREEN、同保存資料局部重播、讀取路由與正常訪談反例檢查。這是既有小型導覽設計的校準，不是建立新索引。
- 導覽候選重播medium與high均在14次仍因正文補丁錯誤中斷，不能宣稱提示或high解決了。下一局部對照只釐清既有`write_file`／patch選擇：短、全文可見、輸出可容納且跨多段時優先全文寫回；長或未讀完整仍patch。這是本案依實測作的工具路由取捨，**不是官方一律偏好覆寫**。[官方StateBackend.write](https://reference.langchain.com/python/deepagents/backends/state/StateBackend/write)允許完整寫入／覆写；[官方通用工具提示](https://reference.langchain.com/python/deepagents/middleware/filesystem/WRITE_FILE_TOOL_DESCRIPTION)允許新增／整份替換，另偏好編輯既有檔而非新增檔，並未規定本案這項細分選擇。未改任何工具底層、匹配規則、引用驗證或寫入權威。
- 最後短檔路由重播medium以5次完成。舊導覽仍保留引用清單，不能說已清乾淨；下一步從全新合成採購職位確認新導覽、案例區隔與自然收尾。先前帳本171+28次全部closed，再開最多50次／US$0.25反例帳本；合計請求護欄250次，總費用仍US$0.75，依closed預留計算不重複占用舊額度。沒有放寬任何產品限制。
