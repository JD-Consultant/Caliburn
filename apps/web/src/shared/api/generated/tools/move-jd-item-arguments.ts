/* Generated from apps/api/contracts; do not edit. */

export interface MoveJdItemArguments {
  /**
   * 要移動或排序的既有項目定位，可選職責、任務、成果／要求、知識／技能、協作或共通條件。原樣使用目前仍有效的 jd_map、read_jd 或成功建立回傳提供的 read_ref，不依名稱或序號自行組出。
   */
  read_ref: string;
  /**
   * current_container 在目前同類集合排序：成果／要求限同任務同類，知識／技能分開，共通條件限同 condition_kind；task_parent 只供任務選目的職責或 null（未歸屬）。
   */
  destination: CurrentContainer | TaskParent;
  /**
   * 在目的集合中的位置；first／last 放首尾，before／after 使用同一目的集合的同類鄰項定位。
   */
  position: EdgePosition | RelativePosition;
  /**
   * 任務實際更換職責／未歸屬時，可同次修訂該任務文字、既有成果／要求正文、原職責與目的職責的 scope_text，或新增該任務成果／要求。沒有伴隨修訂或只是排序時填 []。不接受來源變更、能力關係或明細刪除；每個文字欄位只改一次。實改的支持內容同步更新 JD 核對基準，Memory 來源版本仍由引用動作更新。
   */
  content_changes: (SetMovementText | ClearMovementText | AddMovementDetail)[];
}
export interface CurrentContainer {
  /**
   * 固定為 current_container，保留目前歸屬，在目前同類集合排序；任務限目前職責或未歸屬集合，成果／要求限同一任務同類。
   */
  kind: 'current_container';
}
export interface TaskParent {
  /**
   * 固定為 task_parent，只適用任務；以 parent_read_ref 選目的歸屬。
   */
  kind: 'task_parent';
  /**
   * 目的職責的既有 read_ref，null 表示移到未歸屬集合。原樣使用目前仍有效的 jd_map、read_jd 或成功建立回傳提供的 read_ref，不依名稱或序號自行組出。
   */
  parent_read_ref: string | null;
}
export interface EdgePosition {
  /**
   * first 放到目的集合最前，last 放到最後；不需提供鄰項。
   */
  kind: 'first' | 'last';
}
export interface RelativePosition {
  /**
   * before 放到 neighbor_read_ref 指向的鄰項之前，after 放到其後。
   */
  kind: 'before' | 'after';
  /**
   * 目的集合中同類鄰項的 read_ref，取自目前仍有效的 JD 導覽或讀取結果；任務選目的職責／未歸屬內任務，明細選同任務同類明細，共通條件選同分類。
   */
  neighbor_read_ref: string;
}
export interface SetMovementText {
  /**
   * set_field：隨任務更換歸屬，以完整新文字取代一個允許的相關欄位。
   */
  action: 'set_field';
  /**
   * 要伴隨修訂的對象：被移動任務、該任務的既有成果／要求，或其原／目的職責。原樣使用已提供且仍有效的定位。
   */
  read_ref: string;
  /**
   * 被移動任務可改 title（名稱）或 description（正文）；其成果／要求可改 text；原／目的職責只可改 scope_text（範圍）。
   */
  field: 'title' | 'description' | 'scope_text' | 'text';
  /**
   * 此欄完整的新文字，須含非空白內容且不含 NUL；不填 patch，既有引用集合與固定來源版本保留。
   */
  value: string;
}
export interface ClearMovementText {
  /**
   * clear_field：隨任務更換歸屬，把一個允許的相關可空欄位設為 null。
   */
  action: 'clear_field';
  /**
   * 被移動任務，或其原／目的職責的既有定位；成果／要求正文不可清空。
   */
  read_ref: string;
  /**
   * 被移動任務可清 title 或 description，但至少留一欄有內容；原／目的職責只可清 scope_text，且須仍有 title。
   */
  field: 'title' | 'description' | 'scope_text';
}
export interface AddMovementDetail {
  /**
   * add_detail：隨任務更換歸屬，為該任務新增一筆成果或要求。
   */
  action: 'add_detail';
  /**
   * outcome＝形成、交付或維持的結果與用途；requirement＝執行或完成時的品質、時限、條件與判準。
   */
  kind: 'outcome' | 'requirement';
  /**
   * 新增至被移動任務的完整成果／要求正文，須有非空白文字；與該任務共用來源，不改其他任務。
   */
  text: string;
}
