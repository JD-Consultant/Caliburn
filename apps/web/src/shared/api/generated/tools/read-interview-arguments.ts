/* Generated from apps/api/contracts; do not edit. */

/**
 * 按正式訪談序號選取歷史訊息。只填 query；職務、來源資格與可讀上界由 App 綁定。
 */
export interface ReadInterviewArguments {
  /**
   * 選一種查詢：kind=messages 讀明列的 sequences；kind=range 讀 start_sequence 到 end_sequence 的全部訊息，包含兩端。使用已提供的正式訪談序號，不填內部 ID 或執行回合。
   */
  query: InterviewMessagesQuery | InterviewRangeQuery;
}
export interface InterviewMessagesQuery {
  /**
   * 固定填 messages，表示只取 sequences 列出的訊息，不自動加入中間或前後發話。
   */
  kind: 'messages';
  /**
   * 至少一個正式訪談正整數序號，可不連續、可重複；工具去重後依序號遞增回傳，保留原序號。任一序號不在可讀範圍或無法取得時整筆拒絕；序號之間有空隙不表示沒有其他發話。
   *
   * @minItems 1
   */
  sequences: [number, ...number[]];
}
export interface InterviewRangeQuery {
  /**
   * 固定填 range，表示讀取 start_sequence 至 end_sequence 的連續範圍，包含兩端。
   */
  kind: 'range';
  /**
   * 第一個要讀的正式訪談序號，正整數且不得大於 end_sequence。須在 App 允許的歷史範圍內。
   */
  start_sequence: number;
  /**
   * 最後一個要讀的正式訪談序號，正整數且不得超過 App 為目前執行綁定的歷史上界。工具回傳含兩端的完整範圍；不合法、缺失或超量時拒絕，不靜默縮短。
   */
  end_sequence: number;
}
