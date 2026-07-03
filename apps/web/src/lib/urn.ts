// 任務身分 URN(scheme 同 indexer api/urn.py):由 provenance 現組、不落庫(spec §2 三分:
// 身分存 provenance、顯示用位置碼、鍵用 URN 現組)。
// 自訂任務(無 provenance)回 ""(呼叫端據此停用 catalog query)。
export function taskUrn(p?: { ocs_code?: string; task_code?: string }): string {
  return p?.ocs_code && p?.task_code ? `ocs:${p.ocs_code}:T:${p.task_code}` : "";
}

// 任務的全部身分 URN:合併列選入的任務 _refs 多筆;舊資料/單來源 fallback provenance。
export function taskUrns(task: {
  provenance?: { ocs_code?: string; task_code?: string };
  _refs?: { ocs_code: string; task_code?: string }[];
}): string[] {
  const refs = task._refs?.length ? task._refs : task.provenance ? [task.provenance] : [];
  const out: string[] = [];
  for (const r of refs) {
    const u = taskUrn({ ocs_code: r.ocs_code, task_code: r.task_code });
    if (u && !out.includes(u)) out.push(u);
  }
  return out;
}
