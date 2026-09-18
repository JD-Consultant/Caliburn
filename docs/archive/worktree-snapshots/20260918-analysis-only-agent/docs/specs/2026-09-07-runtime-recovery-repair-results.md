# Q019：Runtime recovery 局部修復結果

> `Q019-RUNTIME-RECOVERY-REPAIR-01` · 2026-09-07 · **四項局部 findings CLOSED；整體測試與獨立 review 通過。**
> Worktree `codex/analysis-only-agent`；程式範圍 `1d2be04c..fef3a22a`；本地保存 tag `q019-runtime-recovery-v1`。只分析的隔離底座，非 production。

## 1. 閱讀路由與不變的方向

- [本段計畫／官方接法核對](../plans/2026-09-07-runtime-recovery-repairs.md)
- [前輪整體審核與四項反例](../../../../docs/specs/2026-09-07-analysis-only-runtime-context-coherence-audit.md)
- [主 register](../../../../docs/current-decisions.md) 是目前狀態入口；不由舊 worktree register 猜施工授權。

保留 A 主顧問、B1 抽取、B2 整併、C 即時修補；原文、詳記／候選、正文、導覽及引用流程不換。仍是原生 reasoning/compaction 延續；Store／Checkpointer／發布 head/receipt 各守既有責任。未接 JD、UI、production；沒有新增 Memory manager、隱藏思考筆記或一般重試 Agent。

## 2. 四項修復狀態

| Finding | 預期修復 | 狀態 |
|---|---|---|
| ER-A01 | 已知唯讀工具失敗可沿原 checkpoint 恢復或安全收尾；未知寫入仍須對帳 | CLOSED／`15b87883`，獨立 review Approved |
| ER-B01 | 整併完成前的可修格式／引用錯誤回同一受限 Agent，不停死在外層 collect | CLOSED／`ff84d860`，獨立 review Approved |
| ER-B02 | 抽取修正能看到上一份候選及精確錯誤，checkpoint 保留有限額度 | CLOSED／`466b4f01`，獨立 review Approved |
| AC-01 | Runtime 標明初始導覽版本；僅本輪 C 結果刷新本輪視圖 | CLOSED／`fef3a22a`，獨立 review Approved |

## 3. 框架與應用各負責什麼

| 責任 | 使用方式與界線 |
|---|---|
| 接續執行 | LangGraph 公開 checkpoint／resume；不把所有 runtime error 一律重試 |
| 模型可修的失敗 | LangChain 公開 middleware 或 LangGraph state/edge，回饋後再由原模型處理 |
| 呼叫額度 | B2 沿既有 Model／ToolCallLimitMiddleware；B1 有限修正次數是本案接線，不宣稱官方預設 |
| 原生 JSON 輸出 | ChatOpenAI 原生 strict schema；Pydantic 檢查應用格式。兩者分開並不新增模型欄位 |
| 外部 HTTP 暫時失敗 | 仍由 OpenAI SDK retry，沒有外層通用模型重試相乘 |
| 寫入真相 | 仍由發布 validator／CAS／receipt 判斷；不讓模型猜是否成功 |

「統一」指各層責任與結果交接一致，不是每種錯誤都用同一個 catch／retry。保留既有版本：LangChain1.4.0、LangGraph1.2.11、langchain-openai1.6.0、Deep Agents0.7.13、OpenAI SDK3.8.0；未 patch 私有 framework converter。

參考 [OpenAI tool results](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)、[Anthropic tool errors](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error) 的失敗回饋原則；具體框架接線依 [LangGraph error responsibilities](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)、[Checkpointer 恢復與公開 StateSnapshot](https://docs.langchain.com/oss/python/langgraph/checkpointers)、[LangChain middleware hooks](https://docs.langchain.com/oss/python/langchain/middleware/custom) 與安裝版 API 核對。這是採公開成熟 primitive 的應用修復，**不是聲稱大廠每一項底層細節完全一樣**。

## 4. 驗證證據

### 主審整體驗證（程式 `fef3a22a`）

| 檢查 | 本次結果 |
|---|---|
| 全套 `uv run --no-sync pytest -q --tb=short -rs --basetemp <fresh scoped temp>/cases` | **427 passed／0 skipped，67.52s** |
| `uv run --no-sync python -m compileall -q src tests` | exit 0 |
| `uv lock --check --offline` | exit 0；既有83個鎖定套件，未升級或安裝 |
| `git diff --check` 與 `git diff --check 1d2be04c..fef3a22a` | exit 0 |

工作目錄 `experiments/analysis-agent`；`PYTHONUTF8=1`、三個 tracing 開關關閉、`LANGCHAIN_OPENAI_TCP_KEEPALIVE=0`。從既有專用容器取得測試連線設定但不輸出憑證，`Q019_TEST_DATABASE_URL` 指向 **127.0.0.1:55433／q019_agent_test**，connect timeout5秒；未連 production DB。包含現有真實 Postgres Saver／Store、連線重建及跨程序測試。新增各局部測試的 InMemory 重建不能因此冒稱每一種新故障都做了 PG crash 測試。

唯一 warning 是既有 Starlette TestClient 使用已棄用的 `anyio.abc.BlockingPortal` alias；非本次新增、未為消除警告改上游套件或遮蔽警告。Docker 沒有重啟、重建或清空資料；各 PG 測試只清理自己建立的隨機 test namespace／rows。主審全套數字不與以下局部／歷史測試相加。

### 逐項紅綠與邊界

- **Task4：**初始導覽 revision 與 guide 同時保存；重用既有 source_reference 限定 C 結果屬於哪個 input，不新增模型參數。RED4 failed→focused23 passed，另20項原生／唯讀恢復回歸通過。實際 root/direct Agent＋SDK：input1 C發布v2、輪間模擬B發布v3、input2讀v3；舊C回覆在canonical與wire逐字保留，單輪system prefix穩定、總共6次原情境呼叫。舊pending缺版本顯示unknown，不用新head假造舊guide版本。只證明上下文接線更明確，不保證自然模型必然遵守。
- **Task3：**原生三欄 schema 不變，候選先進 checkpoint，再驗應用文字格式；預設1次可配置修正，額度在模型呼叫前保存，重開或調高 constructor 也不補額度。正常仍每視窗1次；原生契約失敗／拒答／HTTP與應用格式錯誤分開。RED14 failed/1 passed含缺失API/state；原生三欄形狀的既有resume回歸另1 failed→修復；最終抽取／重抽相關 **63 passed，7.63s**。中間3→1失敗為fixture/native wire期待校正，不冒稱產品finding。舊partial checkpoint無額度metadata明確停住，不做遷移；新流程可恢復。
- **Task2：**B2 公開 after-model hook 對完整 no-tool output 做原暫存驗證，已知格式／引用錯誤帶檔案位置回同一 Agent；原 model/tool 上限與最終發布防線保留。RED5 failed→focused39 passed；相關回歸176 passed／1項舊預期失敗（原本要求 collect 直接拋錯），改驗既有額度耗盡及不發布後補驗1 passed。有限錯誤、HTTP中斷接續、C贏出後重新核對及receipt對帳均涵蓋；不加總作覆蓋率。新 hook 不支援／未驗證「升級前已停在外層 collect」的舊 checkpoint，自動遷移不在本段授權。
- **Task1：**四個正式 Memory reader × 原服務／重建服務，恢復、停止、abandon、call ID配對、既有通知不重播、每輪額度及未知工具負向回歸。有效 RED18 failed/2 passed→focused20 passed；補抓 `process_interrupted` 不能替未知工具認證副作用的負向 RED2 failed/2 passed，再修正。最終相關套件 **186 passed／1項既有Starlette warning，32.91s**；不重複加總 focused/baseline。獨立 review 無重要／次要finding。新測試是重建service並重用序列化InMemorySaver/Store與SQLite，非新PG crash實驗。
- 修改前基準：`uv run --no-sync pytest -q tests/test_service.py tests/test_extraction.py tests/test_consolidation.py tests/test_live_memory.py --tb=short` → **98 passed in 27.80s**。
- 初次 sandbox 執行有 pytest 暫存目錄 WinError5；一般本機權限重跑通過。沒有把環境限制當產品 bug，也沒有修改 fixture 去掩蓋問題。
- 施工前 B2 公開 middleware 探針：錯誤引用→完成→回饋→edit→完成；4 model steps／2 tool calls，有效引用發布。只證明公開接點可用，不是完整修復驗收。
- 施工前 B1 公開 dict schema 探針：同三欄 native schema、保留 raw response，第二次輸入有前次候選＋2000字行長錯誤，修正版通過。無新增 schema 欄位／工具。

本段付費模型呼叫 **0**；HTTP 為合成回應，framework／adapter／SDK 真實執行。不能以此證明自然模型的長訪談完整率、推理品質或實際 token 帳單。

## 5. Review、限制與下一個 gate

- **Review：**Task1–3 各有獨立 spec／quality Approved；最後 reviewer 先審 Task4，再同一次差異審查驗整批接線。確認可信讀取／未知寫入、私有 B 回饋／原文、原生配對／額度、B/C 發布及導覽時效；Critical／Important／Minor皆0。主審另看完整 task reports／程式差異並跑上述全套，沒有以 implementer 自評取代驗證。
- **升級邊界：**本段不遷移修復前的 B2 outer-collect 卡點；B1 舊 partial checkpoint 若缺額度 metadata 明確停止。沒有為了宣稱「全部修好」而清空舊實驗資料或強制重跑未知工作。AC-01 對舊 pending 則只標示版本 unknown，不假造新鮮度。
- **仍非整體產品 ready：**CT-01 完整 request 預算、SK-01 分析 Skills、grep 上限提示與無引用舊原文搜尋仍在後續 gate。沒有接 UI／JD／production，也未測自然模型的訪談分析品質。
- **下一個 gate：**先補完整 request 預算與分析 Skills 的設計／接線；一般原文搜尋與 grep 提示沿原待決邊界處理，其後才最小聊天室與核准成本的小額 Luna／medium 訪談。不要重做 Memory 全套研究。
- **重開條件：**新反例、官方公開契約變動或 Owner 改變效果要求；不是因再次讀到舊 audit 的 OPEN 或找到新名詞便重新討論。本段保留 worktree／本地 commits及tag，未 merge／push。
