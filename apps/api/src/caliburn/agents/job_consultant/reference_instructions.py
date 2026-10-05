"""Optional guidance appended only to newly reference-enabled consultant requests."""

OCCUPATION_REFERENCE_INSTRUCTIONS = """

公版職位參考
已有員工主要工作的整體理解，卻仍不確定是否可以收尾時，才按需查公版參考。
先讀 read_occupation_reference_state，沿已選公版按需讀概述、任務導覽或細節；
需要補找代表性職位時，搜尋文字只放員工已確認實際負責的主要工作和必要脈絡，
不要混入顧問問題、否認工作、未知或整份排除清單。
可選多份公版共同涵蓋主要工作；公版只提供線索，不認定員工職稱，也不要求任務一對一。
select_occupation_references 取代全部選用集合；要保留的舊 ID 一起填，不是追加。
寫入成功只回 updated，表示本輪候選成立；需要完整 state 時再按需讀，已有足夠有效內容就沿用。
員工明確表示沒做或不負責時，必要時讀目前 state，再以實際工作範圍更新 excluded_work，
避免重問；更正時用已有範圍的精確文字移除。未知、沒回答或拒答不算否認。
排除範圍可在訪談中維護，不必等到查公版或收尾。
公版已查閱、已選取或某項被排除，都不代表任務或整份職務說明書已完成。
""".strip()
