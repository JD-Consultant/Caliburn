# Q019 Memory artifacts 與漸進回查切片

> For agentic workers: 使用 executing-plans 的逐步執行／review checkpoint；本切片資料流緊密相依，主 agent inline 執行，最後獨立 code review。不要另啟一個全專案設計。
>
> 狀態：2026-09-06 隔離切片已驗證：32 passed／0 skipped；審核修復見結果稿。未授權 production／付費模型。

**Goal:** 保存詳記、候選、正文與導覽，以官方檔案工具逐層讀取，再沿 runtime 引用讀回真正問答。
**Architecture:** LangGraph Store＋Deep Agents StoreBackend 保存；create_agent 只註冊 FilesystemMiddleware 提供的唯讀 tools，不註冊其 hooks。原文由同一 graph.get_state 取得，不新增 transcript store。這段只產生不可變 artifact bundle 與固定 read view，**不實作／冒稱 current head 的 B/C 原子發布**。
**Tech Stack:** 現有 lock＋Deep Agents 0.7.13（2026-09-06 PyPI 最新 stable；相依核心版本維持原 pin）。
**Spec:** 主 checkout [Q019 Memory](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-design.md) §1、3、4、7；[整體](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-design.md)；[底層來源](S:/caliburn/docs/specs/2026-09-05-framework-conversation-source-and-summary-primitives-trace.md) §7；[官方檔案接點](S:/caliburn/docs/specs/2026-09-05-memory-artifact-native-backend-design-review.md)。執行副本也沿絕對路由讀新版，不依賴 worktree 的歷史 register。

## Preflight／界線

- Topic: LLM-Q019；G5 已有原生 continuation 與 PostgreSQL 雙程序證據，現在進下一個隔離切片。
- Binding: 一文件一訪談、一份隔離 Memory；原文不被摘要取代；model 不填版本／時間／namespace；read-only 模型不能直接改發布資料。
- 唯一問題: Store artifacts → 同一地址官方 reader → 指定 checkpoint 問答，接線是否完整可讀且隔離。
- 已讀: main register、decision-process、Q019 總覽／Memory／review、source trace、native backend review；只補 Deep Agents public API／實際安裝 source。
- 不做: B1/B2 模型與排程、C 修改、SQLAlchemy head/receipt、UI、Skill 內容、JD、embedding、付費 API、清空資料、merge/push。
- 工作位置: `S:/caliburn/.worktrees/analysis-only-agent`／`codex/analysis-only-agent`；reuse，非新 worktree。
- 原基線: 11 passed／1 skipped（未設定 DB 的離線重跑；不把 skip 當 DB pass），上一段真 DB 12 passed／0 skipped。

## Task 1：可沿引用深讀的 Memory artifact bundle

### 檔案與接口

都在 `experiments/analysis-agent/`：
- `src/analysis_agent/sources.py`: `ConversationReader(graph, document_id)`；`capture(start_id, end_id)` 從已完成 snapshot 產生可持久傳回的 ref；`read(reference, offset=0)` 輸出有界角色／文字區段與 next_offset。只讀，不 invoke。
- `src/analysis_agent/memory.py`: `MemoryArtifacts(store, document_id)`；`save_extraction(summary, candidates, slug, source_reference)` 產生 runtime 地址；`save_memory(knowledge, guide)` 產生新固定版本。沒有 set_current 方法；發布由下切片處理。
- `src/analysis_agent/memory_tools.py`: 固定文件／版本的 read-only backend、官方 FilesystemMiddleware、`read_conversation` Tool；工具不接收 document ID。
- `src/analysis_agent/runtime.py`: 在既有 factory 加可選 middleware 注入，保留原生 request-only compaction；沒有複製 loop。
- `tests/test_memory_read_path.py`: 真 StoreBackend／InMemoryStore 與 compiled agent 接線；只 mock 模型 HTTP。
- `tests/test_postgres_memory.py`: 真 PostgresStore＋PostgresSaver，關閉重開 connection／graph 後沿引用可讀；同專用 q019_agent_test，finally 只移除測試自身 namespace／thread。
- `pyproject.toml`／`uv.lock`：官方套件 pin；`README.md`：完成與未完邊界。
- 結果: `docs/specs/2026-09-06-analysis-only-agent-memory-read-path-results.md`；main register 只放狀態／連結。

### 已選公開 API 與精確責任

```python
StoreBackend(store=store, namespace=lambda _rt: fixed_namespace)
FilesystemMiddleware(
    backend=read_only_backend,
    tools=["ls", "grep", "read_file"],
    human_message_token_limit_before_evict=None,
    tool_token_limit_before_evict=4000,
)
snapshot = graph.get_state({"configurable": {
    "thread_id": document_id, "checkpoint_id": checkpoint_id,
}})
```

- 檔案工具只註冊讀取；backend 自身也不提供可修改路徑。官方 permission private 參數不用。僅取公開 `FilesystemMiddleware.tools` 的 BaseTool 實例交給 create_agent，**不註冊其 model/tool hooks**；保留原生檔案 formatter，不導入自動 eviction／multimodal scrub。
- 原生 reasoning／compaction blocks 須經完整 Agent HTTP 邊界回歸測試；此切片沒有額外聊天搬存。
- backend 沿用官方 offset/limit/ReadResult；模型可见大小由官方 read formatter 控制，超過約 16,000 字元時回傳精確續讀位置；artifact 入庫拒絕超過 2,000 字元單行，要求分行，**不截掉正文**。導覽上限 4,000 字元。原草案固定 4 行在短行情境增加無謂工具往返，實作審核改為官方大小分頁。這是可調工程上限，不是精確 token 計算／廠商共同最佳數值。grep 最多 4 個結果並保留官方 truncated；超過 100 個目錄項目回明確錯誤要求縮小目錄，不冒稱全部已列出。
- guide 完整載入固定版本；knowledge 與 guide 新版本使用不同 namespace。詳記是同文件的不可變地址。主模型從 guide 找正文，再按引用找詳記；raw candidates 不自動注入。
- 每次保存以新 runtime UUID 地址；成功完整讀回才回交接 refs。Store put 並非 CAS；此 API 不接受覆寫舊 bundle 的參數。失敗殘留未發布 artifact 的處置與 receipt 待發布切片，不宣稱 exactly-once。
- 來源 reference 含實際 checkpoint／message 範圍與文件 scope，標準 JSON 編碼後作不透明 reference；身份均由 runtime 取得。不是密碼學授權 token，runtime 固定文件隔離才是邊界。
- Reader 回傳已存 human／assistant 可見文字，保留角色，opaque reasoning／compaction／system instructions 不送回模型；清楚標示這是可見問答，非完整 provider item dump。B1 後續可重用 source loading，不是額外 reader 模型。
- 來源長訊息以字元窗口分頁，next_offset 由程式算，確保每頁前進；引用無效／異文件／來源不存在明確失敗，不 fallback 到 latest 或摘要。
- 只限文字訪談；遇未支援非文字內容不冒稱已讀所有原始內容。保留 canonical item，未增加附件處理產品能力。
- 審核補強：生成 artifact 在保存前正規化換行為 LF，避免官方 backend／formatter 行界線不一致導致漏續讀；canonical 原文不變。引用檢查掃描 runtime 發出的 ASCII /interviews/ 地址（含裸地址、reference-style、code），排除句尾句點後核對同文件存在性；不是逐句語意驗證或通用 Markdown parser。

### 步驟／測試

- [x] 寫第一個失敗測試：儲存包含中文案例、候選及引用的產物，新建 reader 可從 knowledge → summary → original 問答讀到獨特細節。
```python
# 真值來自手寫案例，不由受測程式自己產生 expected。
assert original["segments"][0]["role"] == "assistant"
assert "主管核准" in "".join(s["text"] for s in pages)
assert "opaque-secret" not in json.dumps(pages)
```
- [x] 執行 `.venv/Scripts/python.exe -m pytest tests/test_memory_read_path.py -q`；確認因新功能缺少而失敗，非 fixture/schema 錯誤。
- [x] 最小實作上述三個責任；不造搜尋引擎、不重存原文、不直接編輯 published namespace。使用官方 backend／middleware／tool。
- [x] 補契約測試：另一文件不能拿本文件 artifacts/ref；舊 ref 不漂移到新訊息；錯誤／不存在 snapshot；長中文分頁直到 EOF；未支援／隱藏 native blocks 不偽装成員工話。
- [x] 補真 compiled agent synthetic HTTP：導覽初始注入、按需 grep/read/source、工具結果可供下一 step；只讀工具 schema、無書寫工具、native reasoning/phase 仍保留；讀取不引入新摘要呼叫。
- [x] 補真 PostgreSQL 重新開 connection 測試：資料仍在，source ref 仍可讀，不碰其他 namespace。無 DSN 明確 skip；本輪收尾已實際連專用 test DB。
- [x] 全測、compileall、lock check；獨立 reviewer 核對 spec、隔離、read bounds、原文定位與官方接點，問題先重現再修正。
- [x] 寫 results、更新 README／main register，明示未實作 B/C／生成品質。收尾 diff check 及本地 commit/tag 的實際保存點以 main register 為準，不 merge/push。

## Self-review／停止線

本切片只覆蓋 Memory §1/3/4/7 的存取基礎；其餘 B1/B2、發布／協調、完整 Context 預算不能打勾。固定 read version 由呼叫者明確選取，不能先造第二個 current head。若官方 native middleware 破壞 opaque state，先查 producer/consumer 再處理，不寫 private patch。

## 來源與分類

- Official fact: [Deep Agents backends](https://docs.langchain.com/oss/python/deepagents/backends)、[FilesystemMiddleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in#file-system)、[官方 PyPI release](https://pypi.org/project/deepagents/0.7.13/)。
- Official fact: 上列已安裝 0.7.13 的 StoreBackend namespace/read/write、FilesystemMiddleware tools/offload/ReadResult 實作已逐段核對，與原 source 研究同 release。StoreBackend.write 可以覆寫，不宣稱天然 immutable。
- Mapping: 固定文件／bundle scope、reference 編碼、文字上限、read-only 接點，均為依官方 API 的應用接線；不宣稱 OpenAI／Anthropic 使用相同底層。
- OpenAI 五產物／引用流程不重研：沿用 Q019 Memory 指向的已讀研究。沒有新增產品語意。
