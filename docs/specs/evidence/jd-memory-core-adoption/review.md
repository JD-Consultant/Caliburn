# Memory 核心採用：獨立審查

2026-09-13。結論：**PASS；未發現本切片新增且可重現的 P1／P2**。依[本輪設計](../../2026-09-13-jd-memory-core-adoption-slice.md)與[既有成果接點](../jd-consultant-source-integration/memory-seams.md)，核對新 package、來源 adapter、App 依賴，以及主代理新增的專用 PG 初始化／縱向測試。審查者未修改產品、契約、測試或環境，未執行 provider、PG、初始化、服務或新程序。

## 審查範圍與差異

直接以 Git 物件 `033540cef870d1f92baa5c69133a799231c46d48` 的 `experiments/analysis-agent/src/analysis_agent/` 三個原檔比較。排除 checkout 換行表示差異後：

| 核心 | 實際差異與核對結論 |
|---|---|
| [memory.py](../../../../packages/consultant-memory/src/caliburn_memory/memory.py) | 僅 package imports、來源型別及 `validate_source` 委派。既有 StoreBackend／CompositeBackend、固定 namespace、新 UUID artifact／版本、完整 bytes readback、跨文件檢查、長度規則與引用核對保留。 |
| [publication.py](../../../../packages/consultant-memory/src/caliburn_memory/publication.py) | 僅 imports 與來源驗證委派。原兩表、ORM `version_id_col` CAS、同交易 head／receipt、request digest、stale／uncertain 分支及 repair 不前進 `processed_source` 均未改。 |
| [references.py](../../../../packages/consultant-memory/src/caliburn_memory/references.py) | 正規化 checkout 換行後逐行相同，AST 相同。沿 CommonMark／LinkifyIt，不新增來源解碼器。 |
| [SourceReader](../../../../packages/consultant-memory/src/caliburn_memory/sources.py) | 只有文件身分、引用驗證與實際讀取三個接點；沒有另一份原話、來源表、provider 或舊 worktree import。 |

`MemoryArtifacts.validate_source` 在委派前核對同文件及 source 已提供。`save_extraction`／來源 header 讀回仍只驗來源位置，不把它們宣稱為原話內容的語意核實；knowledge／guide 中辨識出的 `conversation:` 引用，仍在保存及 `verify_version` 時實際呼叫來源 `read`。部分 artifact 寫失敗、虛假 ACK 或 prepare 後 bytes 改變不能成為 current。

`publish` 先做無 I/O 的輸入／來源位置檢查，進入 `_publish` 後先查原 receipt，才讀 artifact／原話。原結果不會因後來 head 改變而變成 stale，亦不會重新選回旧 head。這不等於跳過 request scope／digest 驗證，也不等於以缺少 receipt 宣稱操作失敗。

## 新來源接點

[ConversationSourceService](../../../../experiments/jd-relational-app/src/jd_relational/conversation_sources.py) 只在新發配值外加 `conversation:`；原 purpose、salt、dataset、固定 root／source checkpoint 及訊息範圍未改。完整引用與未壓縮 admission 都計入 prefix，不能靠壓縮短 token 繞過 4 KiB。舊裸 signed v1 仍原樣讀回；雙 prefix、錯 scheme、未簽舊四欄位址、篡改或錯 scope 不會成為相容入口。

[MemorySourceReader](../../../../experiments/jd-relational-app/src/jd_relational/memory_sources.py) 固定文件且不可改欄位，逐字委派同一來源 owner。`validate_reference` 不碰 Saver，只證簽章／形狀／scope；`read` 仍讀指定原始 checkpoint，缺失不能換成 latest。新 prefix 能被既有 CommonMark 引用核對發現，不需新來源 registry 或雙寫。當輪來源仍只涵蓋既定 Human 與前 AI 公開上下文，沒有被擴称全部未處理訪談。

## 依賴與測試

[App pyproject](../../../../experiments/jd-relational-app/pyproject.toml) 明確使用標準本地 editable package；獨立程序確認 `caliburn_memory.__file__` 位於 `S:/caliburn/packages/consultant-memory/src/caliburn_memory/__init__.py`，未靠研究 worktree 的 `PYTHONPATH` 載入。相對本輪前的 [uv.lock](../../../../experiments/jd-relational-app/uv.lock)，新增 16 個 package，既有 package 版本沒有升降或移除。DeepAgents 的 transitive provider dependencies 不代表本 package 會呼叫 provider；新核心源碼沒有 provider／HTTP／舊研究 service 接線。

審查者在 App 工作目錄沿已安裝環境執行：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -c pyproject.toml ../../packages/consultant-memory/tests tests/test_memory_sources.py tests/test_conversation_sources.py -q -p no:cacheprovider
```

結果 **98 PASS／8.17 秒，無 warning**：核心 44、新來源 adapter 10、既有固定原話 44。這是一次獨立窄組，不與作者的 [44 案](core-results.md)或 [71 案](source-results.md)相加。

首次合跑上述兩個 pytest project 時未指定 `-c`，pytest 選到 package 設定，App 的本地 `src` 路徑沒有載入，產生 **2 collection errors／8.00 秒**（`No module named 'jd_relational'`）。補上既有 App 設定後通過；沒有改產品、套件安裝、測試或新增研究路徑。這是審查命令的 config 選擇錯誤，不是產品反例。

## PG 證據的靜態核對與限制

額外唯讀核 [init_test_memory.py](../../../../experiments/jd-relational-app/scripts/init_test_memory.py) 與 [test_memory_core_postgres.py](../../../../experiments/jd-relational-app/tests/test_memory_core_postgres.py)：

- 初始化是獨立明示 script，只連固定 loopback 專用測試 DB，核名稱／使用者／PG 18.6／JD public 表集合，僅在 `jd_memory_core_test` 初始化兩張官方 Store 表及兩張原發布表。沒有 drop／資料刪除或一般 host open 的 setup；此 script 不是日常宿主 exact schema profile。
- PG 測試有明示 opt-in，不呼叫 setup。原生 Saver 保存合成原話，再經同 source owner、StoreBackend 與 publication 保存；晚期 repair 後 stale 背景不能覆蓋或前進 cursor。兩個來源／artifact 連線真的關閉後仍可查原 receipt；重開則另建連線、graph、source／artifact owner，確認固定原話、詳記及兩版 Memory，且不再次 invoke 合成顧問。
- 主代理回報該 PG 案 **1 PASS／7.81 秒**；審查者沒有重跑，不把它計入上述 98 案。測試是同程序新連線重開，沒有 provider、實際模型或新宿主程序的證據。

本 PASS 僅支持核心採用與來源接點。wheel／乾淨環境安裝由主代理另驗；正式產品切換、日常 Store 生命週期、明示初始化與備份 profile、全部 Memory 工作排空、B1 完整來源窗口、B2／C、模型工具及自然品質仍依原計畫接合，不能由本次結果推定完成。
