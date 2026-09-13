# 新原話 owner → Memory 來源埠驗收

2026-09-13；[本輪設計](../../2026-09-13-jd-memory-core-adoption-slice.md)的有限 App adapter。作者證據，不代替獨立審查或完整 Memory 接線。

## 實際修改

- `conversation_sources.py` 新發來源為 `conversation:` 加原有 ItsDangerous signed v1 token。同一 signer、salt、dataset、固定 root/source checkpoint 與原話範圍；未新增 token payload 格式或另一個來源 owner。`read`／`resolve` 仍接受原裸 signed v1，回讀保留呼叫者傳入的原字串，不重簽、不改寫既有操作依據。
- 新 prefix 納入 4 KiB **完整引用**與未壓縮 admission 上限；裸 signed v1 保留原上限。雙重 prefix、其他 scheme、舊未簽四欄 base64、錯文件及篡改均拒絕。
- 公開 `ConversationSourceService.validate_reference(reference, document_id) -> None` 只核原簽章、精確 payload 形狀及 scope，不讀 Saver，不宣稱 checkpoint 存在或文字支持某項知識。
- `MemorySourceReader(service, document_id)` 實作 `caliburn_memory.sources.SourceReader`，文件綁定不可變；`validate_reference(ref)` 與 `read(ref)` 直接委派同一 service，後者回原 `SourceExcerpt`。不另保存資料、不新增排程或工具。
- 既有 source 測試只有三处私有 payload 檢查明確移除新增 prefix 後交原 signer；沒有放寬原 shape／scope／range 反例。

## 首敗與最後結果

新 App 既有鎖定環境已由主代理安裝 proper `caliburn-memory` 套件；未藉研究目錄的 `PYTHONPATH` 使 import 通過。

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q tests/test_memory_sources.py
```

先新增反例、尚無 adapter 模組時：**1 collection error／7.82s**，`ModuleNotFoundError: jd_relational.memory_sources`；另有兩個 pytest cache 目錄 ACL 警告。

完成接點後：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q tests/test_memory_sources.py tests/test_conversation_sources.py tests/test_consultant_context.py
```

**71 PASS／7.87s**：新來源埠 10、既有固定原話 44、context 17；一個 pytest cache ACL 警告，未影響測試結果。這是一次窄組實跑，沒有累加先前輪次測數。

新增反例核對：

1. 原生 InMemorySaver 的已保存 Human／前 AI 来源，確實被核心 CommonMark `controlled_references` 發現；同原生 InMemoryStore／StoreBackend 保存 knowledge、guide 與 extraction metadata，再讀出同 ref。
2. 既有裸 signed v1 可讀／resolve，原字串及公開內容保持；新 prefix 不是舊未簽來源的接納入口。
3. 令 graph `get_state` 與 service `read` 一律失敗，形狀驗證仍不讀它們；已簽但缺失位置的 locator 可通過形狀驗證，實際可讀性明確留給 `read`。
4. 同 owner 但錯文件、篡改、錯 scheme、雙 prefix、過長引用，在任何 native read 前拒絕；reader 不可切換文件。
5. 高壓縮率 payload 的原裸 raw admission 剛好在舊限額內，增加 prefix 後超限則拒絕；不能用壓縮後短 token 繞過完整上限。

## 範圍限制

本次使用真原生 in-memory Saver／StoreBackend，無 PostgreSQL、HTTP、新宿主程序、provider 或付費呼叫；未執行 B1／B2／C。Memory package build、真 DB 及發布縱向情境由主代理負責。當輪來源仍只覆蓋已定範圍，不宣稱涵蓋全部待整理訪談；宿主資源、Store 初始化、模型工具與完整 Memory 生命週期仍沿主計畫接合。
