# Q019 第三切片：Memory 保存與按需回查結果

> 2026-09-06 · 隔離實作；**32 tests passed／0 skipped；獨立 review 的 R1／R2 修復後複核關閉，無剩餘阻塞 finding**。
> Topic LLM-Q019；[計畫](../plans/2026-09-06-analysis-only-agent-memory-read-path-slice.md)；[有效設計](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-design.md)；[決策入口](S:/caliburn/docs/current-decisions.md)。
> 不接 production、不做 JD、不呼叫付費 API。此文件不宣稱已完成背景生成／修補或模型品質。

## 1. 本段到底完成什麼

`experiments/analysis-agent` 仍在 `codex/analysis-only-agent` 的隔離 worktree：

| 已實作 | 實際接法／界線 |
|---|---|
| 詳記＋候選保存 | StoreBackend 官方 write/download；Runtime 建地址、清理 slug，header 加入真實來源 reference。模型本段用手寫 fixtures，尚未接 B1 |
| 正文＋小導覽固定版本 | 新 namespace 保存，不接收覆寫舊版本的 ID；回傳 prepared version。**不是 current-head 發布** |
| 漸進查找 | 公開 FilesystemMiddleware.tools 的 ls／grep／read_file，交給官方 create_agent；小導覽固定一次讀取，模型按需深查 |
| 原始問答回查 | 精確 graph.get_state checkpoint＋訊息範圍；不讀 latest 冒充、不 invoke/replay、不新建原文副本 |
| 長中文續讀 | 原文每頁最多 3,000 字元；文件工具使用原生大小分頁及續讀提示。完整內容保存不被截斷 |
| 同文件隔離／唯讀 | runtime document namespace 與 ref scope；讀取 backend 核對執行 thread。無 write/edit/delete/execute 工具，backend 也沒有寫入實作 |
| 原生延續相容 | Memory Tools 循環後的 reasoning、compaction、phase 仍由原接法延續；canonical 原文仍可回讀 |

本段的訪談詳記／正文內容是測試輸入，不是已驗證模型自然產出。Memory 本身不代替模型分析／决定動作。

## 2. 官方元件與我們接的部分

**Official fact：**[Deep Agents backends](https://docs.langchain.com/oss/python/deepagents/backends) 提供 namespace、StoreBackend、read/grep/ls 與公開 backend 擴充；[官方 middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in#file-system) 提供 BaseTool 清單。實際核對安裝版 **0.7.13** 的 constructor、read/write、FileData、工具格式化／續讀、offload hooks；[PyPI 同版](https://pypi.org/project/deepagents/0.7.13/)。不能只從名稱猜 immutable／source lookup 已內建。

本段只拿公開 `.tools` 实例，不註冊整個 FilesystemMiddleware hooks：
- 保留官方檔案格式化與按大小續讀。
- 不附帶聊天／Tool output 搬存、一般 multimodal scrub；原生 Responses items 不經另一層通用整理。
- 不調用 private formatter／permissions；不自製 search／filesystem engine。
- Deep Agents 安裝依賴包含 Anthropic／Google adapters，但本段沒有使用或呼叫它們。實際模型路線仍是先前 OpenAI Responses 接線。

**Caliburn mapping：**artifact 地址／header、來源 reference 編碼、固定 read view、query/頁面界線及唯讀配置。這些為滿足已核准用途而接官方 API，不宣稱 OpenAI 或各家採同一 schema。原 OpenAI 五產物與引用理由沿用 Q019 指路的研究，不重新發明一套記憶流程。

## 3. 這次確實發現／修正的接點

| 接點 | 處理 |
|---|---|
| StoreBackend.write 可覆寫 | 程式只生成新 UUID namespace／artifact path；沒有 A 可用的 writer。真正 B/C 發布／receipt 留給下一切片 |
| 固定只讀 4 行雖有界但增加往返 | 改重用官方工具約 16,000 字元輸出預算，短行可一起讀；工具返回正確續讀位置。不宣稱這是實際 token 精算 |
| 超長單行可能讓官方工具無法完整前進 | 保存時拒絕超過 2,000 字元單行，要求分行，不靜默刪字；可調工程限制，不是語意格式需求 |
| R1：特殊換行讓 backend／formatter 行數不同，可能漏掉尾端 | 先重現 U+2028／NEL 分頁失敗，再於生成 artifact 保存前把換行正規化為 LF；canonical 問答不變。官方工具四種換行測試均逐行讀到 EOF |
| R2：只驗 Markdown inline 引用會漏掉裸地址等形式 | 改核對所有 literal runtime /interviews/ 地址，包含 bare／reference-style／code。補句尾 .／...／。合法引用正向測試，避免吞入標點誤拒。仍拒絕不存在的地址 |
| 只在 model hook 核對文件不足以保護 tool resume | backend 每次讀取也核對 graph scope；跨文件節點讀取測試由失敗變通過 |
| 大目錄可能塞滿 context | 超過 100 筆明示縮小範圍，不截完冒稱全量；grep 最多 4 命中且保留官方 truncated。完整正文盤點用固定版本分頁，不靠 grep |
| 原始 history 有不透明／非文字 items | 原文 Tool 明示是保存的可見問答；返回省略的類型名稱，不顯示／解碼 private reasoning，亦不將它當員工原話 |
| 未完成 checkpoint／錯 reference | 抽取 source capture 拒絕未完成視窗；找不到確切 checkpoint／訊息即失敗，不退回最新訊息 |

僅 keyword search，沒有額外 embedding／向量索引。找不到不是「沒有此工作」。完整盤點目前針對固定版本的整份正文，不表示所有歷史詳記都已被模型整理。

## 4. 實際測試，不混稱效果

- 初始紅燈：4 cases 因 source reader 尚未實作而失敗；新增隔離測試捕獲未檢查工具 scope 的路徑；修復後通過。
- `tests/test_memory_read_path.py`：**19 passed**。覆蓋 12,500+ 中文／emoji 字元原文續讀、137 行正文列舉、41 長行經真 ToolNode 的官方截斷／續讀（LF／CRLF／U+2028／NEL）、不同引用形式與句尾標點、不串文件、舊引用不漂移、缺來源、未完成來源、只讀、真 compiled Agent 漸進工具路由與原生 compaction。
- `tests/test_postgres_memory.py`：**1 passed**。真 PostgresStore＋PostgresSaver；關閉全部 client 再建立 connection／graph，正文／詳記／原始問答仍可回讀。不是程序 kill 或資料庫 failover 證據。
- 最終全套：`python -m pytest -q -rs` → **32 passed in 9.84s，0 skipped**，包含先前雙 Python 程序恢復測試。無 DSN 時兩項 PG tests 會明確 skip，不能寫成 durable pass。
- `compileall`、`uv lock --check --offline` 通過。套件解析 71 packages；原核心 pins 不變。
- 模型 HTTP 皆 synthetic；不讀產品 `.env`、無有效 key、tracing 關閉，**付費模型呼叫 0**。
- 獨立 reviewer：首次提出 R1／R2，先新增測試重現 5 failed／2 passed；修復後又提出句尾標點誤拒，新增正向案例重現 2 failed／1 passed 後修復。最終 reviewer 獨立驗證引用相關 7 passed／12 deselected，回覆 R1／R2 均關閉、無本範圍剩餘阻塞問題。review 是本切片邊界審核，不是模型品質評分。

PG 只用既有專用 `caliburn-q019-postgres`／`q019_agent_test`／localhost:55433。新測試會初始化官方 Store schema，finally 只刪本次随机 `q019-test-*` thread 及其 `q019-memory/{document}` namespace items；不清空整庫、不碰既有產品資料。這些被刪的是本次手寫測試案例，可由測試重建。

## 5. 限制與下一段，避免把元件齊全當完成

1. **尚無 B1/B2 模型與背景生命週期**；沒有自動抽取、去重品質或 live repair 效果證據。
2. **尚無 current head／receipt／B/C CAS**；現在由可信呼叫者選 prepared version，並建立同版本 guide＋reader。不能讓此處的寫入接口被當發布接口。部分保存失敗可能留下尚未交接 artifact；後段 publication seam 才管協調／恢復。
3. 固定 read view 建立後不自動切版本；下一個 run 要由呼叫者建立新 view。C 的受控刷新留在後段。
4. 本段工具回傳有界，Store grep／get_state 底層仍可能讀整個 namespace／snapshot；沒有宣稱大型訪談 DB 成本固定。
5. 文字訪談；非文字／tool native blocks canonical 保留，但 raw Tool 不是 provider JSON dump。B1 要用的可見工具資訊仍依設計另選，不將 opaque reasoning 交給背景。
6. 引用檢查覆蓋存入內容的 literal ASCII runtime `/interviews/` 地址存在性（不限定 Markdown 展示形式），以及來源引用格式與 scope；不是通用 Markdown parser、自然語言所有提及的語意正確性，也不是已完成 B2 全部輸出驗證。
7. 沒有 UI、JD、Skills／run token 預算／付費 Luna 測試；不 merge、不 push。

**Next gate：**依 Q019 Memory §6 接 prepared artifacts 的原子發布／版本衝突與 receipt，再接 B1/B2 抽取／整併及 C。不再重開已驗證原文保存者／檔案 reader 名詞研究；遇到實際反證才調整。
