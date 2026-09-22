# JD 顧問：當輪訪談來源接合

狀態：隔離接合已驗，JD-R002／OI-02 局部；2026-09-13。入口：[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)、[未解事項](2026-09-13-jd-app-open-issues.md)。當輪改動畫面已收斂，不增舊對話選輪入口。

> **2026-09-20 model-view successor：**本稿驗證的 source owner、signed locator、固定原話回查與 JD `jd_source_link` 保存仍有效；「把 `source_ref` 直接送給模型再由模型回填」則由[跨顧問、Memory 與 JD 的模型安全證據契約](2026-09-20-cross-agent-evidence-and-jd-context-contract.md)取代。正式 ref 留在 Runtime／artifact／JD，A 只看並提交本 run 的 `evidence_key`。這是待施工的 adapter 對齊，不改本稿當時的實測事實。

## 效果與責任

先接通「本輪已保存原話 → 顧問取得引用 → JD 共用保存驗證 → 固定原話回查」。原話繼續由同一 native Saver 保存；不新增原話表，不將 JD 當 Memory，不引用可反覆改寫的 Memory 路徑冒充永久原話。本切片不宣稱完整 Memory、背景整理、專業指引或自然訪談品質已完成。

接點稽核：[Memory](evidence/jd-consultant-source-integration/memory-seams.md)、[原話](evidence/jd-consultant-source-integration/source-seams.md)。引用是否可讀由 App 驗證；內容是否忠實、有沒有把顧問的問題當員工事實，仍須顧問判斷及後續品質驗收。`basis_digest` 只表示 JD 目標當時內容，不是語意正確證明。

## 有限實作

1. 使用現有 `AiRunCheckpoints`，在 native `durability="sync"` 已保存本轮 Human 後固定 root 與 source child checkpoint。有限 native 實驗先核對真正 model request 的時序，未證實不臆測 checkpoint 位置。
2. source owner 自行選當輪 Human（App 的 run ID）及它前面最近一則有公開文字的 AI 回應作上下文。只有員工原話代表員工陳述，AI 文字不可視為已確認事實。App 產生 opaque `source_ref`，LLM 不計行數、拼 checkpoint 或填資料庫欄位。
3. 引用使用既有 ItsDangerous 標準簽署、同一持久 key／dataset，獨立 purpose／salt；固定 dataset、document、run、root checkpoint、source namespace／checkpoint、first／last message ID。這是來源 owner 的定位，不是 JD ref／chat cursor 的別名；不自建通用簽署或定位引擎。
4. 每個前景回合只有一份來源選取；後續工具迴圈不因 checkpoint 前進而重新發配。真正 model request 必須仍有對應的原 message role、ID、完整內容，才能告知引用可用；系統通知僅含 App metadata，原話不複製到 system 或偽造 ToolMessage。將來壓縮移除對應原話時，需接原始來源讀取，不將這份通知當成讀過的證明。
5. AI 與人工 service 注入同一來源 owner resolver。沿既有 `command_context → bind_edit → domain → SQL` 保存來源字串與目標關係；不增加另一條規則或原話雙寫。操作查回、恢復依原 durable binding／receipt，不重建引用或重播模型。
6. source owner `read` 只讀固定 checkpoint 與確切消息範圍，輸出原公開角色／文字；跨文件／dataset、錯 purpose、缺失來源或不符範圍失敗，不退到目前對話。真正 UI 來源回查與較早 Memory 所需來源讀取沿 OI-02 接續，不能把 metadata 的 `not_checked` 標成已驗。

## 依據及適用界線

查閱日均為 2026-09-13；官方網站為現行滾動文件，版本效力以本地 lock 及有限實驗核對。以下是公開能力及本案映射，不宣稱供應商採用本案引用格式。

| 依據 | 官方事實／本案使用 | 版本、狀態、授權與限制 |
|---|---|---|
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | checkpoint 與 Store 各有責任，子圖有自己的 namespace；採既有固定原生觀察讀原話。 | 本地 1.2.11、Saver 3.1.2，穩定 API，MIT；未採建議中的清除歷史，仍有來源引用的 checkpoint 須保留。 |
| [LangChain middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom) | `wrap_model_call`／`request.override` 可在呼叫前調整 request；本案用來提供來源 metadata、保留原角色。 | 本地 1.4.0、core 1.6.3，穩定 API，MIT；實際時序須 native 驗證。 |
| [Anthropic memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) | client 執行儲存操作並控制資料，context 可依需求讀取；不代表需要第二份 Memory 或特定 DB schema。 | 現行官方工具契約，商業服務條款；只作能力參照，本輪 0 provider。 |
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) | App 執行工具，原始請求、工具呼叫及對應結果維持關係；本案保留原消息及既有工具結果，不造未發生的讀取 ToolMessage。 | 現行 Responses 契約，商業服務條款；不宣稱 OpenAI 使用本案來源格式，也不變更本地既有 Anthropic adapter。 |
| [OpenAI customization](https://learn.chatgpt.com/docs/customization/overview#skills)／[Anthropic Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) | 說明可按需揭露；不把所有理解／原文塞進 system。 | 現行官方產品文件，各自服務條款；不表示本切片需要 hosted code execution 或新 Skill 引擎。 |
| [ItsDangerous serializer](https://itsdangerous.palletsprojects.com/en/stable/serializer/) | 沿本 App 已驗證的 serializer 與用途隔離，來源 token 不含原話正文。 | 本地 2.2.0，穩定，BSD-3-Clause；簽章不等於語意核實或資料加密。 |

## 驗收與停止條件

- native Agent request 前已保存原話；同輪多個 model request 的 ref 固定；原 messages 不被修改或複製成 system。
- 引用只覆盖確切原話與標明的 AI 上下文；繁中、換行、工具／thinking block 不誤投影；被移除或更改的 request 原話不能冒稱已讀。
- 錯 key／dataset／document／purpose、位置或消息範圍錯誤、來源缺失皆有限失敗，不 fallback 最新、不模型重試。
- 使用來源 ref 的 JD 寫入與查回實際保存結果一致；重開、晚期更正後仍讀原來源，不影響原話或 Memory。
- 固定 request、native Saver、真 PostgreSQL 證據分開；獨立審查處理具體缺口後停止擴測。付費自然品質及真瀏覽器不得代稱通過。

## 實際結果與下一步

- [原生時序](evidence/jd-consultant-source-integration/native-timing.md)：真正 model request 前已同步保存 Human，後續 child 前進不影響固定來源。
- [來源模組](evidence/jd-consultant-source-integration/source-results.md)：44 PASS；固定來源、角色／全文、跨範圍拒絕、缺來源與故障均有反例。
- [App／故障](evidence/jd-consultant-source-integration/runtime-results.md)：103 PASS；來源故障不冒充模型參數錯誤、不繼續模型步；人工來源讀取結束前不關 Saver。
- [真 PG 縱向](evidence/jd-consultant-source-integration/postgres-results.md)：1 PASS；6 次程序內 Mock SDK request、兩輪訪談、手改、最終 JD 版本4／操作3／來源關係5。新 connection／serializer／owner 回查原話及原操作不重發引用。首敗是測試忽略原生讀取續頁，已修測試，沒有放寬產品規則。
- [獨立審查](evidence/jd-consultant-source-integration/review.md)：CSI-R01／02 故障歸因與讀取排空修正後窄複核；實際界線見審查稿。

一般入口仍不啟動模型；0 provider、0 新 DB schema、0 正式採用切換。這不是自然模型品質、全 Memory、Windows 新程序恢復或來源 UI 驗收。下一集中接既有 Memory／案例和專業指引的正式模組／保存生命週期、較早原話讀取及 UI，依 OI-01／02 推進；沒有新產品問題需要 Owner 重選。
