/* Generated from apps/api/contracts; do not edit. */

/**
 * 只提交 query，指定目前 JD 中一筆引用的來源差異；不接受職務、版本或舊正文選取參數。
 */
export interface ReadJdChangesArguments {
  query: SourceQuery;
}
/**
 * 唯一支援的查詢為 kind=source 加 citation_ref，比較該 JD Memory 引用所固定的舊來源與本輪固定版本的同一物件。
 */
export interface SourceQuery {
  /**
   * 固定填 source，表示查所選引用的 Memory 來源差異，不是人工 JD 修改差異。
   */
  kind: 'source';
  /**
   * 原樣複製目前 read_jd 局部 supporting_sources 中 kind=work_situation 或 work_understanding 的 citation_ref；它定位既有引用，不是來源標題、JD read_ref、版本 ID 或人工差異中已刪引用的歷史定位。kind=interview 的引用不適用此工具。
   */
  citation_ref: string;
}
