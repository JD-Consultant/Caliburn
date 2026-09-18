# 已驗收編輯核心：後續測試與採用輸入

2026-09-12。核心 `54cdfb34`／tag `jd-editor-core-isolated-20260910`；主產品對照 `638ed877e85be3da4c5fd6d1f263b2efc204d1d8`。

[baseline.json](baseline.json)固定 **84項Git原始輸入**，含既有顧問／Memory、JD工具、Skill、SSOT與生成物、native adapter、Web及lock／授權清單。檔案由已接受commit讀取，不取工作區未提交研究；[逐檔再核對](verification.json)全部一致。沒有複製到production或安裝套件。

Python正式與隔離lock有 **92項名稱／版本差異**，宣告、Python要求與Web依賴差異列在同檔。差異清單不是合併後可安裝證據：正式依賴仍需A1/A2核對，不能直接用隔離lock覆蓋正式API。這是已接受版本的本地事實，不是最新版本推薦或供應商共識。

這份輸入接續9/10的Task4預覽；原件保留沿革。本份已涵蓋Task5、Task6與整體修正，**不代表A1完整採用manifest、P3 OFF01全部完成或G6已通過**。工具／Skill／格式hash可用作後續凍結起點，實際trial的endpoint／完整配置、預算防護、案例與費用授權仍待具體執行包。P3-B01公開計費上界缺口仍OPEN；未發模型請求。

正式HTTP／composition映射沿已採設計A2完成，不把這份responsibility欄位當新架構裁決。舊writers退役仍依原採用盤點；沒有刪除任何正式入口。
