"use client";

// 顧問稽核視圖:訪談逐字稿(唯讀;文件本體回工作台看)。
// T12(ADR 0030):evidence/建議層退場——溯源住文件 `_pending.src`(表格「?」出處卡),
// 審閱紀錄住 review-events(後台/trace 用);本頁保留逐字稿=溯源真相。
import { use } from "react";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useInterview } from "@/hooks/useInterview";

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
            <p className="mt-2 text-xs text-muted-foreground">
              AI 寫入的出處(官方來源/原話)在工作台表格各筆的「?」出處卡查看。
            </p>
          </section>
        </div>
      )}
    </div>
  );
}
