# Memory 核心採用：實作與離線驗收

日期：2026-09-13。依[本次設計](../../2026-09-13-jd-memory-core-adoption-slice.md)，採用既有 checkout `033540cef870d1f92baa5c69133a799231c46d48` 的三個核心。結果 **44 PASS／6.86 秒**；真 DeepAgents StoreBackend／LangGraph InMemoryStore、原生圖作用域與 SQLite 發布交易。沒有 provider、PG、服務或新程序驗收。

## 實際採用差異

| 檔案 | 保留與調整 |
|---|---|
| [memory.py](../../../../packages/consultant-memory/src/caliburn_memory/memory.py) | 保留 StoreBackend／CompositeBackend、原 namespace、artifact 準備與完整 readback、版本隔離、原話 metadata、既有長度及引用檢查。僅改 package imports、来源型別與驗證委派。 |
| [publication.py](../../../../packages/consultant-memory/src/caliburn_memory/publication.py) | 保留原兩張表、ORM version CAS、同交易 head／receipt、stale／提交不明與原操作查回順序。僅改 imports，來源驗證改呼叫 `artifacts.validate_source`。 |
| [references.py](../../../../packages/consultant-memory/src/caliburn_memory/references.py) | 與原始檔內容相同；沿 CommonMark／LinkifyIt，辨識 `/interviews/` 及 `conversation:`，不解碼來源位址。 |
| [sources.py](../../../../packages/consultant-memory/src/caliburn_memory/sources.py) | 新小型 SourceReader Protocol，只有 document_id、validate_reference、read；沒有原話存取實作、資料表或舊四欄 source decoder。 |
| [套件出口](../../../../packages/consultant-memory/src/caliburn_memory/__init__.py) | 匯出 artifacts、version、publication 型別與來源埠，不匯入舊研究 package。 |

`validate_source` 要求提供 source 且同文件，再由來源 owner 驗形狀／scope；此步不做 I/O。正文 `conversation:` 引用仍實際 `read` 驗可讀。原 publication receipt 在 artifact verify／來源 I/O 之前查回，不因來源暫不可讀而重發布或倒退 current head。原無來源的 Memory 仍可使用；含來源位址時不得省略驗證。

## 測試範圍

- [test_memory.py](../../../../packages/consultant-memory/tests/test_memory.py)：真 backend 的固定版次、跨文件隔離、繁中分頁、空 view、來源形狀與真正回讀的區別、原話不被 artifact 換行正規化、不可讀／錯 scope 引用、部分 artifact 寫失敗、虛假寫入 ACK、原生圖的文件作用域，以及模型正文不能偽造 runtime source header。
- [test_publication.py](../../../../packages/consultant-memory/tests/test_publication.py)：保留原 publication 十個測試函式及參數化情境，僅替換 imports／source fixture；另補原回執優先於來源 I/O 與來源 shape/scope 不 I/O。涵蓋 stale 不覆蓋修補、修補不推進背景游標、同 key 不同意圖、遺失／被改 artifact、提交前回滾、COMMIT ACK 遺失與查回連線故障。
- [test_references.py](../../../../packages/consultant-memory/tests/test_references.py)：opaque 來源在 Markdown／裸文字／程式碼中的辨識、重複 reference definition、外部 URL 排除與不擅修字串。
- [conftest.py](../../../../packages/consultant-memory/tests/conftest.py)：只模擬 SourceReader；Memory 用真 StoreBackend／InMemoryStore，publication 用 SQLite。沒有舊 provider／conversation／service fixture。

## 首敗與最後結果

1. 套件尚未建立／安裝前：[首敗](../../../../.research-tmp/jd-memory-core-first.txt)為 **2 collection errors／1.20 秒**，`caliburn_memory` 不存在。
2. 主代理完成正式 editable 依賴安裝後：[首次新環境](../../../../.research-tmp/jd-memory-core-installed-first.txt)為 **41 PASS／3 FAIL／12.15 秒**。兩案 fault fixture 嘗試改 InMemoryStore 的唯讀 instance method；另一案 fixture 把「導覽」直接黏到裸來源 token 後，被既有嚴格引用檢查正確拒絕。另有兩個 pytest cache 權限 warning。
3. 只修 fixture：故障注入改 class method、引用改成明確 Markdown 連結；命令加 `-p no:cacheprovider`。沒有放寬來源解析或修改 backend。最終[原始輸出](../../../../.research-tmp/jd-memory-core-final.txt)為 **44 PASS／6.86 秒，無 warning**。
4. [實際環境](../../../../.research-tmp/jd-memory-core-environment.json)確認從新 `packages/consultant-memory` 載入，不使用舊 worktree venv 或研究 PYTHONPATH；DeepAgents 0.7.13、LangGraph 1.2.11、LangChain 1.4.0、core 1.6.3、SQLAlchemy 2.0.52、markdown-it-py 4.2.0、linkify-it-py 2.2.0。

工作目錄 `experiments/jd-relational-app`，沿正式本地 package 依賴與 lock：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest ../../packages/consultant-memory/tests -q -p no:cacheprovider
```

## 限制

SQLite 不證明 PG 競爭／故障；SourceReader double 不證明新 App 的原話 adapter。本報告不包含 package wheel build、App 接合與獨立審查結果，由主代理分別核實。未採 B1/B2/C、模型工具、排程器、宿主 Store 生命週期或完整 Memory 功能，沒有新增 current authority 或第二份原話。正式產品未切換。
