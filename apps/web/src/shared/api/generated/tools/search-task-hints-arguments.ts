/* Generated from apps/api/contracts; do not edit. */

/**
 * 只填 query；用於幫員工回想這類任務通常涉及的內容方向，不是認定員工職位或已完成的工作。
 */
export interface SearchTaskHintsArguments {
  /**
   * 以自然語言描述一項具體工作任務或職責片段，保留動作、對象與情境。只找任務層級的公版內容，不回傳也不綁定任何職位身分；必須有非空白內容，最多 12,000 字元。
   */
  query: string;
}
