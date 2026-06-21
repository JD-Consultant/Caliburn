"use client";

// D27 seed 入口（T8 的一部分）：status=none 時顯示。搜尋職類 OCS → 複選（順序=
// 優先度）→ 建立骨架文件。純 REST：ocsSearch + seedDocument。
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ocsSearch } from "@/lib/api";
import { useSeedDocument } from "@/hooks/useDocument";
import type { OcsSearchHit } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search } from "lucide-react";

export function SeedPanel({
  profileId,
  defaultQuery,
  onError,
}: {
  profileId: string;
  defaultQuery: string;
  onError: (msg: string) => void;
}) {
  const [q, setQ] = useState(defaultQuery);
  const [hits, setHits] = useState<OcsSearchHit[]>([]);
  const [picked, setPicked] = useState<string[]>([]); // 有序：優先度

  const search = useMutation({
    mutationFn: () => ocsSearch(profileId, q),
    onSuccess: (r) => setHits(r.hits),
    onError: (e: unknown) => onError(e instanceof Error ? e.message : "搜尋失敗"),
  });
  const seed = useSeedDocument(profileId);

  const toggle = (code: string) =>
    setPicked((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );

  const runSeed = () => {
    if (picked.length === 0) return;
    seed.mutate(picked, {
      onError: (e: unknown) => onError(e instanceof Error ? e.message : "建立骨架失敗"),
    });
  };

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <div>
        <h2 className="text-base font-semibold">選擇職類（建立職務說明書骨架）</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          搜尋並複選對應職類，順序＝優先度。建立後會帶入任務骨架，再逐格填寫。
        </p>
      </div>

      <div className="flex gap-2">
        <input
          className="w-full rounded-lg border px-3 py-2 text-sm"
          placeholder="搜尋職類（例：AIoT 應用工程師）"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") search.mutate();
          }}
        />
        <Button onClick={() => search.mutate()} disabled={search.isPending || !q.trim()} className="gap-1">
          <Search className="h-4 w-4" />
          {search.isPending ? "搜尋中…" : "搜尋"}
        </Button>
      </div>

      {hits.length > 0 ? (
        <div className="space-y-1.5 rounded-lg border p-2">
          {hits.map((h) => {
            const order = picked.indexOf(h.ocs_code);
            return (
              <label
                key={h.ocs_code}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted/50"
              >
                <input
                  type="checkbox"
                  checked={order >= 0}
                  onChange={() => toggle(h.ocs_code)}
                />
                {order >= 0 ? (
                  <Badge variant="secondary" className="h-5 w-5 justify-center p-0 text-xs">
                    {order + 1}
                  </Badge>
                ) : null}
                <span className="flex-1">{h.job_title}</span>
                <span className="font-mono text-xs text-muted-foreground">{h.ocs_code}</span>
              </label>
            );
          })}
        </div>
      ) : search.isSuccess ? (
        <p className="text-sm text-muted-foreground">沒有結果，換個關鍵字試試。</p>
      ) : null}

      <Button onClick={runSeed} disabled={picked.length === 0 || seed.isPending}>
        {seed.isPending ? "建立中…" : `建立骨架（已選 ${picked.length} 個職類）`}
      </Button>
    </div>
  );
}
