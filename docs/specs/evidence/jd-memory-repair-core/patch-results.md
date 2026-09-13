# Memory C：官方 staged patch 採用與驗證

查閱日：2026-09-13；本輪基準 `7d3f474a`。範圍只含 `caliburn_memory.patch` 與 native staging 測試；不採用 OpenAI Runner、provider client、trace 或另一套 agent loop。

## 官方依據與版本決定

- 已先搜尋並讀取[OpenAI 官方 apply-patch 的 Agents SDK 段落](https://developers.openai.com/api/docs/guides/tools-apply-patch#use-the-apply-patch-tool-with-the-agents-sdk)。現行 Python 範例仍公開使用 `from agents import apply_diff`，文字轉換與真正文件操作由應用分開負責。本案將其用於原生 StateBackend 暫存文字，不宣稱已接 Responses 原生 `apply_patch` 工具。
- 採 **`openai-agents==0.22.0`**，不是為追版本重新選擇。[PyPI 的該版頁面](https://pypi.org/project/openai-agents/0.22.0/)列 2026-08-19 發布、MIT、Python >=3.10，查閱時仍提供下載；wheel SHA256 為 `985a74a8024123980c2d4dc329d19b2332a0f86919fa7b3f6b9c2abaae022680`，與舊 lock 相符。此結論不等於宣稱供應商承諾長期支援期。
- 原安裝 metadata 要求 `openai>=3.0.0,<4`，與新 App 3.13.0 相容；pydantic 2.13.5、requests 2.34.2、typing-extensions 4.16.0、websockets 16.1.1 均符合其範圍。沒有 LangGraph 版本依賴；LangGraph 1.2.11 與 Deep Agents 0.7.13 的 staging 相容性另以新環境實跑確認。
- 主代理修改 lock；本審核者只讀比較：新增 openai-agents 0.22.0、griffelib 2.3.0、mcp／mcp-types 2.2.0、opentelemetry-api 1.44.0、pyjwt 2.14.0、python-multipart 0.0.32、sse-starlette 3.4.11，共8包；現有套件沒有升降或移除。沒有為只取函式而複製官方 matcher。

## 採用邊界

來源為 analysis-only-agent `033540cef870d1f92baa5c69133a799231c46d48` 的 `analysis_agent/memory_patch.py`。移至套件後只增加來源 docstring；排除此 docstring 的 AST 完全相同。

- 原檔 SHA256：`b26e5be41214c79664a42e1995bf670406b6c4c8e4af9feefa455be2b534b6fd`。
- 採用檔 SHA256：`7ec27fc2b206d1d8f298f0c2abead1082c9eb33757abfb0a7f00c1d606d57dd8`。
- 保留 `apply_staged_patch(file_path, diff) -> bool`、`PATHS`、`MAX_PATCH_CHARACTERS=12000`、`PATCH_GUIDANCE`、`MemoryPatchError`。只允許既有 knowledge／guide 文件，必須在 graph staging context 執行；整個 SDK diff 成功後才 queue StateBackend 寫入。此層不發布 Memory、不碰原話或 JD。
- 沿[CT10 比較](../../../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-memory-editor-framework-comparison.md)與[其後採用結果](../../../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-official-memory-patch-trial-results.md)：官方 matcher 的 exact／空白 fallback、first-match、單一 advisory anchor 可未命中而繼續均保留。重複文字要用實際 context；不以標題或套用成功推定語意位置正確，不新增唯一匹配／fuzzy matcher。
- 實際不符的 context 或後面 hunk 失敗回 `MemoryPatchError`，不 queue 前面 hunk 的半成品。官方合法末尾標記保留；帶下一文件操作或尾隨內容的 envelope 拒絕，避免 SDK 停在 delimiter 後靜默略過。

## 實際驗證

實作前新 package 測試首敗：**1 collection error／8.41s**，`ModuleNotFoundError: caliburn_memory.patch`；原始輸出 `.research-tmp/jd-memory-patch-first.txt`。主代理完成 frozen sync 後，在新 App 鎖定環境取得 **22 PASS／17.39s**，輸出 `.research-tmp/jd-memory-patch-final.txt`；沒有使用舊 checkout 環境代跑。

22案涵蓋兩個指定文件、非法／空／過長 diff、尾隨操作拒絕、三種官方合法結尾、完整 context 分辨重複繁中案例、first-match／單一 anchor 的已知限制、缺 context、後段 hunk 失敗不 queue 半成品、後續 patch 讀最新暫存、no-op、倒序 hunk、缺檔／非 Memory 路徑拒絕，以及無 graph context 不得落到主機檔案。

安裝後再核 public export 及實際版本：openai-agents 0.22.0／openai 3.13.0／LangGraph 1.2.11／Deep Agents 0.7.13。`agents.apply_diff` 是原模組的公開函式，官方檔 SHA256 `d09b0c15365b389b58a3d71c4cadfb6719c76ee1f9d3fe253a6e51a743e31e1d`，與先前 CT10 使用的同版官方檔完全一致。測试期間没有另載私有 matcher 或自行改官方原碼。

重跑入口（工作目錄 `experiments/jd-relational-app`）：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest ../../packages/consultant-memory/tests/test_patch.py -q -p no:cacheprovider
```

本輪不執行 provider、SQL、服務或自然模型。純 staging 驗證只證明修補函式行為；C 的整批發布、回執／重開與 App 接線另由其責任測試驗收。
