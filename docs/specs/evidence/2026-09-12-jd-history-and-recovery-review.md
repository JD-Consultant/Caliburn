# JD 歷史與恢復：文件審查紀錄

- 日期：2026-09-12；Topic：JD-R002；本輪只做需求裁決、官方研究與文件審查。
- 主要稿：[歷史／還原／重開](../2026-09-12-jd-history-and-recovery-design.md)、[工作區裁決 §7](../2026-09-12-jd-agent-workspace-necessity-research.md#7-owner-澄清後的裁決第一版不設持久-ai-試稿區)。
- 狀態：**兩份独立唯讀文件審查 PASS**；無 runtime／DB／瀏覽器／自然模型驗收。整體 G4 尚未通過。

## 1. 基準與初步核對

Owner 已選不設待整理區、歷史對照／局部更正／整份還原、不加最近一步撤回。工作區目的已澄清為先試改穩定再提供；研究者受權裁決 WS-01 第一版先不設持久試稿分支，有明確多輪候選用途或實證缺口再重開。

`jd_command_semantics_review` 獨立核 Microsoft／Google 產品及 AWS／PG 官方恢復原則；root 另核 Codex worktrees、Claude checkpoints、Google、Microsoft 版本歷史、AWS 與 PG。Microsoft「without unwanted changes」頁在 root 讀取失敗、Google `hl=en` 一次 timeout；root 改讀同官方版本歷史頁及 Google `hl=en-10` 正文，沒有依失敗頁推定功能或無限重試。

`jd_storage_audit` 初步核對既有文件：未承諾所有未保存按鍵可恢復，A 固定請求與 B 後續輸入已有分界，JR-R02／03 不需重開；指出整份還原應形成新修訂、來源不可讀與原 basis 的分界、切文件出口需補。root 已納入新稿與原 schema／tools／autosave／整體設計，未把建議直接當實作完成。

## 2. 獨立審查與複核

| Reviewer／範圍 | 結果 |
|---|---|
| `jd_storage_audit`：新稿與 schema §3.10／4／6.4、tools §8–9、autosave 接點 | PASS；九組 current 表有界重建、parent=current、來源沿用／receipt、A／B 與切頁、通知基準無阻擋性矛盾。不重開 JR-R02／03 |
| `jd_command_semantics_review`：新稿、workspace §7、需求 §10–11 及重審狀態 | PASS；三種取消／更正／還原分清、沒有未授權最近一步或通用逆運算；WS-01 未混淆多輪試稿與 App 單次候選，官方事實與本案映射分開 |

唯一非阻擋措辭建議：tools 原稱整份還原「亦產生新的 manual event」，root 核對 no_change 後加上「有實際變更時」及 no_change 只留操作結果，已處理。root 另將 schema 原 catalog `restore` 用語明定為 `unarchive`，與新 `restore_revision` 分開；原鎖與 admission 機制未改。未出現需進修正輪的阻擋 finding。

## 3. 驗證範圍

本輪初次靜態核對為 11 份文件、140 個本地連結、46 個 anchors，0 問題；補齊路由後最後為 **11 份文件、142 個本地連結、47 個 anchors，0 問題**。差異空白檢查通過，LF／CRLF 提示不算功能測試。HR-01–12 均是後續可證偽情境，沒有執行模型、寫入 DB、操作瀏覽器或證明自然訪談品質。整體 G4 Needs revision、ADR0075 Proposed／production0060 不變。
