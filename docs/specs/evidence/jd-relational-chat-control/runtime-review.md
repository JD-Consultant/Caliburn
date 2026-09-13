# 聊天控制：AI coordinator 獨立窄審

日期：2026-09-13；基準 `36cc1cb9`。唯讀檢查本輪 `ai_runtime.py`、`test_ai_chat_control.py`、`test_ai_runtime.py`、`test_ai_restart.py` 改動及 [shared-tool-research-review.md](shared-tool-research-review.md)。只新增本文件，不改實作／測試；審查者自己編寫的 owner 不列獨立證據。

**結論：PASS；AC-R01（P2）已重現、主代理修正並經獨立窄複核關閉，指定範圍沒有剩餘阻擋項。** 首次檢查時 `ai_history.py` 尚未交付，這是已知並行依賴，不列成產品 bug；其落檔後已跑本次 23 項 coordinator／restart 測試及真 native history 的原反例窄複核，不擴稱整個 history 模組已由本審查全面驗收。

## 1. AC-R01：本輪無 binding 的成功工具結果可被誤當可信 terminal

修正前根因位置：[ai_runtime.py](../../../../experiments/jd-relational-app/src/jd_relational/ai_runtime.py) 的 `_verify_saved_results`（本輪修正前約 146–168 行）在 `binding is None` 時直接略過；新增 `_lookup`（修正前約 310–328 行）驗 terminal 時依賴此檢查。`_binding_receipts` 只會查本輪已保存 bindings，所以空 bindings 配上當輪宣稱 committed 的 ToolMessage 會產生 0 次原 SQL receipt 查回，仍可返回 completed。

### 已重現反例及必要正例

兩次獨立 Python probe 皆使用真正 `InMemorySaver`／`build_document_graph`／`AiRunCheckpoints.observe`，只透過合成 node 準備保存資料，沒有執行 provider。由現有 `_receipt_fixture` 產生配對的 JD mutation call 與合法結果形狀；沒有真 SQL 寫入。為隔離當時尚未交付的 history import，probe 在自己的 Python 程序注入一個明示空模組，並讓 `run_history.find` 回傳已由原生 checkpoint adapter 核過的 observation。**這只測 coordinator 的材料驗證，不冒稱真 history locator 已驗收。**

| 情境 | 實際輸出 | 應有結果 |
|---|---|---|
| 本輪 Human＋本輪 `jd_set_text` call＋committed／success ToolMessage；`jd_ai_bindings=[]` | native closed=True；`_lookup().wait(0)` 回 completed／input_saved=True；SQL receipt lookup=0 | 拒絕本輪缺少 binding 卻宣稱已保存的結果，不能發布可信 terminal。 |
| 前輪 Human＋已配對成功 mutation，再接本輪 Human＋公開 AI 回覆；本輪 bindings=[] | completed／new-public-reply，原前三則完整保留；SQL receipt lookup=0 | 必須保留。本輪 bindings 不能用來否定前輪已完成結果。 |

最小修正要帶 exact `run_id`，先定位本輪真正 HumanMessage，再只核本輪工具結果。已知 mutation 沒有 binding 時，只能接受現有 `validate_result` 通過的 unbound error：未綁 operation、effect unchanged、receipt unconfirmed，且原 call／name／ToolMessage error status 對得上；不能接受無原操作的 committed／no_change 或 bound 結果。read／change-read 的正常無 binding 結果沿原讀取契約。不要掃全部歷史，將前輪的合法成功當成本輪缺 binding。

這是新公開 terminal 查回需要補齊的保存材料完整性邊界；不是指正常工具目前會漏存 binding，也不表示原 SQL 已保存內容應回滾。

**窄複核：CLOSED。** 主代理已讓三個 production 呼叫位置（startup terminal、lookup terminal、settle）明傳 `run_id`；helper 核唯一當輪 Human 且其後無另一 Human，再限制當輪無 binding 的非讀工具只能回合法未執行錯誤。新增反例拒假成功，對照保留前輪成功及本輪合法 unbound error。依賴落檔後，獨立重跑原本的本輪假成功 native fixture，改用真正 `AiRunHistory(AiRunCheckpoints(graph))`，實得 `invalid_saved_tool_result`，0 SQL 查回，沒有公開假 terminal。這次沒有 history import 替身。

## 2. 其他接點核對

| 接點 | 核對結果與限制 |
|---|---|
| 新原請求與 base | `start` 只收 UUID expected revision，建立新版原 record；原字串 Human 與 canonical start revision 進原意圖 digest。不能用現在 head 替舊請求補版次。record codec／V2 由並行作者負責，不以此列為完整 schema 獨立審查。 |
| cached／歷史原結果優先 | `_start` 的 callback 先 `_lookup`，比較原 format／digest，再由同 owner 新准入比 head。cached live handle 也經相同 callback；同 key 改原話或 canonical base 拒絕。歷史尚未查明不能轉成 None 開新回合，具體完整性依新 `AiRunHistory.find` 接合驗證。 |
| 查詢與資源關閉 | public `lookup` 走 owner 的唯讀範圍再查 cached／native；沒有 GET 包裝 start／recover。cached 結果不是繞過已關資源的入口。此處只核 coordinator 呼叫位置，不把自己 owner 實作當獨立證據。 |
| V1 查回 | `test_ai_restart` 刻意建真正 V1 digest／record；查原回合改用 lookup，不補 start revision。新 V2 start 遇 V1 走 original-run-lookup-required，不能僅因有舊 handle 而略過版本核對。 |
| terminal 與 SQL | 非 cached 歷史分支先查 bindings 的原 receipt，要求 confirmed、原 tool 呼叫／結果相符、原生 closed 且無待配對呼叫；此結構正確。AC-R01 補的是無 binding 的當輪 mutation 成功漏檢。cached terminal 代表本宿主先前已確認結果，不能將它描述成每次 GET 都重新查全部 SQL。 |
| preinput 與 head 再核 | 真 `_run` 在 invoke 前再核 current 與 notice head 的 canonical identity；未進 graph 前的拒絕不能說 Human 已存。既有 `_confirm_input_not_saved` 保留真 Future／無 tool entry，以及 invoked 後 exact before／after idle root 的要求；未看到把單一 not_found 或 timeout 當未保存證據的新改動。 |

新 `test_ai_chat_control` 最初五個案例涵蓋 stale 新請求零 input／model、原請求優先與 base conflict、跨較晚回合查回、live lookup、真正 `_run` 的 head 前置拒絕，後續補錯誤輸入、已關 owner 不回 cached start／lookup 及 AC-R01。測試多數沿 `SyntheticRuntime`，head 再核案例才直接呼叫真 `_run`；不能把全部固定 node 測試稱為已跑真 provider／完整 HTTP。

## 3. 分享研究文件與官方抽查

[分享核對文件](shared-tool-research-review.md)明列十五節分享為二手分析，未取得的二十二章／三十三來源／五十八檢查不當成本案實證；沒有把未驗 MCP／PTC／async 能力或作者建議改成產品決策。AI 直寫 JD、Memory 獨立、未知不補造及自然模型仍待驗收的界線保留，沒有不實「大廠共識」或全面採用的宣稱。

本審查未重新讀分享全文；依授權只抽查兩個會影響採用解讀的官方來源，均於 2026-09-13 開啟正文：

- [OpenAI Define tools](https://developers.openai.com/plugins/plan/tools)確為 ChatGPT／Codex 的 plugin MCP 工具規劃，支持按使用目標組合相關操作及依風險／權限拆分；不指定本案十工具、資料表或模型版本。使用 OpenAI Docs 官方搜尋後讀正文，沒有僅依搜尋摘要判斷。
- [Anthropic Strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)的 weather 範例確有 `unit` property 未列 required；因此文件指出兩家 schema 規則不能直接互抄有具體依據。沒有由此推定 strict 可取代本案 scope／業務／原 receipt 驗證。

這是窄來源核對，不是另一份完整工具研究；未調模型、套件、欄位、來源權威或費用範圍。

## 4. 實測狀態

先執行上述兩個有界原生 checkpoint material probe：當輪假成功 **重現缺口**、前輪成功保留 **對照通過**。修正及依賴就緒後，獨立執行：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_ai_chat_control.py tests/test_ai_restart.py -q -p no:cacheprovider
```

結果 **23 PASS，1.03 秒**；另以真正 `AiRunHistory` 對原 native 假成功資料窄複核，正確拒絕。三個 probe 與這 23 項分開列示，不與主代理的 48 項／真 PG 4 項累加。全部獨立實跑 0 DB／provider／HTTP／OS；本審查未重跑真 PG，也未自行修改產品程式或測試。
