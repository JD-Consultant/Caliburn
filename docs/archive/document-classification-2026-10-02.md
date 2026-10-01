# 文件分類與封存紀錄（2026-10-02）

## 範圍與結論

Owner 要求先研究分類，再整理 `docs`、封存不再使用的文件。整理基準為 `target-rebuild@b4157033dbfa0274cc1a5969eec1b26cd50e107e`。本次只改文件位置與閱讀入口，不改產品、Prompt、工具契約、資料庫、服務、驗收狀態或正式入口；沒有付費請求、merge 或 push。

**按用途分類，按證據判定是否封存。**研究與規格不能只靠檔名辨認；日期早、試驗結束或方案曾失敗，也不等於沒有保存價值。根入口與分類表見 [docs/README](../README.md)，本紀錄不另立產品規範。

## 研究與採用的範圍

查閱日：2026-10-02。

| 外部一手資料 | 可借鑑的原則 | 本次取捨 |
|---|---|---|
| [Diátaxis](https://diataxis.fr/) | 按讀者需求區分教學、操作、參考與解說，不強制技術實現 | 用讀者要完成的事組織入口；不把內部研究、ADR、實驗原件硬塞進四個資料夾 |
| [GitLab documentation topic types](https://docs.gitlab.com/development/documentation/topic_types/) | 區分概念、任務、參考、排錯；頂層導覽可集中提供連結 | 讓研究、指南、規格、操作、報告各有用途；用少量 README 導航，不複製正文 |
| [arc42](https://docs.arc42.org/home/) | 系統架構分元件、執行、部署、橫切概念、決策、品質與風險等視角 | 保留既有架構地圖與責任文件，不將架構、工程規則及實驗結果合成一份大文檔 |

上述來源支持分類思路，**不規定 Caliburn 必須採用此目錄樹**，也不能據此宣稱唯一最佳或所有大廠使用相同結構。具體歸檔仍依[既有架構討論規範](../architecture-discussion-standard.md)與[決策流程](../decision-process.md)。

## 實際整理

| 類別 | 動作與判定 |
|---|---|
| 55 份研究材料 | 由 `specs/` 移至 [research/](../research/README.md)：Agent／Context／Memory／評測 23 份、工作分析／訪談／JD 13 份、工程／文件／編輯互動 13 份、檢索／OCS 6 份；保留原題名與日期 |
| 8 份已失去當前入口用途的文件 | 移至 [retired-documents/](retired-documents/README.md)：5 份原文明示 Retired 的舊通知、09-15 工作樹進度地圖、2 份原文明示被取代的設計研究；不刪正文 |
| 指南與有效契約 | 新增 [guides/](../guides/README.md)、[specs/](../specs/README.md) 導讀。工作分析指南仍被 Prompt 內容權威註解及大量文件引用，維持路徑；工具共同規範雖名為 research，也留在原契約位置 |
| 計畫與證據 | 新增 [plans/](../plans/README.md) 接手入口；任務表仍為進度 owner，測試／事故仍在任務 evidence，原始資料不因分類搬動或複製 |
| 教授報告、實驗、歷史 | [reports/](../reports/README.md) 接到研究／指南；[experiments/](../experiments/README.md) 明確區分研究與實測；新增[封存總入口](README.md) |
| 相互引用 | 63 次搬移及受影響 Markdown 連結機械更新共涉及 150 份既有 Markdown；後續入口文案另列 Git diff。ADR 只調連結目的地，決策正文、ID、狀態不變；歷史命令與內嵌原始路徑不當成目前操作指令重寫 |

每個搬移的原路徑、新路徑、原因、來源提交、原工作檔與搬移後 SHA-256 均在[對照表](document-classification-2026-10-02.csv)。搬移後正文除 Markdown 導航外不變；工作檔行尾與 Git 正規化行尾可能不同，SHA-256 比較以表中工作檔位元組為準。

## 保全與驗證

- 搬移前確認 `target-rebuild` 乾淨；逐一檢查來源存在、目的地未存在且解析後位於 `S:/caliburn/docs/`，不搬出 repo、不覆蓋其他檔案。
- 既有封存與 `data/`、`cases/`、`trials/` 原件共 3,344 檔列入前後 SHA-256 比較；不重寫實驗數字、日誌、PDF、圖片或封存的原始材料。
- Markdown 搬移前後以相同範圍檢查相對檔案連結，再另檢查新增／重寫的分類入口與錨點；不把未檢查的歷史內容宣稱為已驗。
- 這是文件整理，不跑產品全套測試、不把文件連結通過當作產品驗收。

實際檢查結果如下；分類本身不改 T14–T18 的狀態。

| 檢查 | 結果 |
|---|---|
| 63 份搬移目的地、原位置與 manifest SHA-256 | 63 份存在於新位置，原位置已移出；雜湊不符 0 |
| 3,344 份既有封存／原件的前後 SHA-256 | 改變或遺失 0 |
| 同範圍 Markdown 相對檔案連結回歸 | 原有失效連結 350 → 350，新增失效 0；不包括凍結原件的內部連結 |
| 10 份分類／閱讀入口的檔案連結及錨點 | 失效 0；使用既有 `check_links.py` 核對 |
| 機械轉換後再次比對 150 份既有 Markdown | 只有 `current-decisions.md` 額外增加本次整理狀態；其餘與預先計算的「只改連結／位置」結果一致 |
| Git 空白與 patch 檢查 | `git diff --check` 通過；提交前再檢查 staged diff |

移轉用的一次性清單及核對腳本保留於本機 ignored `.research-tmp/docs-classification-2026-10-02/`，不作產品依賴，也不宣稱它們已遠端備份。可在 checkout 直接重跑入口檢查：

```powershell
py -3 .research-tmp/eval/tools/check_links.py docs/README.md docs/research/README.md docs/guides/README.md docs/specs/README.md docs/plans/README.md docs/archive/README.md docs/archive/retired-documents/README.md docs/archive/document-classification-2026-10-02.md docs/experiments/README.md docs/reports/README.md
git diff --check
```

該連結檢查 helper 同樣是既有本機工具；跨機器追溯不依賴它，來源提交、搬移清單與雜湊已保留於 repo。沒有刪除既有失敗紀錄來讓檢查變綠。

## 限制與後續

1. 初次掃描既有可維護 Markdown 得到 **350 處相對連結指向不存在檔案**，分散在不同年代文件，並非 350 個產品 bug。搬移只保持既有導航意義，不憑猜測把舊程式路徑接到新實作。這個數字不包含所有錨點問題，也不等於全 repo 的完整品質統計。
2. `specs/` 還有混合研究／契約及較早設計；未證明失效的先保留。入口已區分有效責任集合與沿革，不把剩餘舊文件全部冒稱有效或全部封存。
3. 既有歷史快照、原索引、原始輸出及其內部路徑不隨搬移更新；查現位置用對照表，查當時原件用對應 Git 提交／tag。這既保留證據，也避免把歷史命令誤寫成現在可執行的指令。
4. 整理沒有重新核對 55 篇研究內所有廠商/API/論文的有效性；後續選型仍須查當前官方契約。
5. 不動其他 worktree、分支、資料庫或憑證，也不因本地整理而宣稱已有遠端備份。

## 原件查回

對照表列出本批原始提交。要查看搬移前正文，可使用唯讀 Git 查詢（以單一文件為例）：

```powershell
git show b4157033dbfa0274cc1a5969eec1b26cd50e107e:docs/specs/2026-09-26-reasoning-tool-results-and-state-boundary-research.md
```

這只顯示歷史，不回退工作樹或復活舊規格。先前的 Repo／分支整理仍查[原紀錄](repository-organization-2026-10-02.md)與[工作樹歷史索引](worktree-history-index.md)。
