/* Generated from apps/api/contracts; do not edit. */

export interface MoveJdItemArguments {
  /**
   * read_jd 提供的既有 JD 項目定位；保留身分與來源，不以刪除重建模擬移動。
   */
  read_ref: string;
  destination: CurrentContainer | TaskParent;
  position: EdgePosition | RelativePosition;
  /**
   * 通常為空。只有任務換職責／未歸屬時，可同次修正該任務文字、明細及來源／目的職責 scope_text，或新增成果／要求；全部原子套用。不變更來源引用。
   */
  content_changes: (SetMovementText | ClearMovementText | AddMovementDetail)[];
}
export interface CurrentContainer {
  /**
   * 在目前容器同類項目中排序；成果／要求限同一任務、同一類。
   */
  kind: 'current_container';
}
export interface TaskParent {
  kind: 'task_parent';
  /**
   * 目的職責的 read_ref；null 表示未歸屬。只有任務可換容器。
   */
  parent_read_ref: string | null;
}
export interface EdgePosition {
  kind: 'first' | 'last';
}
export interface RelativePosition {
  kind: 'before' | 'after';
  /**
   * 目的容器中同類鄰項的 read_ref。不是數字 position，也不是任意其他區域。
   */
  neighbor_read_ref: string;
}
export interface SetMovementText {
  action: 'set_field';
  read_ref: string;
  /**
   * 移動任務 title/description；該任務明細 text；來源與目的職責 scope_text。
   */
  field: 'title' | 'description' | 'scope_text' | 'text';
  value: string;
}
export interface ClearMovementText {
  action: 'clear_field';
  read_ref: string;
  /**
   * 僅清空可空欄；任務／職責仍須有有意義內容。
   */
  field: 'title' | 'description' | 'scope_text';
}
export interface AddMovementDetail {
  action: 'add_detail';
  kind: 'outcome' | 'requirement';
  /**
   * 為本次移動任務新增的完整成果或要求；不改其他任務。
   */
  text: string;
}
