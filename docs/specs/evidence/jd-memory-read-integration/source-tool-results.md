# 詳記到固定原話的唯讀工具

2026-09-13；基準 `81a1ca76`。本頁為此接點作者的實作／測試證據，非獨立審查，也不代表自然模型或完整 Memory 執行已通過。

## 已接行為

新增 `experiments/jd-relational-app/src/jd_relational/memory_read_tools.py`，公開 `build_conversation_read_tool() -> BaseTool` 與純投影 `source_page(excerpt, offset=0)`。模型只填 `reference`、`offset`、`part=source|context`；文件、資料集、回合、固定 Memory view、Store 與停止狀態由既有 `memory_session(runtime)` 核對。

- summary 路徑先核固定 UUID 語法，再由 `MemoryArtifacts.source_window` 解析既有正式標頭。工具沒有重寫標頭 parser、建立新原話表或重算 checkpoint 定位。
- 同一 `MemorySourceReader` 委派唯一 `ConversationSourceService.read(reference, document_id)` 讀完整固定來源，再投影每頁最多 3,000 公開 Unicode 字元。保留 `message_id`、`role`、每段 `text_offset`、原始文字／換行；跨頁可串回逐字相同內容，不插入分隔符。
- `offset` 是同一來源訊息序列的字元位置，不是行號、byte 或另一個來源 reference。模型沿 App 回傳的 `next_offset`，不自行計算。來源服務本身仍只接受完整 reference，不假裝有 `read(reference, offset)`。
- 不重新簽发來源；`conversation:` 新引用及已保存裸 signed v1 原樣回傳。只投影 source owner 已確認的公開訊息，不回傳 thinking／tool／signature，也不假造舊來源的 `turns` 或省略類型欄位。
- summary 沒有另外保存 context 時，明確回 `context_available=false`、空 segments／next_offset；這不等於沒有較早訪談。直接來源 ref 不接受 `part=context`。
- 可修正的語法／reference／明確詳記缺失使用固定 `ToolException`。`source_not_available`、未知 Store I/O 或其他內部錯誤不吞成模型可重試結果；保留固定不可用錯誤供 App 停輪，沒有自動重試。

目前採用的核心尚無 typed artifact errors。本薄接點只對 `source_window` 已知的明確缺失／無效標頭錯誤做窄分類；其他 `ValueError` 也停止。已核 Deep Agents 0.7.13 `StoreBackend.download_files`：`store.get` 的 I/O 例外向外傳遞，只有找不到 item 時回 `file_not_found`。後續若核心錯誤契約調整，需要同步此有限適配，不以一般 `except ValueError` 吞掉來源故障。

## 官方依據與本案選擇

| 來源 | 事實及本案使用 |
|---|---|
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions) | 建議清楚描述工具／參數、使用 enum、讓 App 提供已知參數。本工具不要求模型填文件、run、Memory version 或權限欄位。已用官方文件工具搜尋後讀取原段落。 |
| [Claude define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools) | 官方要求說明何時使用、每個參數含義、輸出及限制；工具明示 summary/context、公開訊息和分頁範圍。這不證明兩家公司使用同一來源儲存方式。 |
| [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools#access-context) | 公開 `ToolRuntime` 由 ToolNode 注入且不進模型 schema；官方支援 Pydantic 或 JSON Schema 工具定義。本案沿 native JSON Schema 接點，仍使用同一 Pydantic 定義驗證模型引數。 |

適用鎖定穩定版：LangChain 1.4.0、langchain-core 1.6.3、LangGraph 1.2.11、Deep Agents 0.7.13、Pydantic 2.13.5，均沿現有 OSS MIT 套件；沒有安裝、升級或新增依賴。除了現行官網，亦核已裝 `langchain_core/tools/base.py::_parse_input`、`langgraph/prebuilt/tool_node.py::_get_all_injected_args` 與 `deepagents/backends/store.py::download_files`。

3,000 字元是延續既有已驗工具的本案輸出界線，不稱跨廠統一標準；沒有新的摘要、通用分頁服務或字素正規化。每頁可能切開一個組合字元序列，但各段未修改，完整串接保持原字元／換行。

## 首敗與實際結果

工作目錄 `experiments/jd-relational-app`，使用現有 frozen／offline App 環境與 `PYTHONUTF8=1`。

1. 先新增反例：`test_memory_read_tools.py` 因新模組尚未存在，**1 collection ERROR／6.82s**。
2. 首次實作原生接線：**13 PASS／10 FAIL／7.84s**。原生 ToolNode 先注入 runtime，嚴格 Pydantic args_schema 將其當額外欄位；另有測試試圖 patch InMemoryStore 唯讀實例方法。改用正式 JSON Schema 路徑、在 callable 內只驗證模型引數，並改測試 class 級故障注入。
3. 下一次 **16 PASS／7 FAIL／8.26s**，七例實際均正確拋出固定故障；pytest 9 將 LangGraph task note 納入 `match`，原測試 `$` 斷言誤判。改為核對例外 class 與 `.code`，不更改錯誤行為。
4. 當時新 25 案加原 source／Memory adapter 54 案：**79 PASS／9.06s**。
5. 自查追加 `/interviews/bad/summary.md`：**1 FAIL／25 deselected／7.74s**，核心 UUID 解析錯誤被誤映射成 Memory 不可用。補輸入邊界的固定 UUID 路徑檢查後，新檔最終 **26 PASS／7.05s**。此修正沒有改標頭解析或來源 owner；已過的原 source 54 案未再重跑。

所有 pass 命令均有不影響執行的 pytest cache 存取警告；未把警告寫成無警告通過。

最後兩組命令：

```powershell
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q tests/test_memory_read_tools.py tests/test_memory_sources.py tests/test_conversation_sources.py
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q tests/test_memory_read_tools.py
```

覆蓋字元分頁／CRLF／emoji／跨訊息串回、輸入與範圍錯誤、原生 ToolRuntime 隱藏欄位及 Store 注入、錯文件／thread／view／stop 拒絕、summary source/context、無 context、裸 signed v1、正文冒充 header、來源失敗與 Store I/O 不降級成模型重試。使用真原生 InMemorySaver、InMemoryStore、ToolNode、StateGraph；沒有 provider、真 PG、HTTP、OS 宿主、自然模型或背景 Memory C/B1B2 執行證据。本頁不冒稱完整顧問成功，也不冒稱工具已讀內容等於專業事實成立。
