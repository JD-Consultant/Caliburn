# JD 契約補正：離線驗證與 SDK 傳遞

2026-09-10；JD-R002/C03。對應[責任稽核](../../2026-09-10-jd-responsibility-and-evidence-audit.md) TF01–04／ER01–03／DB02–04 的設計補正。這是有限契約驗證，不是正式編輯器、DB、ToolNode 或自然模型測試。

## 1. 實際修改與結果

唯一可修改的設計 SSOT 仍是[正式候選 schema](../../contracts/jd-editor-v1.schema.json)。本目錄的 before／after 是歷史證據快照，不能作 runtime／codegen 的第二來源。

| 材料／驗證 | 結果 |
|---|---|
| [補正前 schema](schema-before.json) | 85 defs；SHA256 `6B42BA220C0102590DC651692BE7497AE400BD713CB6F0D86FA1C5103F753F67` |
| [補正後 schema](schema-after.json) | 86 defs；SHA256 `CED26A3B625DE891989A63D5F12E4AC884484083D7F677CF10AD8C54E318B973` |
| [同一最終檢查的補正前結果](before-results.json) | 201 checks，136 項不符補正後預期；全是可定位 assertion，不是 schema 解析／環境出錯 |
| [補正後結果](after-results.json) | 201 checks，0 mismatch；全部 definitions 可編譯解析 |
| [模型輸入／結果檢查腳本](check-contract.cjs) | Node 22.12.0／AJV 8.20.0＋既有 ajv-formats，Draft 2020-12；不 coercion、補 defaults、刪欄位或修改 payload |
| [SDK 實際送出內容](provider-request.json)、[輸出](provider-output.txt) | 同一既有 LangChain／ChatOpenAI／OpenAI SDK，1 次 MockTransport request，本地固定 400 結束；三工具參數及正式說明與 SSOT 完全相符 |

201 項包含：模型／resolved set-unset 交集、單一 span 意圖與 saved HTML 表示保留、只在內容附著來源、write action 全組合與未確認回執優先、read_failed 與唯讀錯誤出口、failure refs、no_change 不發布暫時 operations、完整官方 r2、App-only 欄位拒絕、四個現行契約例與三個來源例。

其中 `baseline_source_scope_is_not_a_schema_claim` 明確預期未發配但字串合法的 source ref 仍可通過 shape；這是後續 App owner 必驗的語意，不將 schema-valid 冒稱來源有效。scope／head／原生座標／grid／跨欄位 ref 相等及真實 receipt 也未由這組測試證明。

## 2. 先重現，再修正的軌跡

先建立檢查、對尚未修改的 schema 執行，取得[初次紅燈](initial-red-177.json)：177 checks、116 mismatch。修正參數與動作矩陣後，追加 no_change 的兩個反例並得到[中間綠燈](initial-green-179.json)：179 checks、0 mismatch，當時 schema hash 為 `48C30CC11DD2EE6AA5016922322D2CA2906E3D61B9F710E9CF91FD264708F477`。

最後補足 failure／busy 結果引用限制、conflict 原結果正例，以及七個正式文檔例子；以同一最終 201 checks 重跑 before／after，結果如 §1。這些計數不是新增了同等數量的員工情境；多數是封閉狀態矩陣的組合。舊 F02／provider／schema-validation 材料原样保留，沒有回填舊 hash 或把其失敗改判成功。

## 3. Provider binding 證據範圍

[實際腳本](provider-wire.py)沿用既有 `build_agent`／`wrap_model_call`／`build_model`，只使用 dummy API key 與 `httpx.MockTransport`，不開 DB、不執行工具。三個 tool description 取 SSOT 的 `*ModelInput.description`，不再是舊 probe placeholder；parameters 同一 root＋refs closure，包含共用 property constraint，沒有模型 attributes／頂層 source_refs。

固定版本：LangChain 1.4.0、langchain-core 1.6.2、langchain-openai 1.6.0、OpenAI SDK 3.8.0。三工具 raw function 保留 `strict:false`；非 JD control tool 仍省略 strict，`parallel_tool_calls:false`／`store:false` 不變。一般 BaseTool converter 對照仍把 refs 4／59／4 變成 0／0／0；這支持沿既定 raw function 接點保留完整 schema，不支持宣稱 non-strict 是跨廠偏好。

執行時既有套件產生一次 HTTP socket-options／環境 proxy auto-detection 提示；實際同步請求仍被自帶 MockTransport 捕捉，固定回 400，沒有外部 provider 請求或付費生成。這不是 provider 的 schema rejection，不能據此說供應商接受或不接受本方案。真 ToolNode／來源執行與自然模型效果仍待後續切片。

## 4. 重現及後續驗收

在 repo root、既有已安裝依賴下執行 `node docs/specs/evidence/jd-contract-closure/check-contract.cjs`；預設檢查 current SSOT。指定 `docs/specs/evidence/jd-contract-closure/schema-before.json` 可重現相同預期下的原缺口；before exit code 應非零。腳本同時讀現行契約四例與來源附件三例，後續若文檔例子變更須另記版本，不能將本次觀測當成新例已驗。

SDK 腳本在 `S:/caliburn/.worktrees/analysis-only-agent/experiments/analysis-agent`、既有 `.venv` 下執行本目錄 `provider-wire.py`；它會生成本地 request 材料，後續執行須另開結果位置或先保留本封存，不覆寫歷史觀測。這不啟動服務、也不需要真 API key。

原生 span 更新／來源保存、兩連線交易、取消／關頁重開、錯誤閉合及正式人編，依[六切片計畫](../../../plans/2026-09-10-jd-editor-core-implementation.md)驗收。SQL 與 Node 秒數是本案起始配置，並未在本輪量測效能或驗證 OS／DB 的取消時限；本輪只完成策略與契約閉合。
