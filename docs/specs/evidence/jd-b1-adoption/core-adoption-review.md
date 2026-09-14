# B1 核心採用 353c400b：審查與下一片接線界線

2026-09-14；JD-R002／OI-01、OI-02。受審提交 `353c400b`／tag `jd-b1-core-adoption-20260913`。對照 9/12 關聯式保存／模型工具責任、9/13 採用映射／完成窗口契約／C 已完成接合及當前 H4 計畫。

## 結論

**本片核心採用可以保留，未發現需退回重寫的阻擋級程式缺陷。**指引、三欄輸出、驗證更正與續作流程確實沿已驗來源。來源 Protocol 與注入 structured runnable／`accepted(raw)` 都是現有框架外的有限接點，未形成第二套 Agent 或保存引擎。

尚未完成的是新 App 的 source/provider 接合；下列事項是下一片的實際責任，不把尚未接線誤列成本片程式 bug，也不因此追加獨立架構階段。舊 CT49／CT50 品質證據不自動延伸到另一模型。

## 為什麼用了框架仍有這個問題

LangGraph 已處理節點、checkpoint 與續作；LangChain `with_structured_output` 已提供 schema、原生呼叫、JSON 解析及 `{raw, parsed, parsing_error}`。本案不需要自製 JSON parser 或 Agent loop。

但 **JSON 解析成功和模型完整完成是兩件事**。獨立探針使用已鎖的真 SDK／ConfirmedChatAnthropic／MockTransport：回覆 `stop_reason=max_tokens`、JSON 少最後一個右括號時，框架原生 `JsonOutputParser` 仍恢復出全部三欄，且 `parsing_error=None`。因此單憑 parsed 有值就保存，會把截斷結果當完整；這是保存邊界必須核對的 provider 結果，不是重新發明框架。

## 已查實的採用範圍

- 原 `4f94fbfb` extraction 檔 SHA256 `06dd3e8c…`、新檔 `af728c46…` 與 `adoption.json` 相符。
- INSTRUCTIONS 字串內容完全相同。manifest 的 `83b14376…` 是 **Python assignment 原碼加 LF** 的 hash；字串值本身的 hash 為 `0f621a77…`，兩個計算範圍不可混稱。原檔與新檔相同，沒有 prompt 漂移。
- diff 除文件／import 外，只有來源簽章入口及 provider 組裝／完成接受条件移出；`ExtractionOutput`、窗口迴圈、應用格式更正、save／resume／reextract 規則未重写。`_prepare_text` 留在同套件，不在 App 複製格式規則。
- App 以 editable package 使用本來源，來源套件測試有效；這不證明先前 C 的 wheel 已含 B1。新 wheel 驗收應在新採用產物封裝時更新，不沿用舊 wheel hash 冒稱完成。

## 要澄清的問題及最小解法

### 1. 已決定 B1 先採 OpenAI，但不是全 App 改成 OpenAI

9/13 runtime 文件說的是該片既有對話接點只驗 Anthropic，並非禁止 B1 使用 OpenAI。框架也沒有此限制。原 CT／B1 流程綁 OpenAI 是舊組裝與結果判定的耦合，不是顧問方法本身的限制。

**本案決定：**B1 下一片以 OpenAI structured output 作為產品接線的第一個 provider，沿原已驗 `ChatOpenAI`／JSON schema 路徑；目前對話顧問的 Anthropic 接點不在本決定內，不做全 App provider 切換、雙 provider 選單或自動 fallback。仍由 App 組裝模型與接受條件，套件不把 API key、模型名稱或 provider SDK 寫死。

保留原 prompt／6000、1500、16 窗口／1 次格式更正及顯式 8192 等已定語意；確認當前 OpenAI／LangChain 相容版本與實際請求 body 後再鎖依賴，不盲目複製舊版本。是否達到已驗品質由 OI-09 自然案例判斷，不能靠相同 prompt hash 保證。

### 2. `strict`、輸出上限與完成訊號必須核實際框架路徑

已裝 `langchain-anthropic==1.7.2` 的 `with_structured_output` 有 `**kwargs`，並非傳 `strict=` 就一定拋錯；實作**忽略這些額外參數**。原生 `method="json_schema"` 會送 `output_config.format`，已提供結構化能力，無須自行補 strict 引擎。把 OpenAI 的 `max_output_tokens` 原樣塞入此方法也會被忽略。

**接法：**用框架 `method="json_schema", include_raw=True`；沿既有 `ExtractionOutput.model_json_schema()` 傳 dict，保留「先保存 candidate 再進應用格式驗證／有限更正」的語意。不要為了看似更原生就直接換 Pydantic parser，讓格式錯誤被提前歸入不可更正的 parsing_error。Anthropic 的 `max_tokens=8192`／effort 在實際 model 組裝或支援的 bind 接點配置，以攔截 HTTP body 證明生效，不只驗 Python 參數有填。

`accepted(raw)` 對所選 JSON 輸出模式核正常終局及拒絕；不能只看 HTTP200／parsed，也不能把 A 的 tool_use 終局集合整批搬給 B1。串流完整性沿已有 ConfirmedChatAnthropic，不再補一套串流監視器。未知、拒絕、截斷與解析錯誤不得保存為成功；套件內既有格式更正次數仍只處理應用格式問題。

**stop_details 限制：**本地串流 mapper 的 message_delta 只投影 stop_reason／stop_sequence 等選定欄位，沒有投影 stop_details；非串流 `_format_output` 走另一條 `model_dump` 路徑。不能假定 API 有此欄位，就一定能從本案串流 `raw.response_metadata` 讀到。優先用實際保留且足夠的 stop_reason／已驗終局證據，不為取得非必要診斷新增 mapper。若確需 stop_details，先證明用途與傳遞路徑再改。

### 3. source/context 要有各自語意，旗標本身不會接通讀取

`MemorySourceReader(window_references=True, context_references=True)` 目前只擴大**驗證用途**，其 `read()` 仍是本輪 source 的 `SourceExcerpt`。B1 的 `ExtractionSourceReader.read(ref, offset)` 要回分頁 dict，不能直接拿這兩個旗標冒充已完成 adapter。

**接法：**在同一 owner 上提供 B1 窄 adapter：新工作的 validate／plan 只接受 window；讀取可依用途接 window 或 context；artifact 驗證接受兩者；publication processed_source 仍不接受 context。planning 應尊重輸入 ref 的固定範圍與位置，不把「decode 後拿最新內容」當固定來源。

context 缺 `turns/next_offset` 的問題在此 adapter 完成：無後頁要明示 None，回合資訊只能來自同一固定位置的已驗終局，不一律偽造 completed。舊 source.read 對範圍內含 Human 的回合會提供終局，只有 AI 前置問句時可沒有 turns；新接點須保留這個差異。若必要就讓同 owner 回傳所需投影，不複製第二套來源或走鏈。驗 W-13 時讀真正不可變 artifact pair，追加新回合後仍重抽原文字、正常 B1 輸入位置不前進；不增加配對登記表。

## 下一片有限驗收

1. 同一 source owner＋真 Store/Saver，正常多窗口、帶 context、無 context、失敗／取消回合原話、追加回合後原 pair 重抽及正常輸入位置不前進。
2. 真 SDK 固定回覆：正常三字串；拒絕；max_tokens 即使可解析也拒绝保存；格式錯誤與應用更正；串流中斷及原工作續作。保留实际请求的 schema、輸出上限與角色配置。
3. 新模型接受函式與既有窗口／更正預算配對，不使用常數 `lambda raw: True`；同工作續作不重設已有預算。來源 I/O 不是模型格式錯誤，不暗自再呼叫模型修資料庫。
4. 完成這個接合單位後更新 package README／adoption／封裝證據，再依映射接 B2。背景與通知沿既定完整工作單位，不趁本片造新 scheduler。

以上不是要求本片先交自然模型品質、B2 或背景完整驗收；保持零 provider，付費依 OI-09 授權。

## 本次實證及權威依據

| 獨立執行 | 結果及限制 |
|---|---|
| Memory 套件完整測試 | **146 passed／18.06s**，含16個新B1測試；原生InMemoryStore/Saver＋来源／provider替身 |
| [框架輸出探針](framework-output-review-probe.py) | **3 passed／6.52s**：正常／截斷／拒絕；真SDK＋原生structured runnable，程序內MockTransport。截斷JSON可被解析已證實；額外max_output_tokens=123被忽略，model的max_tokens=8192仍發出。這是框架行為證據，尚未接產品accepted函式。 |
| 原始碼／hash | source、adopted、prompt及精確diff已核；沒有未列明的流程重寫 |

沒有重跑 App2776、真PG、wheel隔離安裝、自然模型或UI；沒有provider出站、付費或產品程式改動。

查閱 2026-09-14，官方現行滾動文件；本地版本 LangChain1.4.0/core1.6.3、LangGraph1.2.11、langchain-anthropic1.7.2／anthropic1.5.0，框架／SDK為已發布MIT套件，模型API依服務條款。沒有依此升級依賴。

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)：refusal／incomplete 是需另處理的結果，schema 不等於所有回覆必然完整可用。
- [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)：原生 output_config.format，refusal／max_tokens 可不符合schema；不能因HTTP200就當成功。
- 本地 `langchain_anthropic/chat_models.py` 的 `with_structured_output`／`_make_message_chunk_from_anthropic_event`：框架已提供原生schema及解析；忽略extra kwargs與串流metadata差異由本次精確版本原碼、固定SDK探針核對。這是版本限制，不能推論所有framework版本都相同。
- [採用映射](../../2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)、[窗口契約](../../2026-09-13-jd-interview-window-source-contract.md)、[runtime接合界線](../../2026-09-13-jd-ai-runtime-and-tools-slice.md)：已驗顧問方法可採用，新App接合及跨provider品質仍需另驗。

共同原則是使用原生結構化輸出、核真實結果、由App保護保存；`accepted` 函式與本案來源adapter是有限整合，不宣稱大廠指定相同介面。
