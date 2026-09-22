# 0067. Deep Agents Store-backed JD working draft

- **狀態**：Accepted
- **日期**：2026-08-22
- **Owner 對齊**：owner 於 2026-08-22 核准把持久 JD working draft 從 `StateBackend` 修正為 `StoreBackend`；產品效果與其餘 ADR 0066 決策不變
- **研究**：[`2026-08-22-persistent-ai-jd-working-draft-and-semantic-review-research.md`](../specs/2026-08-22-persistent-ai-jd-working-draft-and-semantic-review-research.md)
- **Supersedes**：ADR 0066 決定 2 對 `/workspace` 使用 `StateBackend`／同一 files state channel 的指定，以及 Consequences 中「不先採 DeltaChannel」的實作假設
- **保留**：ADR 0066 的一份 JD 一個非權威 working draft、五個 namespace、六個低階 Tool、自動驗證、derived semantic review、部分決策、stale／rebase、精簡 final、按需 context、no-RAG／no-auto／no-Git 與切片回歸；ADR 0060–0065 未被 0066 取代的全部邊界

## Context

ADR 0066 正確選擇 Deep Agents VFS 與 LangGraph persistence，但把持久 `/workspace` 指定為 `StateBackend`。施工前映射 pinned Deep Agents 0.7.5 與最新官方文件後，發現這個 primitive 選得不夠精確：

- `StateBackend` 把 files 放在當前 agent thread 的 LangGraph state，透過 checkpointer 跨同一 thread 的 turns 保存；官方主要定位為 agent scratch pad，且在 graph 外直接呼叫 backend 不會立即形成 state update。
- pinned `FilesystemState.files` 已使用 LangGraph `DeltaChannel`；因此 ADR 0066 所說「先不採 DeltaChannel」並不是使用現行 `StateBackend` 時可成立的選項。
- Caliburn 的員工 review／direct-edit API 也必須讀寫同一份 workspace，以完成 accept後重基線、reject撤回、defer保留與approved direct edit rebase。若堅持 `StateBackend`，需額外建立可在agent外安全操作其checkpoint channel的state graph bridge，增加同步、恢復與拓撲耦合。
- Deep Agents `StoreBackend` 是同一套成熟 VFS 的官方內建 backend，直接使用 LangGraph `BaseStore`，官方定位就是跨thread／跨execution的durable files，並特別適合已配置Postgres Store的系統。傳入明確store與固定namespace後，application command也能在graph外操作同一份virtual workspace。

本修正不是把 workspace 變成核准文件，也不是自建另一套資料庫。PostgreSQL Store已是ADR 0060核准的framework persistence；只是讓跨回合草稿放到其正確的Deep Agents backend，而對話、interrupt、run recovery與attempt checkpoints仍留在LangGraph Saver。

## Decision

1. **`/workspace` 改由 Deep Agents `StoreBackend` 持久化。** 每份JD使用固定namespace `("caliburn", "consultant", <document_id>, "workspace")`，並傳入production `AsyncPostgresStore`。`CompositeBackend`把`/workspace/` route到application policy wrapper包住的`StoreBackend`；不得改用host filesystem、另一張application-owned workspace table或自寫filesystem implementation。

2. **LangGraph Saver與Store各做其擅長工作。** Saver／checkpointer保存agent messages、middleware state、interrupt、run receipt與故障恢復；StoreBackend保存可由AI與employee command共同操作的canonical workspace resources。employee sources、correction lineage與decision memory繼續使用各自document-scoped Store namespaces。核准JD仍只在authority graph checkpoint，export不讀workspace Store。

3. **application只新增最薄workspace metadata，不複製文件。** 一個不暴露給模型的manifest保存`generation`、canonical file digest、approved baseline revision、validation status與diagnostics。每次讀取都以實際Store files重算digest；manifest不匹配時視為unvalidated／stale並重新驗證，不信任manifest冒充after-state。metadata使用同一LangGraph Store的獨立namespace，不建立資料表。

4. **工作草稿允許暫時invalid，審核仍fail closed。** StoreBackend的每個write／edit／delete立即持久；mutation wave後由middleware驗證完整after-state並更新manifest。若process在file write與validation之間中斷，下一次model／snapshot／employee command以digest mismatch偵測並重新驗證。只有manifest與實際files完全相符且status為valid時才產生review groups。

5. **employee authority採approved-first可恢復順序。** accept／edit-accept先在document lock內重驗approved revision、workspace generation／digest與group digest，再提交核准JD與command receipt；之後把workspace依新approved重基線。若在checkpoint成功、workspace rebase前中斷，reopen／exact replay依command receipt與baseline mismatch確定性完成rebase。不得先刪workspace差異再嘗試提交approved。reject／defer同樣以idempotent decision record與workspace digest防止套到不同內容。

6. **同document的model mutation與employee command必須序列化。** 第一版本機單一操作者沿用runtime document lock／active-run guard：employee review或direct edit不得與尚在執行的workspace mutation交錯。不同resource的同一model tool wave仍可由framework平行執行；wave完成後只做一次完整驗證。未來若要多process／多人同時編輯，必須另開ADR加入真正CAS／lease，不以本機process lock假裝完成。

7. **不因改用StoreBackend擴張context。** 模型仍透過`ls／read_file／grep`按焦點讀取workspace；Store內完整files不自動注入prompt。`write_file／edit_file／delete`與readonly routes仍受同一path／permission policy，Tool surface維持六個。

## Consequences

- 關閉、重啟、provider失敗或下一個員工turn後，AI與employee review API都能取得同一份workspace，不需重播patch或跨graph操縱`StateBackend` channel。
- Deep Agents `StoreBackend`直接承接file CRUD、namespace與Postgres persistence；Caliburn只保留path policy、manifest驗證、JD semantic diff與authority recovery。
- Workspace files不再享有Saver每個agent step的time-travel checkpoint；第一版本來就不提供版本歷史／rewind UI。員工需要的是目前active draft與精確semantic review，不是workspace branch history。
- Store file write與authority checkpoint不是同一資料庫transaction；approved-first、digest mismatch、command receipt與deterministic rebase形成source-first式可恢復seam，必須有crash-window測試。
- 不再需要為持久草稿引入或自寫DeltaChannel bridge；pinned framework的agent state仍可在內部使用自己的channels，但它們不再是JD workspace truth。

## Rejected alternatives

- **維持StateBackend並讓review API直接改checkpoint internals**：耦合LangGraph channel／checkpoint topology，需額外bridge且不符合framework public backend分工。
- **同時把workspace複製到StateBackend與StoreBackend**：形成兩份after-state與同步問題，違反單一active workspace。
- **把每個低階patch另存成事件流再重播**：重新製造自寫document store；semantic diff只作derived review，不作workspace truth。
- **以host files或Git保存草稿**：不適合本機Web API的資料與安全邊界，也不是owner所說VS Code概念類比的要求。
- **因StoreBackend跨thread就增加多workspace／branch**：primitive能力不等於產品需求；第一版仍只有一個document-scoped namespace。

## Sources

- [Deep Agents — Backends](https://docs.langchain.com/oss/python/deepagents/backends)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- pinned Deep Agents 0.7.5 `StateBackend`／`StoreBackend`／`FilesystemState` public implementation與signatures（2026-08-22本機characterization）
