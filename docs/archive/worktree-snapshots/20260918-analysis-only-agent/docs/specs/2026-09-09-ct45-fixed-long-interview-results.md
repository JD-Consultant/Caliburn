# CT45：固定版長訪談，背景第八輪仍未完成

2026-09-09 · LLM-Q019 · **G8 OPEN／不得稱穩定完成**。
[計畫](../plans/2026-09-09-ct45-fixed-long-interview.md) · [實際八輪對話](evidence/2026-09-09-ct45-transcript.md) · [完整請求、各版Memory、來源核對與腳本](evidence/2026-09-09-ct45-fixed-long-interview.json)。

## 固定條件与結果

從空白合成「接案前端工程師」開始，固定CT44 `587065b5` 的src雜湊。真API入口、PostgreSQL Saver／Store、自然通知及既有背景流程；A/B1/B2全部Luna high，輸出8192，前景12模型／11工具、背景12模型／12工具。原生reasoning all_turns及compaction12000。未預填Memory、不製作JD、不改production。每輪讀顧問真正提問後再回答，沒有把理想答案塞給整併模型。

8輪前景都completed；主要涵蓋需求／估算、兩個相似網站、驗收／維護／部署、交付／交接、低頻套件升級，最後升級追蹤尚未回答。前景22、抽取6、整併42，共**70次請求，usage估US$0.10913243**，180次／US$0.75帳本closed。前景回覆中位9.205秒，最長41.30秒；不是背景延遲，也不是全體職位的效能保證。

第8輪B1成功，B2達12模型／12工具後仍無final，既有框架報`ModelCallLimitExceededError`，背景blocked，Memory停在revision7。**沒有發布該次staging，也沒有把被拒patch算成功**。第9輪員工文字已準備但沒送出，不算訪談完成。未進行最後全職務盤點、撤銷對照或空近期context深查，這些仍未驗收，不拿前七輪代替。

## 已觀察到的效果與問題

### 內容與更正

- 最初「印象中產品負責人核准、未核合同」保留不確定；第4輪查證營運主管後，A實際呼叫C工具，更新Memory，不只口頭答覆。
- 青禾付款**成功但權限畫面未刷新**，雲岸**連點導致前端重送、後端仍需冪等**，目前正文未把两案原因互換；雲岸沒有金流。
- 雲岸候補名單只評估過但**本期不做、尚未開發**，目前正文沒有變成已交付功能。
- 每案初次操作說明、重大變動才追加說明、相關文件受影響即更新，三個條件同時保留；每天排查不等於當日修完、每週五彙整所有專案亦保留。
- 第6輪共同段仍泛稱估算等「可能」工作、尚未確認；第7輪新交付資訊後該舊段消失。不能因此忽略中間版本的不精確性；獨立review另列判斷。

### CT45-Q01：長patch抄錯引用，反覆修正耗盡（Important）

第8輪B2 #59讀正文、#60讀導覽，#61首次patch，#62再patch、#63重讀、#64patch、#65搜尋、#66–67重讀、#68patch、#69patch導覽、#70重讀；下一模型被12次上限阻止。

#61、64、69的舊context中，真實`839db2c1-...`被抄成缺字`839db2c-...`或不同字`839db2c2-...`，官方SDK拒絕不匹配上下文。第62次patch有套到staging，但帶出多餘列表符號；後續有修訂，仍未完成。這是**模型生成patch／重試路徑**失敗，不是沒有工具結果、provider不支援，也不證明matcher應該忽略不同ID。不加自製模糊匹配。

現有prompt已有短檔多處改動可全文write、長檔局部patch、錯誤後回讀、保留舊細節等規則。不能因為看到cap就假定應再全面增加；先用相同輸入B2 xhigh局部對照，見[CT46](../plans/2026-09-09-ct46-b2-effort-replay.md)。單次成功也不代表穩定成功率。

### CT45-Q02：來源地址存在，但替換後不支持同一內容（Important）

第6輪正文將維護與估算指向`cc78445a-.../summary.md`。第7輪寫入後移除該鏈結，末尾卻將這些工作與交付一起稱為`4f9e69f1-.../summary.md`的內容。後者的實際詳記只談交付／前端交接，不含前兩者的完整案例。導覽也沿用這種過寬的來源說明。

**原詳記還在，不是物理遺失；但回查導引變差。** 程式可驗地址存在及原話可讀，不會自動判斷引用語意正確。不能把完整來源audit通過當成Q02已修好。補查其他詳記是否能找回尚未真測；不先聲稱查不到，也不稱路由完整。

## 原始對話、壓縮及引用核驗

第4／5輪前景請求#34、38產生原生compaction，後續不透明項目有重送；沒有解碼／猜測其內容。重開app後，**8員工＋8AI可見回答全部精確相同**；兩次C publication的來源片段亦與canonical問答相符。

獨立唯讀核對**所有6份已觀察B1詳記**（不只現在正文引用的四份），逐頁source/context片段皆可對回canonical原文；6份詳記与候選全文封存。未被現在正文連結的兩份：第6輪維護／估算（Q02）；第8輪套件升級（B2未發布，符合失敗狀態）。兩者不能混稱同一錯誤。

Audit首次誤把抽取清單當dict而TypeError，未呼叫API或改資料；修正測試腳本後完成六份來源核對。此harness錯誤與產品Q01/Q02分開保留。原始opaque只保留hash／必要metadata，未封存金鑰或加密內容。

## 官方依據與下一步

- [OpenAI GPT-5.6提示指南](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)：先明確結果、保留事實／引用與停止條件，檢查工具依賴，使用真实trace一次改一組；先建立effort baseline再比較high／xhigh，不以少迴圈取代正確性。
- [OpenAI apply patch](https://developers.openai.com/api/docs/guides/tools-apply-patch#implementing-the-patch-harness)：app套用並回報成功／失敗供模型續作；本案SDK接線及限制已在[CT11](2026-09-07-official-memory-patch-trial-results.md)核對，不重開編輯器選型。
- [Anthropic提示建議](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)：清楚說明用途與約束、依來源處理長內容；不推論Claude效果必定能移植到Luna。
- [Luna官方模型](https://developers.openai.com/api/docs/models/gpt-5.6-luna)確認xhigh可用；[計價](https://developers.openai.com/api/docs/pricing#text-tokens)只用於usage估算，不當成帳單。

Decision：CT45不改產品src或預設；保留完整失敗及原PG，先做CT46同B1／同寫前基準的B2 effort局部對照，Q02另外審提示与來源關聯。Status：G8 OPEN。Reopen trigger：修後同批能完成且引用／重要舊細節正確，才再進固定版新補充／撤銷與完整訪談；不得將混合設定結果稱成從頭驗收。無新Agent、schema、tool、語意validator或retry loop。
