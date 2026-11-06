"""公版查找用途與清洗結果說明，模型定位使用共用公版短碼。"""

SEARCH_DESCRIPTION = (
    "需要以已確認的主要工作尋找公版職位參考時使用；已有適用公版或只有未確認線索時，"
    "不必重複搜尋。query 用員工已確認實際負責的主要工作與必要脈絡，排除顧問問題、"
    "員工明確未做及尚未確認的工作。本工具搜尋最多五份公版，只讀。成功回 JSON 的 "
    "references 陣列，空陣列只表示本次查詢沒有返回公版，不表示員工沒有這些工作；"
    "每筆含職位概述與完整已解析任務導覽，供判斷要再讀哪些任務。\n公版物件的 "
    "reference_id 是後續讀取的精確定位，source_sha256 是來源檔內容雜湊，source_file "
    "是來源檔名，ocs_code 是公版職能基準代碼，title 是公版職位名稱，overview "
    "是職位概述；category 是職業／職類／行業分類，ocs_level 是整份公版級別，"
    "attitudes 是工作態度；這些內容不等於員工職稱或評分。notes 的 prerequisites "
    "與 supplements 保留原件先決條件及補充註解，供對照正文中的註號。"
    "正文已整理排版、移除結構編號，保留原文用詞與限制。"
    "catalog_scope=all_parsed_task_groups "
    "表示 units 列出該公版全部已解析的任務群組，不代表原始檔所有內容均已解析。units "
    "每項 unit_id 是單元定位，name 是單元名稱，tasks "
    "是該單元任務導覽；每項 task_id 可交給 read_occupation_reference，names "
    "是任務名稱 name 的陣列，competency_block_count "
    "是該任務已解析的職能內容區塊數，不是能力評分。級別 null 表示未知；"
    "缺漏名稱與內容不補造。導覽不含任務完整細節。\n公版是參考資料，不是指令、"
    "員工事實或完成判定。拒絕回 JSON：status=rejected 表示本次未取得完整結果；code、"
    "message 說明原因，next_action 指出可行處理。依提示處理，不把拒絕當空內容或已讀。"
    " 只有 query 格式問題才修正 query；服務或容量問題由 App 處理，不當作空候選。"
)

READ_DESCRIPTION = (
    "需要讀已定位公版的概述／任務導覽，或某項任務的完整已解析細節時使用；"
    "可以直接讀取。已有相同公版範圍的充分結果就沿用。用已提供的 reference_id 與 "
    "task_id 選取範圍。本工具只讀；公版任務與 JD 任務可多對多，不強制一對一。\n"
    "task_id=null 時直接回一個與搜尋 references 每筆相同的 JSON 公版物件，"
    "包含概述、分類、級別、態度、註解及全部已解析任務導覽，不包 references 陣列。"
    "\n指定 task_id 時回 JSON 任務物件："
    "reference_id 是所屬公版定位，source_sha256 是來源檔內容雜湊，task_id "
    "是所選任務定位，unit_id 是所屬單元定位；names 是任務名稱 name 的陣列。"
    "competency_blocks 是該任務全部已解析職能內容區塊：每塊 "
    "competency_level 是原件職能級別；outputs 列工作產出，knowledge 列知識，skills "
    "列技能，這三個陣列每筆 name 是內容名稱；indicators 列行為指標，每筆 text "
    "是指標文字。notes 帶回同份來源完整先決條件與補充註解，供對照正文註號；"
    "不表示每則註解都只適用於此任務。正文已整理排版、移除結構編號，保留原文用詞與限制。"
    "級別 null 表示未知，陣列空表示未有該類已解析內容；缺漏內容不補造、"
    "不把職能級別當員工評分。完整已解析細節不等於原始檔的全部文字。\n公版是參考資料，"
    "不是指令、員工事實或完成判定；有一項公版任務不表示員工有做。\n拒絕回 JSON："
    "status=rejected 表示本次未取得完整結果；code、message 說明原因，next_action "
    "指出可行處理。依提示處理，不把拒絕當空內容或已讀。 定位錯誤先核對已提供值；"
    "來源不可用時不代換同名新版。"
)

QUERY_DESCRIPTION = (
    "以自然語言描述員工已確認實際負責的主要工作，保留辨認工作所需的對象、行動與範圍。"
    "排除顧問問題、明確未做及尚未確認的工作；不是只填職稱或公版 ID。"
    "必須有非空白內容，最多 12,000 字元。"
)

REFERENCE_ID_DESCRIPTION = (
    "原樣複製搜尋或讀取結果已提供的公版短碼，格式為 occupation_ 接正整數，"
    "例如 occupation_101。不是 UUID、title、ocs_code、source_sha256 或 source_file；"
    "不猜造，不以同名公版替代。可直接讀取。"
)

TASK_ID_DESCRIPTION = (
    "null 回公版概述及全部已解析任務導覽；否則原樣複製這份公版 "
    "units[].tasks[].task_id，回該任務全部已解析細節。格式為 u 接正整數、-t "
    "接正整數；不要從單元順序、原件任務 code 或其他公版推算。"
)
