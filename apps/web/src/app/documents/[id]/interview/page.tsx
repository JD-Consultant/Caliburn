"use client";

// 顧問稽核視圖(T13;spec §7):員工做完後,顧問看逐字稿 + 槽值↔原話對照(證據)
// + 建議歷史。唯讀;文件本體回工作台看。
import { use } from "react";
import Link from "next/link";
import { ChevronLeft, ShieldAlert, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useInterview } from "@/hooks/useInterview";

const STATUS_BADGE: Record<string, "default" | "secondary" | "outline"> = {
  pending: "outline", accepted: "default", rejected: "secondary",
};

export default function InterviewAuditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, isLoading, isError } = useInterview(id);

  return (
    <div className="mx-auto max-w-4xl px-6 py-6">
      <Link
        href={`/documents/${id}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4" /> 回工作台
      </Link>
      <h1 className="mt-2 text-xl font-semibold">訪談紀錄(顧問稽核視圖)</h1>

      {isLoading ? (
        <div className="mt-6 h-40 animate-pulse rounded-xl bg-muted" />
      ) : isError || !data ? (
        <p className="mt-6 text-sm text-muted-foreground">此職務尚無訪談紀錄。</p>
      ) : (
        <div className="mt-6 space-y-8">
          <section>
            <h2 className="mb-2 text-sm font-medium">
              逐字稿 <Badge variant="secondary">{data.turns.length} 回合</Badge>
            </h2>
            <div className="space-y-2 rounded-md border p-3 text-sm">
              {data.turns.map((t) => (
                <div key={t.seq} className="flex gap-2">
                  <span className="w-10 shrink-0 text-xs text-muted-foreground">
                    {t.role === "employee" ? "員工" : "顧問"}
                  </span>
                  <span className="whitespace-pre-line">{t.text}</span>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-sm font-medium">
              證據對照(槽值 ↔ 員工原話)
              <Badge variant="secondary" className="ml-1">{data.evidence.length}</Badge>
            </h2>
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-xs">
                <thead className="bg-muted/40 text-left">
                  <tr>
                    <th className="p-2">欄位 path</th>
                    <th className="p-2">員工原話</th>
                    <th className="p-2">驗證</th>
                  </tr>
                </thead>
                <tbody>
                  {data.evidence.map((e, i) => (
                    <tr key={i} className="border-t align-top">
                      <td className="p-2 font-mono">{e.doc_path}</td>
                      <td className="p-2">「{e.quote}」</td>
                      <td className="p-2">
                        {e.verified ? (
                          <span className="inline-flex items-center gap-1 text-emerald-600">
                            <ShieldCheck className="h-3.5 w-3.5" /> 逐字稿相符
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-amber-600">
                            <ShieldAlert className="h-3.5 w-3.5" /> 未驗證
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-sm font-medium">
              建議歷史 <Badge variant="secondary">{data.suggestions.length}</Badge>
            </h2>
            <ul className="space-y-2 text-xs">
              {data.suggestions.map((s) => (
                <li key={s.id} className="rounded-md border p-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono">{s.doc_path}</span>
                    <Badge variant={STATUS_BADGE[s.status] ?? "outline"}>{s.status}</Badge>
                  </div>
                  <div className="mt-1 text-muted-foreground">{s.reason}</div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}
