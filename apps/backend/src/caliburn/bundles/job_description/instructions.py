"""JD 能力的使用目的；參數細節由各工具維護。"""

JD_INSTRUCTIONS = """JD 是正式職務內容。先以導覽辨識既有內容，按需讀取目標全文，
再根據已知工作事實作局部編修；保留未受影響內容、分類與共用 K/S。
短碼是項目的固定定位；正文提及的其他短碼不是可自動替換的文字。
一次成功工具呼叫已保存其效果；後續普通拒絕不撤銷先前成功修改。
工具回覆要求重讀時，先核對目前內容再決定修改，不猜測先前操作未保存。
引用隨其支持的內容保存。JD 讀回的 supporting_sources 是既有引用摘要，
用 read_jd 的 item 查 citation_ref 可讀來源原件；
Memory 來源變更用 read_jd_changes 比較。
新增引用的 supporting_sources 或 add_source 接已讀來源：
訪談將原話提供的 ref 填入 message_ref；
Memory 使用固定發布版已讀正文的類別與完整標題，導覽只供定位。
既有 Memory 引用摘要的 kind=memory 不是新增來源種類；新增時使用 memory_kind 對應的
work_situation 或 work_understanding，不複製整筆摘要回填。
共用 K/S 定義保留自身依據，並連到實際需要的任務；不因只用於單一任務或內容基礎而省略。
needs_recheck 表示需要核對支持關係，
核對後逐筆 confirm；來源已刪除時保留舊標題，不以同名新項目代替。
"""
