# CT32：更正漏用工具的 Context 因素對照

- Topic：LLM-Q019／Q019-MEM-CADENCE-01／CT15-R07。
- 日期：2026-09-08；G5 已完成，帳本 closed；G8 OPEN，未接入產品修復。
- 唯一問題：先前可見回答與原生 compaction 延續，哪一種單獨保留時仍出現「回答已更正、Memory 未更正」？
- 範圍：Luna／medium，共最多20次模型請求、US$0.10；兩個隔離合成副本。Owner 本輪明確核准；不重跑長訪談、不改提示／工具／Memory 架構／產品設定。
- [執行清單](../plans/2026-09-08-ct32-context-isolation.md)。

## 已知事實與避免重複研究

[CT28](2026-09-08-ct28-live-repair-context-contrast.md) 中，短 context 7次模型／6工具成功寫回；原延續1次／0工具漏存。[CT31](2026-09-08-ct31-memory-routing-calibration.md) 的提示候選沒有改善並已還原。[CT30](2026-09-08-ct30-missed-memory-write-official-controls.md) 已比較工具描述、prompt 與完成檢查，不重新發明第四版同義提醒。

CT28 失敗 wire 中：系統導覽明示 Memory 仍為10日；prior visible tail 是員工重述5日＋AI表示以5日為準；另有一個舊 compaction block。這不證明哪一项造成失敗，故只隔離這兩項。歷史短 context 與完整 context 是參考控制，不是 CT32 同批重測。

## 官方來源與可支持的範圍

| 來源（本輪複核） | 真正支持什麼 | 不支持的推論 |
|---|---|---|
| [OpenAI Preserve reasoning across calls](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls) | 可見對話與推理延續不同；stateless replay 需保留相容項目及 phase，尤其同輪工具往返 | 不能由 opaque hash 看出模型思考，也不能據此宣布 compaction 有 bug |
| [Anthropic tool-use troubleshooting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use) | 未呼叫應檢查工具名稱、說明的使用時機、範例等 | 說明已送達不保證一定呼叫；既有提示已做過不能假稱新修復 |
| [Anthropic Memory prompting guidance](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance) | 官方 Memory 工具透過指示引導工作中讀取、記錄與維護記憶 | 不代表任意自訂 function 自帶這些內建提示或自動漏寫檢查 |
| [Anthropic prompting／tool usage](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#tool-usage) | 可明確引導採取工具行動而不只建議 | Claude 建議不能直接當成 Luna 已驗證修復 |
| [LangChain transient context](https://docs.langchain.com/oss/python/langchain/context-engineering) | `wrap_model_call`／`request.override(messages=...)` 可只改本次輸入，不改持久 state | 這是診斷接點，不是應刪歷史的產品建議 |

## 對照與限制

`visible_only` 保留舊可見問答，不送舊 compaction；`opaque_only` 原樣保留舊 compaction，不送其後舊可見問答。兩者都保留本輪員工訊息起的完整消息鏈，`all_turns` 設定、系統提示及工具定義不變。保存中的完整訪談不修改，不解密／改寫推理。

這是應用層選取輸入的局部診斷，不宣稱兩家具有相同內部成因。每組一次，只能縮小調查方向，不足以宣稱修復或成功率。不讓實驗隔離成為產品退化，也不自動加 Stop judge／強制工具。

## 結果

| 對照 | 舊可見尾段 | 舊 compaction | 模型／工具 | 持久結果 |
|---|---|---|---:|---|
| CT28 歷史短 context | 無 | 無 | 7／6 | 正文及導覽10→5日 |
| **CT32 visible_only** | 有 | 無 | **8／7** | **正文及導覽10→5日，revision 3→5** |
| **CT32 opaque_only** | 無 | 有 | **1／0** | **只在回答說5日，Memory 正文及導覽仍10日，revision 3** |
| CT28 歷史原延續 | 有 | 有 | 1／0 | 只回答5日，Memory 未更新 |

CT28 是前次歷史控制，非 CT32 同時重測。每組只有一次，不能計算一般成功率。CT32 共 **9次 Luna／medium、估 US$0.01421874**，全部 HTTP200／completed，未碰20次／US$0.10護欄；帳本已關閉，沒有追加生成。

### 模型真的做了什麼

- visible_only：`grep → grep → read_file → repair_memory（invalid_edit）→ read_file → repair_memory（applied正文）→ repair_memory（applied導覽）→ final`。第一個搜尋未命中是正文使用「每月 10 日前」而 query 無空白；擴大「月報」搜尋後找到。首 patch 抄舊段時多了不存在的句號，框架回傳精確錯誤；重讀後分別成功修補正文與導覽，因此 revision 增加兩次。沒有把修補重試從成本／工具統計移除。
- opaque_only：一次 final，沒有搜尋、讀取或修補；回答確實知道5日與其他既有工作細節，但持久 Memory 未改。因此不是「不會理解員工日期」，是未採取記憶行動。
- 舊編輯介面比較仍停放。首 patch 失敗已保留，不因聚焦零工具問題而宣稱工具格式無瑕疵，也不在本次自行更換。

### 核驗不是只看回答

[封存證據與可重現腳本](evidence/2026-09-08-ct32-context-factor-isolation.json)，SHA256：`4c5586e1552ebbdd0041be369b6c39e8e997b60f4ac9a1c640a4a7d73d5b21f9`。

1. 真實 wire 與 CT28 對比：visible_only 的可見訊息與原失敗組完全相同（只正規化 runtime 來源地址），差別為不帶舊 compaction；opaque_only 的 compaction hash 與原失敗組相同，可見部分僅系統＋本輪輸入。每次工具定義、CT25 提示、初始導覽及模型設定均核對。
2. 同輪新產生的不透明推理逐項原樣回送，沒有刪工具 call／result／phase；只選取舊 request view，未改 canonical。兩組都保存原42則＋新問答2則，重開服務核對相同。
3. 成功組正文只將「每月 10 日前」換成「每月 5 日前」、導覽只將「每月10日前」換成「每月5日前」；其餘全部字元／詳記引用完全相同。失敗組內容完全沒變。
4. 四份詳記的回查頁面及原始訊息片段與起始完全相同；兩次 applied receipt 的來源均能回查到這輪更正。背景狀態及已處理來源水位不變。重開驗證期間封鎖模型網路呼叫。
5. 77項局部離線測試通過（10.92s）＋ledger 邊界自測。測試前曾誤指不存在的測試檔，及受 Windows 暫存 ACL 阻擋；改用已確認的測試檔與隔離新暫存路徑、正常權限執行後通過。這些是測試啟動問題，不冒充產品失敗／通過。產品 `src/analysis_agent`／`tests` 相對 CT25 未變。
6. 封存後再跑完整離線回歸＋CT32選取測試：**548 passed／41 skipped，46.55s**。41項需專用 PostgreSQL 測試設定而略過；不能稱全套 PG 測試通過，本次真實副本的 PostgreSQL 保存已另依上述步驟核驗。僅既有 Starlette／AnyIO deprecation warning，未在此插入依賴升級。

## 結論與下一個 gate

**已縮小方向：這份舊壓縮延續保留時仍漏用工具，舊可見問答單獨保留時則能修補。** 不能說「所有 compaction 都會讓模型失敗」，也不能知道加密內容具體寫了什麼；模型隨機性、壓縮輸入及狀態延續仍待區分。不得將移除舊 compaction 當成產品修復，否則違反長訪談延續需求。

下一個唯一 gate：依既有 OpenAI／框架研究，核對**這份 compaction 的生成輸入與後續重新提供的目前 Memory／工具規則**，判斷是接線有可證實的缺口，還是完整接線下的過早完成。先做唯讀追溯，不再重複增加同義提示；若需改 context 組裝或採用 CT30 的完成檢查，再提出最小方案與成本供 Owner 審核。Stop judge／額外 Agent／強制 tool 均未因 CT32 自動獲准。

獨立唯讀審核完成，無 P0／P1／P2 阻擋項：核對11份腳本、24份產品原始碼雜湊、4項選取測試及封存結果，確認對照有效但僅限單次診斷。此結論可依新證據修訂，非不可翻案的架構決策。
