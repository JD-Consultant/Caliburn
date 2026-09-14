# P3 AI controller 操作者採用：有限文件同步

2026-09-10。只在 isolated 工作樹同步；root 採用的是待付費授權的 P3 測法，非 Owner 既有真人豁免、自然品質通過或付費授權。有限獨立 spec／quality PASS 的受審候選 SHA256：`3016d934f2ad174c83f7925b56e9abe16ec8261f7969b42b62eec2d2eb109d43`。

**文件同步與靜態保全核對完成，供 root 核對後同步主工作區。** 不改 register／總計畫；proposal header 按交接要求標 root 已採用／文件同步中，原候選正文作歷史保存。無程式／DB／Job／model／key／install／git 動作，0 產品 provider 請求。未測 guard／自然 trial／真人使用，不阻 Task4／5／6。

## 1. v1 先封存，再更新 active v2

修改前核對原 manifest 五檔SHA／bytes與品質source hash；受審design hash也一致。先以原檔複製，封存五份卡包內容、原manifest、原品質source共七份至 `docs/specs/evidence/jd-product-p3-calibration/archive/v1/`。`snapshot-manifest.json` 記每份原路徑、SHA256／bytes，原manifest逐byte不改；snapshot不hash自己。封存先完成才寫active。

原品質source SHA256：`1407e42b0a3c0d87c73caff6d37c05faa74020973f8f3d6441594bbdc6bbd92c`。archive中的相對links保留原bytes，僅供歷史證據，不當active入口。主工作區尚未由本task更新。

## 2. 精確 diff 與修改範圍

[逐筆精確before／after差異](task-p3-operator-adoption-text-diff.json)包含所有文字替換、budget日期append及manifest完整前後JSON；[比對结果](task-p3-operator-adoption-checks.json)保存固定區段SHA與reverse-diff相等結果。未使用git命令。逐檔套回反向diff會重建原封存文字；設計反向diff可重建受審候選完整SHA。此diff不是摘要性猜測。

|檔案|實際改動|
|---|---|
|品質材料|僅§6：增加root採用測法沿革；「由人」改既有AI controller；「無模擬員工LLM」改為明示controller在模擬，但不另啟provider員工／評分模型。補非盲／非獨立／非真人與平台成本區分。|
|employee-card|v2與操作者metadata；從首個##起全部正文原樣。|
|release-protocol|v2／AI操作者header，僅在原禁止模擬員工句改成已採controller與不新增provider的範圍說明；揭露规则／W映射／事件次序不改。|
|oracle|只改v2及操作者metadata；所有語意規則／Q表原樣。名稱的「獨立語意oracle」不等同獨立評讀，metadata已明說同controller判讀不是獨立人工。|
|README|v2、操作者文字、已採測法與v1封存入口、曝光／非盲／非獨立／平台費用區分；仍NOT AUTHORIZED／0trial。|
|results-template|v2／AI操作者效力metadata、操作者／判讀者欄；仍空白結果、不填runtime或usage。|
|manifest|v2、新sourceSHA、五檔SHA／bytes、追加曝光、operator_method與revision_history；保留建立時間與v1歷史；execution整物件與runtime整物件原值相等；scope_excludes僅澄清Product runtime or architecture changes（v2調整的是operator test method）。|
|operator design|僅首段當前狀態、有限review與同步路由；保留受審全文作沿革，不重寫研究；header review／sync改走durable evidence路由。|
|budget preflight（scratch及durable）|僅日期補記：原真人card operator是舊測法假設而非Owner硬裁決；原文與P3-B01–04／OFF01–09不改。|

## 3. 保全驗證

- archive七份檔案SHA／bytes全部吻合snapshot；其中原manifest仍原bytes。
- active v2五檔SHA／bytes全部吻合manifest；sourceSHA吻合品質原件。
- 品質§1–5完整前綴（涵蓋§4–5）原樣；§7–9完整後綴原樣，P6真員工／未見案例及原人工評讀門檻未降低。
- card從首個##起（開場／W01–10／晚期W05／M-W1-DOC／CHAT）原樣；oracle從首個##起（揭露、支持／排除、M與Q及嚴重度）原樣。
- 對quality、五份卡包文字與design逐筆反向套回精確diff成功，未出現未列文字差異。release只有操作者相關替換，沒有改W或事件條件。
- manifest.execution完全相等：NOT RUN、NOT AUTHORIZED、0trial／0requests、12／180／1.00、含背景失敗均保留；runtime所有null與pending狀態完全相等。
- v2未新增任何員工／judge provider；controller是AI、已見oracle、非盲／非獨立、平台運算與App美元帳本不同範圍均明示。原4個budget缺口未關閉。

固定區段SHA256（UTF-8文字位元組；非整檔SHA）見下表，v1／v2兩側完全相等。

|區段|SHA256|
|---|---|
|Quality sections 1-5|61f2b70cacf5b238e686064a4270ac0f2a93d7b4c67f349355ac2491b7b9453b|
|Quality sections 7-9|086ba1e265ffc216af2d2292c7a3276907d51fda7676f4784c4445dceef0b93f|
|employee-card.md all sections from first ##|d0ae576fa334c24a7f4540b6508b76e6c1a3ee9ebbe4c43152fd23a36b24da19|
|oracle.md all sections from first ##|e1623614a5217f7eddcb2791d8ca6a98ac0fe34a49ea5d2849225610edc750b5|

## 4. 精確修改／新增檔案與完成時SHA

本輪修改10檔；新增archive8檔、scratch精確diff／checks／本報告3檔、operator-adoption逐byte副本3檔，共14新增檔。報告不hash自己。以下以isolated checkout為相對根，沒有改主工作區、register或總計畫。

|類型|路徑|SHA256|
|---|---|---|
|修改|docs/specs/2026-09-10-jd-product-quality-acceptance.md|0a81e44018e55bdcf2d38780d229709750d7dfba932a0cd4c638a9533f47215e|
|修改|docs/specs/2026-09-10-jd-natural-calibration-operator-design.md|58635bbe45f5888e399203eea92ac9e9f482d141bcca0ab0c159abe6c297bee6|
|修改|.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task-p3-budget-preflight.md|d1138039a5564504a972186ae2131913e157794448cdf80fd14fe07dbe89c8e5|
|修改|docs/specs/evidence/jd-product-p3-calibration/employee-card.md|bd54e73337ffd0cbd41b8578f430d647ed433802bd9295fbf724f2ee04170281|
|修改|docs/specs/evidence/jd-product-p3-calibration/release-protocol.md|4db446fea06d51b8451bac58e7734aa1c9f7600c67231c4b9248180aeb57a46f|
|修改|docs/specs/evidence/jd-product-p3-calibration/oracle.md|61f08183f5a85ef7be29cdf9e984f440013fab61d206b48f7c023b7b95c33b60|
|修改|docs/specs/evidence/jd-product-p3-calibration/README.md|0c2d1275ce251e68ead12246a25cb67bb406cc49a54d2d58a91f1be58dbdfee8|
|修改|docs/specs/evidence/jd-product-p3-calibration/results-template.md|aef13928a9a28adaafbbd6543903bd4b003912e5c49ef7043cf3607e7c34752d|
|修改|docs/specs/evidence/jd-product-p3-calibration/manifest.json|5fcbc77216a0fbe55bcd489d10dc270fa4c98c04877d0f749a2c87b8c30dc6a2|
|新增|docs/specs/evidence/jd-product-p3-calibration/archive/v1/employee-card.md|231d8020e72a11b607f35be8a7daf8ac4ec38b1a8733b5fa516110c8a669262a|
|新增|docs/specs/evidence/jd-product-p3-calibration/archive/v1/release-protocol.md|923686b5c4fe6d55186bdbdbefb5218646bbcf73fd2a1e609c9a32cdea9728dc|
|新增|docs/specs/evidence/jd-product-p3-calibration/archive/v1/oracle.md|8b157e14dc1097e1129098a26a42b23b279925352f8a2d2ea44c074e21edbf52|
|新增|docs/specs/evidence/jd-product-p3-calibration/archive/v1/README.md|910042a810869dd9e93864eaf8f4f45bc0d43a08ccbd29d6d3c776d60c9563cb|
|新增|docs/specs/evidence/jd-product-p3-calibration/archive/v1/results-template.md|cf3d1087c94e8de9fc0231cf6da66e0534db56c1dd78534d961f48e53b011f79|
|新增|docs/specs/evidence/jd-product-p3-calibration/archive/v1/manifest.json|5d4598ceca456f3451fd594c23687902b7596bf9154a204f0b24d43df5201eeb|
|新增|docs/specs/evidence/jd-product-p3-calibration/archive/v1/2026-09-10-jd-product-quality-acceptance.md|1407e42b0a3c0d87c73caff6d37c05faa74020973f8f3d6441594bbdc6bbd92c|
|新增|docs/specs/evidence/jd-product-p3-calibration/archive/v1/snapshot-manifest.json|663c5b146cc1602b71244b4b076f1a8b94a70d36fda14a29854319fa989e8d44|
|新增|.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task-p3-operator-adoption-text-diff.json|b07593d007f298de131af7d925e0f377f55388a1685a311a9d28f83eb5c3ec53|
|新增|.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task-p3-operator-adoption-checks.json|7b23448a56138bf32e98b9793b3adb3c344253206b7e7b4ae7f9ddc45a45bc49|
|新增|.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task-p3-operator-adoption-sync.md|本報告不hash自己|
|修改|docs/specs/2026-09-10-jd-natural-trial-budget-preflight.md|d1138039a5564504a972186ae2131913e157794448cdf80fd14fe07dbe89c8e5|
|新增|docs/specs/evidence/jd-product-p3-calibration/operator-adoption/task-p3-operator-adoption-text-diff.json|b07593d007f298de131af7d925e0f377f55388a1685a311a9d28f83eb5c3ec53|
|新增|docs/specs/evidence/jd-product-p3-calibration/operator-adoption/task-p3-operator-adoption-checks.json|7b23448a56138bf32e98b9793b3adb3c344253206b7e7b4ae7f9ddc45a45bc49|
|新增|docs/specs/evidence/jd-product-p3-calibration/operator-adoption/task-p3-operator-adoption-sync.md|本報告逐byte副本，不hash自己|

補核：header兩條路由已指向既有durable review與operator-adoption同步報告；budget日期補記已原樣同步durable原件，原budget正文不改。report／text-diff／checks在operator-adoption保存逐byte副本，三份同目錄相對連結保持有效。archive v1七份再核SHA不變，manifest execution／runtime整物件不變，最終design反向diff仍回到受審3016d934候選。

下一步由root核對並同步主工作區／register／總計畫；本報告不代替root整合或任何付費授權。
