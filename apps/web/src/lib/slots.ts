// 11 細項槽標籤(鏡像 apps/api app/interview/slots.py 的 SLOT_DEFS;改那邊要同步這邊)。
// T8 起從 reviewMap.ts 移入(reviewMap 資料流退役、檔案 T12 刪)。
export const DETAIL_SLOT_LABELS: Record<string, string> = {
  frequency: "頻率", time_share_pct: "工作比重", duration: "單次耗時",
  volume: "數量批次", trigger: "觸發條件", inputs: "準備材料", tools: "工具系統",
  collaborators: "協作對象", wait_points: "等待瓶頸", exceptions: "例外處理",
  standards: "完成標準",
};

// 表頭 pending 槽標籤(ocs_profile._pending 的鍵;ADR 0030)
export const HEADER_SLOT_LABELS: Record<string, string> = {
  ocs_code: "主要職能基準", job_description: "工作描述", ocs_level: "基準級別",
};
