# CT45：固定版長訪談、三層記憶與回查驗收

> 延續已核准CT42／44驗收設計；使用executing-plans逐段驗證。Owner本輪授權持續局部優化及同模型effort／token／呼叫額度調整，重大才討論。

**Goal:** 驗證整份職位的訪談、案例詳記、共同工作理解、修訂與按需回查；不製作JD、不接production。
**Architecture:** 真FastAPI入口、PG Saver/Store、現有A/B1/B2及自然通知；只換新空白實驗資料庫。固定CT44程式，先驗A/B1/B2 Luna high；不是新增agent或新記憶方式。
**Spec:** [CT44結果](../specs/2026-09-09-ct44-preservation-results.md)、[CT42驗收範圍](2026-09-09-ct42-final-long-interview.md)、current register及Owner完整goal。

## Preflight

- Topic LLM-Q019，stage G8，前輪是progress（局部提示／額度接入、558＋41通過）。
- 唯一問題：固定新版本能否從空白持續理解整份工作，保留既有細節、修訂已更正部分並沿引用查回？沒有產品語意blocking question。
- 官方[GPT-5.6提示指引](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)本輪重讀：明確結果／約束／完成條件、先baseline、每次改一組、提高effort須有代表性證據、少工具迴圈不優先於正確性。它不保證個別prompt或高推理一定正確。
- [官方計價](https://developers.openai.com/api/docs/pricing#text-tokens)核對Luna標準input0.20、cached0.02、write0.25、output1.20 USD/M；usage估費而非帳單。既有帳本保守預留並計入所有重試。
- 不重開closed帳本；新180次／US$0.75護欄，含A/B1/B2／回查，遇額度或品質失敗先保留證據。只送agent合成訪談及其生成Memory至官方Responses endpoint，不送真員工／其他文件或秘密。

## 固定設定與測法

- source HEAD `587065b5`，記錄src雜湊；A/B1/B2 high，8192輸出、原生all_turns／compaction12000（沿前次實驗設定），A12/11、B2 12/12。這是驗收設定，不宣稱medium預設通過。
- 新資料庫只含本次合成文件；真模型走SDK、工具、錯誤與背景排程不mock；setup/audit只隔離排程及禁止外網。每輪重開app驗保存延續。
- 沿前端接案完整範圍，但讀實際顧問問句後再寫員工回答；含糊核准者→查證、兩個相似網站不同原因、估算／开发／部署／維護／彙整／交接／低頻升級。追加真正撤銷與新補充，再確認整份工作，不為填欄位無限問未知的他人權限。
- 逐層逐段核對：原始Q/A完整且含可見commentary；詳記保留當批全部職務相關條件／行動／結果／責任／頻率／不確定性；正文正確歸納共同工作，不混案例、不漏仍有效內容、不殘留被解答的同一未知。未說不是撤銷。
- 閱讀能分層深入、引用指向真實詳記及原話；空近期context診斷讀者不注入答案、不寫Memory。查一份正文不等於證明可發現所有案例。
- Compaction／reasoning僅驗不透明item傳遞與源資料保存，不解碼或杜撰模型內部思考。發現測試腳本限制與產品失敗分開記，不能過觀察timeout就重啟活著的工作。

## 工作與退出條件

- [x] 重用已讀既有driver/ledger，建立CT45設定及成本帳本，初始化空白文件；不改產品。
- [x] 正常逐輪訪談、確認背景進度及三層產物；第8輪B2失敗，已分類及保存，非完整訪談通過。
- [ ] 新補充、明確撤銷、相似案例及遠期原話回查；原始對話與詳記引用逐項核實。
- [ ] 官方方法對照後才做必要局部修正；每項真失敗保留、修後重測，最後固定版驗收不可混用修前結果。
- [ ] 短結果報告＋獨立機器證據＋逐輪問答＋review，更新register，適用測試通過後本地提交/tag；不push/merge。

通過代表性情境不等於數學保證所有職位100%正確。仍有重要範圍遺失、來源錯引、案例混淆或無法完成訪談就G8保持OPEN；不得以語法驗證綠燈替代語意審核。

## Closure

CT45原始失敗與70次請求已封存，未做的收尾／新補充／撤銷／回查仍未勾選。局部後續轉[CT46–48結果](../specs/2026-09-09-ct46-48-edit-routing-and-budget-results.md)，不在這份固定版計畫混入修後成功。下一次完整驗收另用固定新版本；不重開CT45帳本。
