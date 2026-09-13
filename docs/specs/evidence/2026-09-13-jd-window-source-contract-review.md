# 完成訪談窗口 source port 契約審查

2026-09-13；JD-R002／OI-01、OI-02。受審提交 `ab483f6c`／tag `jd-window-source-contract-20260913`。本輪只審契約及其與 9/12、9/13 已定責任的接合；沒有實作、測試執行、provider 呼叫或資料表變更。

## 1. 結論

**方向正確，可以沿用作 H4 的施工起點；原稿有四個會讓實作者產生不同合法行為的契約缺口，已在[契約稿](../2026-09-13-jd-interview-window-source-contract.md)修正。**核心沒有偏離 9/12 關聯式 JD／保存責任，也沒有把 C 的當輪來源誤當成 B1 的完成窗口：原話仍由同一 native Saver 保存，`processed_source` 仍是 publication head 的唯一覆蓋權威，B1／B2 的 durable progress 仍由既有工作保存。

修正後才進入有限實作。W-01–W-14 仍是待建立的固定案例，不是已通過的產品證據。

## 2. 發現與修正

### F1／P2：觸發清單與實際連續處理範圍混在一起

- **問題：**原 `pending_windows` 只列有整理通知的回合，但 W-02 允許安全的第 3 輪「納入或停止」。這把通知誤當成可挑選主題，會讓同一份實作在不漏資料與漏掉資料兩種結果都被判定合法。
- **9/06 依據：**整理訊號決定「何時值得排程」，不是決定只處理哪個主題；B 必須沿未處理游標讀連續安全範圍，沒有訊號的相鄰安全回合也不能被跳過。
- **修正：**`pending_windows` 明確是觸發回合清單；dispatcher 另取 `unprocessed_source` 的連續安全範圍。W-02 固定為：第 3 輪安全就納入，未安全才止於第 2 輪。

同一界線也適用於未安全回合前的後續通知：在缺口閉合前不可把更後的通知先列為可 admission 目標。

### F2／P2：`window` 引用無法進入既有 B2 publication validation

- **問題：**9/12 保存契約的 `MemoryArtifacts.validate_source` 及 `PublicationStore._validate` 會驗證 `PublishRequest.processed_source`。目前 App 的 source reader 只接受 `purpose="source"`；若新窗口只發 `purpose="window"`，B2 的完成結果會在發布前被拒絕。
- **依據：**`packages/consultant-memory/src/caliburn_memory/sources.py` 的 `SourceReader` 是 source owner 的唯一驗證接點；`memory.py:139–142`、`publication.py:125–132` 對 extraction／publication 一律走它。9/12 明定 source_ref 由另一 owner 發配，不在 JD 或 Memory 內另建別名。
- **修正：**契約要求同一 source owner 提供用途感知 adapter／capability：允許 `window` ref 被驗證、讀取並保存為 `processed_source`，但 C repair 與當輪只讀工具仍限 `source`。不能複製 cursor、原話庫或用無簽章 parser 繞過驗證。

跨 root checkpoint 比較也必須證明 ancestor lineage；不能以相同 message ID 或 UUID 順序取代 lineage。

### F3／P2：只定 `read_window`，沒有定 B1 需要的 source/context pair

- **問題：**舊 B1 的 `extraction_windows` 回 `{source_reference, context_reference}`；`context_reference` 是消歧所需的前置問題及其間答覆。原稿說要沿用該語意，卻沒有規定新 port 回傳這一對，實作者可能只給一個範圍，造成 B1 失去已驗的上下文。
- **修正：**新增窗口規劃輸出契約。每個 planned window 必須回完整 `source_reference` 與 `context_reference|null`，兩者固定在發配時 root checkpoint；B1 直接使用這一對，B2 只接收保留這對 metadata 的 immutable extraction artifact；重抽只讀原 pair，不因預算或最新回合重新擴張。

### F4／P2：目的隔離與「同一簽章」文字矛盾；offset 單位未明

- **問題：**9/13 source integration slice 已要求同一持久 key／dataset 下獨立 purpose／salt；原稿「同一簽章」容易被實作成共用 salt。另，9/06 固定來源讀取以 Unicode 字元位置分頁，原稿沒有寫明，繁中／emoji 可能出現不同 offset。
- **修正：**契約改成共用 codec 類別、key、dataset 與演算法，但 `source`／`window` 使用獨立 salt／簽章 domain，purpose 不可互驗；明定 offset／`next_offset`／`text_offset` 是可見文字串接的 Unicode code-point（Python `len`）位置，不是 bytes、UTF-16、行號或 token，且分頁不插入分隔字元。
- **補充：**保留既有 B1 的 `max_chars=6000`、`context_chars=1500`、`max_windows=16` 語意；既有有限批次可只建立前綴，但必須保留未處理尾端並由下一批接續，不能截取前綴後假稱整批完成或丟掉尾端。

## 3. 核對過的既有邊界

1. **9/12 資料庫與保存：**JD 仍是十三表關聯式 current／revision／operation；source link 只保存 owner-issued opaque ref 與 basis digest，不存原話，不把 Memory 當永久來源。完成窗口的覆蓋位置仍寫 publication head 的 `processed_source`，沒有新增第二游標。
2. **9/12 LLM／App 契約：**模型只使用 App 發配的 opaque ref；身分、版本、關係、交易與錯誤由 App／domain 負責。source ref 不是可由模型拼出的行號或欄位值。
3. **9/12 自動保存與回復：**未知結果保留原 operation／receipt，不能重播；本次 source port 只讀固定位置，不改 JD、Memory 或原始對話的撤回界線。
4. **9/13 App source integration：**C 的 `purpose="source"` 當輪來源與 B1 完成窗口並存；原 C／只讀工具不改。用途隔離、固定 checkpoint、缺來源不 fallback latest 的要求保留。
5. **9/13 顧問接續：**採用的是已驗 B1／B2／A 方法的接點，不把後來的舊 JD editor 當已驗顧問；日常 AI 仍未啟用。

## 4. 官方與原始碼依據

查閱日期：2026-09-13。官方資料只用來核對責任原則，沒有把單一產品內部行為宣稱為本案規定。

| 來源 | 核對結果 | 本案界線 |
|---|---|---|
| [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) | checkpoint 保存 graph state／成功工作，支援中斷後續作及故障恢復；thread id 是持久狀態範圍。 | 支持沿既有 Saver／固定祖先鏈續作；不代表任意副作用自動冪等，仍須以 operation／receipt 對帳。 |
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) | 模型提出工具呼叫，應用程式執行並回傳工具結果；工具輸入與結果是應用邊界。 | 支持 App 持有引用、版本與執行結果；不規定本案 source token 或資料表。 |
| [Anthropic tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview) | 工具由 client／server 執行，模型使用回傳結果繼續；工具錯誤需由執行端回報。 | 支持由 App 執行 source read／B admission；不把 provider 的 tool schema 當資料保存模型。 |
| [AWS：Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | 重試要以同一請求意圖及可查回結果維持冪等，不可由不確定結果另發新意圖。 | 支持既有 B1／B2 同 operation reconcile；不推導出全域鎖、特定表數或每輪整理。 |

## 5. 後續有限施工與停止條件

下一工作單位只做：

1. 在 source owner 上實作用途感知的 validate／read adapter，先以跨 C source 與 B window 的 purpose、key、dataset、document 反例閉合。
2. 實作窗口 planner，產生 source/context pair，核安全終局、連續範圍、原話角色、Unicode offset 與固定 checkpoint。
3. 建立 W-01–W-14；補一個 B2 `processed_source=window` 的 publication validation 案例，證明這不是只在 source port 單元層通過。

缺鏈、超 256 祖先、未安全回合、publication cursor 無法讀取、用途／scope／位置不符都必須明示失敗。未完成上述案例前，不宣稱 H4、B1／B2 或自然訪談已接通；不新增資料表、不改 JD 格式、不重做 H2–H3、不啟動 provider。
