# Issue tracker：Local Markdown

本 repo 的 issue、spec 與 ticket 使用 `.scratch/` 下的 Markdown 檔案管理，不使用 GitHub Issues。

## 慣例

- 每個 feature 一個目錄：`.scratch/<feature-slug>/`。
- Spec 放在 `.scratch/<feature-slug>/spec.md`。
- Ticket 放在 `.scratch/<feature-slug>/issues/<NN>-<slug>.md`；每個 ticket 獨立成檔，從 `01` 編號。
- Ticket 靠近檔案開頭使用 `Status:` 記錄 triage 狀態。
- Ticket 靠近檔案開頭使用 `Blocked by: NN, NN` 記錄依賴；所有 blocker 都 resolved 才算解除阻擋。
- 討論與歷程附加在檔案末尾的 `## Comments`。

## Skill 對應

- 「publish to the issue tracker」：在 `.scratch/<feature-slug>/` 建立對應 Markdown 檔案。
- 「fetch the relevant ticket」：讀取使用者指定的 ticket 路徑或編號。
- Wayfinder map 放在 `.scratch/<effort>/map.md`；child tickets 放在
  `.scratch/<effort>/issues/<NN>-<slug>.md`。
- Claim ticket 時先將 `Status:` 設為 `claimed`；完成後補上 `## Answer`，再設為 `resolved`。
