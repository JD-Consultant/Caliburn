# 從 JD 的來源標記讀回自己說過的話

日期：2026-09-14；Topic：JD-R002；[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md) 第 4 項的「來源」。隔離 App，ADR0075 Proposed／production ADR0060 不變。零 provider。

承接[來源標記](2026-09-13-jd-app-open-issues.md)（OI-02 的 2026-09-14 局部）：畫面已經會說「依據你說過的 N 段訪談」，但點不開。這一單位讓它點得開。

## 1. 要完成的效果

員工看到 JD 上某一段，想知道「我當初到底說了什麼」，可以直接把那次訪談的原話叫出來對照——**是自己的話，不是 AI 的轉述**。AI 在那次說的話也一併標明角色列出，但不會被當成員工事實。

## 2. 範圍

| 做 | 不做 |
|---|---|
| 一條唯讀 HTTP 路由，把既有 `ConversationSourceService.read()` 的結果投影出來 | 不新增第二個 source owner、cursor、parser 或原話資料表 |
| 依契約 SSOT 生成輸入／輸出型別，不手改生成檔 | 不改 `jd_source_link`、不改任何 domain 或保存流程 |
| 畫面上由來源標記點開，逐則標示角色與原文 | 不做跨文件、跨資料集或「所有歷史」檢索；不做較早來源的搜尋 |

## 3. 先寫的反例

- 別的文件的 `source_ref` 必須被拒（`invalid_ref`），不得讀出任何訊息。
- 已無法取得的來源回明確代碼（`source_not_available`），不得回空陣列冒充「沒有原話」。
- 亂造或被竄改的 token 被拒，錯誤不含 token 內容。
- 這條路由**不寫入**：呼叫前後 JD head、revision 數與 operation 數完全不變。
- 回傳逐則帶 `role`；`assistant` 的內容不得被標成員工說的話。
- 路由與其他唯讀查詢共用同一組安全標頭與錯誤格式，不另立一套。

## 4. 依據

| 依據（查閱 2026-09-14） | 官方事實與本案使用範圍 |
|---|---|
| [契約策略](../contract-strategy.md) | 新公開格式由 SSOT 生成，不手改生成檔；本單位依此新增輸入／輸出型別並跑 `--check`。 |

沒有新增相依，沒有引入新框架。

## 5. 實作結果（2026-09-14）

| 交付 | 位置 |
|---|---|
| 唯讀路由 `POST /api/documents/{id}/jd/sources/read` | [query_api.py](../../experiments/jd-relational-app/src/jd_relational/query_api.py) |
| 投影服務（包既有 source owner，沒有第二個擁有者） | [source_reads.py](../../experiments/jd-relational-app/src/jd_relational/source_reads.py) |
| 契約型別（由 SSOT 生成，`--check` 相符） | `contracts/jd-read.schema.json` 的 `SourceReadInput`／`SourceMessageRecord`／`SourceReadPage` |
| 畫面：來源標記旁的「看第 N 段原話」與逐則標示角色的對話框 | [JdEditor.tsx](../../experiments/jd-relational-app/web/src/components/JdEditor.tsx)、[DocumentWorkspace.tsx](../../experiments/jd-relational-app/web/src/components/DocumentWorkspace.tsx) |

**實際行為：**別的文件的引用回 `invalid_ref`（422）；來源真的不在了回 `target_missing`（404）而不是空陣列——空陣列會被讀成「你從來沒說過」；不合格的請求連 source owner 都不會碰到；未預期的失敗只留 `read_failed`，錯誤訊息不含連線字串。沒有裝 source owner 的組裝（例如純查詢探針）拒絕作答，不編造。畫面只在拿得到 handler 時才顯示「看第 N 段原話」，不透明 token 永遠不出現在畫面上；對話框底下明說顧問的回覆是當時的整理用語、不是員工確認過的事實。

**驗證：**服務層 12 項、HTTP 層 6 項、Web client 3 項、畫面 1 項，全部通過；全組真 PG **3248 passed**（只剩既有 OI-05 缺陷）、Web **305 passed**、`tsc`／build／`generate_contract --check` 通過。變異驗證：拿掉「回傳的 source_ref 必須是問的那一個」，對應反例立刻失敗（改動後以 `git hash-object` 確認還原）。

**真瀏覽器（2026-09-14 補）：**固定離線訪談腳本改成引用 App 當輪發給它的來源後，[整輪撤回旅程](evidence/2026-09-14-jd-restore-and-undo-browser-results.md)在真 Chrome 上走完：AI 寫完後 JD 顯示「依據你說過的 1 段訪談。」、四個項目各有一顆「看第 1 段原話」，按下去看到**員工原話一字不差**，顧問當時的回覆另行標示並註明不是員工確認過的事實；那一輪的改動清單也多出四筆「加入引用 · 「…」的依據」。撤回之後 `jd_source_link` 回到 0 筆，因為來源隨那一輪的項目一起被取回。

**限制：**只走過一條成功路徑；來源讀不到、引用失效或對話框開啟中途斷線都沒有在瀏覽器驗過。較早來源的檢索（不是由標記點進去，而是主動找某段訪談）仍未做。
