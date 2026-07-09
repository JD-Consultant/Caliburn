"use client";

// D27〔選職類〕modal：搜尋 + 複選 OCS（順序=優先度）→ setOccupations。
// 0028 D1:訪談引擎可程式化開啟(autoSearch=true 掛載即搜)——同一元件、入口不同。
import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ocsSearch } from "@/lib/api";
import { useSetOccupations } from "@/hooks/useDocument";
import type { OcsSearchHit } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, X } from "lucide-react";

export function OccupationPicker({
  profileId,
  defaultQuery,
  autoSearch = false,
  onClose,
  onError,
}: {
  profileId: string;
  defaultQuery: string;
  autoSearch?: boolean;
  onClose: () => void;
  onError: (msg: string) => void;
}) {
  const [q, setQ] = useState(defaultQuery);
  const [hits, setHits] = useState<OcsSearchHit[]>([]);
  const [picked, setPicked] = useState<string[]>([]);

  const search = useMutation({
    mutationFn: () => ocsSearch(q), // 根層全域目錄搜尋，不吃 profileId（ADR 0019）
    onSuccess: (r) => setHits(r.occupations),
    onError: (e: unknown) => onError(e instanceof Error ? e.message : "搜尋失敗"),
  });
  const setOcc = useSetOccupations(profileId);

  // AI 開窗即帶查(0028):顧問剛用這個 query 搜過職類 → 開窗直接出結果
  const autoRan = useRef(false);
  useEffect(() => {
    if (autoSearch && !autoRan.current && q.trim()) {
      autoRan.current = true;
      search.mutate();
    }
  }, [autoSearch, q, search]);

  const toggle = (code: string) =>
    setPicked((p) => (p.includes(code) ? p.filter((c) => c !== code) : [...p, code]));

  const confirm = () => {
    if (picked.length === 0) return;
    setOcc.mutate(picked, {
      onSuccess: onClose,
      onError: (e: unknown) => onError(e instanceof Error ? e.message : "設定職類失敗"),
    });
  };

  return (
    <Modal title="選擇職類（順序＝優先度）" onClose={onClose}>
      <div className="flex gap-2">
        <input
          className="w-full rounded-lg border px-3 py-2 text-sm"
          placeholder="搜尋職類（例：AIoT 應用工程師）"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search.mutate()}
          autoFocus
        />
        <Button onClick={() => search.mutate()} disabled={search.isPending || !q.trim()} className="gap-1">
          <Search className="h-4 w-4" />
          {search.isPending ? "搜尋中…" : "搜尋"}
        </Button>
      </div>

      {hits.length > 0 ? (
        <div className="mt-3 max-h-72 space-y-1 overflow-y-auto rounded-lg border p-2">
          {hits.map((h) => {
            const order = picked.indexOf(h.ocs_code);
            return (
              <label
                key={h.ocs_code}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted/50"
              >
                <input type="checkbox" checked={order >= 0} onChange={() => toggle(h.ocs_code)} />
                {order >= 0 ? (
                  <Badge variant="secondary" className="h-5 w-5 justify-center p-0 text-xs">
                    {order + 1}
                  </Badge>
                ) : null}
                <span className="flex-1">{h.ocs_name}</span>
                <span className="font-mono text-xs text-muted-foreground">{h.ocs_code}</span>
              </label>
            );
          })}
        </div>
      ) : search.isSuccess ? (
        <p className="mt-3 text-sm text-muted-foreground">沒有結果，換個關鍵字。</p>
      ) : null}

      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>取消</Button>
        <Button onClick={confirm} disabled={picked.length === 0 || setOcc.isPending}>
          {setOcc.isPending ? "設定中…" : `確定（${picked.length} 個職類）`}
        </Button>
      </div>
    </Modal>
  );
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl bg-background p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">{title}</h3>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
