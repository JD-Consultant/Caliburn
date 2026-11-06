# 契約策略與邊界

每個邊界只有一份可修改的來源；HTTP、模型工具與內部能力按用途投影，不強制共享相同 envelope。生成位置及命令見[資料與契約接線](../implementation/data-and-contracts.md)。

## 現行規則

HTTP 由各模組 Presentation 的 Pydantic request／response 與正式 routes 定義，FastAPI 導出 OpenAPI，前端生成 SDK、型別及 Ajv runtime guards。SSE 具名事件也由正式 Schema 導出，不能另維護一套事件常數。

模型工具的參數型別、description、StructuredTool 定義與結果投影由各 Bundle 維護。檢查應使用實際初始化後的模型可見 schema，並覆蓋 handler 與結果，而非只比對手寫副本。

Domain 不直接依賴傳輸 DTO。邊界完成驗證與轉換後才呼叫內部型別；正式來源、版本、交易與權限仍由能力模組裁決。OpenAI 原生 items 沿 SDK 接續契約，不套入另一套 App 訊息格式。

## 驗證及相容

型別註解不驗證 runtime 值，生成型別也不保證 Python 與 JavaScript 接受集合相同。自訂文字、整數、UUID 或 nullable 政策時，須同時核實際入口、OpenAPI 及前端 validator 的代表性正反例；不得只靠各語言的 `strip`、`\s` 或 coercion 推定同義。

共用 HTTP UUID 接受連字號形式及十六進位大小寫，不接受 compact、URN 或大括號；以 [HTTP 值型別](../../apps/backend/src/caliburn/shared/presentation/api/values.py)為來源。文字是否非空沿 Domain 的 Python `str.strip()`／`str.isspace()` 語意，OpenAPI pattern 投影同一碼點集合，不靠 JavaScript `\s` 推定同義。保留原話，不偷偷 trim、截斷或改寫。

wire 整數上限須明訂在 JavaScript 可精確表示範圍 `9007199254740991` 內，既有較小界線保留；JSON 數學整數是否接受 `1.0`、拒絕布林或字串，須沿各正式來源核對。新用途若超出範圍應明定另一種表示，不讓前端悄悄失真。錯誤只回安全分類及可行下一步，不回顯金鑰、敏感輸入或完整 provider 例外。

模型只提供需要判斷的內容意圖，Workspace、執行身分、正式 UUID 與可信版本由 App 綁定。來源短碼不是權限憑證；工具輸入合法也不等於有寫入資格。未保存結果可能在恢復時重做，不能以 call ID 配對宣稱業務恰好執行一次。

Agent 的破壞性 Node、Tool、Hook 或 State 變更須更新 `resume_version`，詳見 [Agent 設定](../../apps/backend/src/caliburn/modules/agent/README.md#明示設定)。

## 公版共用契約

[ocs-contract](../../packages/ocs-contract/README.md) 以 JSON Schema 為來源，生成公版文件的 Python model；[indexer-contract](../../packages/indexer-contract/README.md) 以 Pydantic 定義公版查讀形狀。兩者由 `occupation_reference` 使用，是後端正式依賴，不代表公版是另一套選用部署。

## 交付流程

1. 定位唯一來源、資料 owner 與受影響消費端。
2. 改動權責、跨層契約或相容承諾前，依[變更範圍](../../CONTRIBUTING.md#變更範圍與審查)確認有效決定。
3. 同步來源、生成物、handler 與消費端；生成檢查在暫存目錄比較，不手改生成檔。
4. 執行適用的邊界、業務及 UI 驗證；離線工具 schema 通過不能代替真 provider 或產品品質。
