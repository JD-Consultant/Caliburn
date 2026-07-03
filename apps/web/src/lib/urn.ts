// 任務身分 URN(scheme 同 indexer api/urn.py):由 provenance 現組、不落庫(spec §2 三分:
// 身分存 provenance、顯示用位置碼、鍵用 URN 現組)。
// 自訂任務(無 provenance)回 ""(呼叫端據此停用 catalog query)。
export function taskUrn(p?: { ocs_code?: string; task_code?: string }): string {
  return p?.ocs_code && p?.task_code ? `ocs:${p.ocs_code}:T:${p.task_code}` : "";
}
