"use client";

import { use, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useProfile } from "@/hooks/useProfiles";
import { useInterview } from "@/hooks/useInterview";
import { ProgressTracker } from "@/components/interview/ProgressTracker";
import { IcapBadges } from "@/components/interview/IcapBadges";
import { ChatBubble } from "@/components/interview/ChatBubble";
import { LiveDocPanel } from "@/components/interview/LiveDocPanel";
import { StageGuide } from "@/components/interview/StageGuide";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Send, BriefcaseIcon, FileText, CheckCircle2 } from "lucide-react";

export default function InterviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: profile, isLoading: profileLoading } = useProfile(id);
  const { messages, isLoading: histLoading, streaming, streamMessages, send, sendSilent } = useInterview(id);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const autoStarted = useRef(false);

  useEffect(() => {
    if (
      !profileLoading &&
      !histLoading &&
      !autoStarted.current &&
      messages.length === 0 &&
      profile?.stage === "basic_info"
    ) {
      autoStarted.current = true;
      sendSilent("開始訪談");
    }
  }, [profileLoading, histLoading, messages.length, profile?.stage, sendSilent]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamMessages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    await send(text, outgoingPhase);
    inputRef.current?.focus();
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const tasks = profile?.graph_state?.extracted_tasks ?? [];
  const candidates = profile?.graph_state?.icap_candidates ?? [];
  const readiness = profile?.graph_state?.interview_readiness_detail;
  const behaviorIndicators = profile?.graph_state?.behavior_indicators ?? [];
  const ksaItems = profile?.graph_state?.ksa_items ?? [];
  const stage = profile?.stage ?? "basic_info";
  const isPreview = stage === "preview";
  const missingFields = profile?.graph_state?.missing_fields ?? [];

  const currentTaskIndex = profile?.graph_state?.current_task_index ?? 0;
  const currentTask = tasks[currentTaskIndex];
  const outgoingPhase =
    stage === "star" && currentTask ? `star_${currentTask.task_name}` :
    stage === "five_w2h" && currentTask ? `five_w2h_${currentTask.task_name}` :
    "general";

  if (profileLoading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-muted-foreground text-sm">載入中...</div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-muted-foreground mb-4">找不到此職務檔案</p>
          <Link href="/dashboard">
            <Button variant="outline">返回列表</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <header className="border-b px-4 py-3 flex items-center gap-3 shrink-0">
        <Link href="/dashboard">
          <Button variant="ghost" size="icon" className="shrink-0">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <BriefcaseIcon className="w-4 h-4 text-blue-600 shrink-0" />
        <div className="flex-1 min-w-0">
          <h1 className="font-semibold text-sm truncate">{profile.job_title}</h1>
          <p className="text-xs text-muted-foreground">{profile.department}</p>
        </div>
        {isPreview && (
          <Button
            size="sm"
            className="shrink-0 gap-2"
            onClick={() => router.push(`/profiles/${id}/preview`)}
          >
            <FileText className="w-3.5 h-3.5" />
            查看報告
          </Button>
        )}
      </header>

      {/* Progress */}
      <div className="border-b shrink-0">
        <ProgressTracker stage={stage} readiness={readiness} />
      </div>

      {/* iCAP badges */}
      {candidates.length > 0 && <IcapBadges candidates={candidates} />}

      {/* Main area */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Chat — left column */}
        <div className="w-[36%] shrink-0 flex flex-col min-h-0 overflow-hidden">
          <ScrollArea className="flex-1">
            <div className="py-4 space-y-1">
              {histLoading && (
                <div className="flex justify-center py-8">
                  <div className="text-xs text-muted-foreground">載入對話記錄...</div>
                </div>
              )}
              {messages
                .filter((msg) => !(msg.role === "user" && msg.content === "開始訪談"))
                .map((msg, i) => (
                  <ChatBubble key={i} message={msg} />
                ))}
              {streamMessages.map((msg, i) => (
                <ChatBubble
                  key={`stream-${i}`}
                  message={msg}
                  streaming={streaming && i === streamMessages.length - 1}
                />
              ))}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>

          {/* Task confirmation bar */}
          {stage === "task_extraction" && tasks.length > 0 && !streaming && (
            <div className="border-t bg-blue-50/60 dark:bg-blue-950/20 px-4 py-3 shrink-0">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                    AI 整理出 {tasks.length} 項任務
                  </p>
                  <p className="text-xs text-blue-700/70 dark:text-blue-300/70 mt-0.5">
                    確認正確後進入深度訪談。如有遺漏請在下方輸入補充。
                  </p>
                </div>
                <Button
                  size="sm"
                  className="shrink-0 gap-1.5"
                  onClick={() => sendSilent("確認", "general")}
                  disabled={streaming}
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  確認任務清單
                </Button>
              </div>
            </div>
          )}

          {/* Input */}
          <div className="border-t p-4 shrink-0">
            <StageGuide
              stage={stage}
              currentTask={currentTask}
              currentTaskIndex={currentTaskIndex}
              taskCount={tasks.length}
              missingFields={missingFields}
              readiness={readiness}
              streaming={streaming}
            />
            <div className="flex gap-2 items-end">
              <textarea
                ref={inputRef}
                className="flex-1 rounded-xl border bg-muted/50 px-4 py-3 text-sm resize-none outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-h-[44px] max-h-32"
                placeholder={
                  streaming ? "AI 回覆中..." :
                  stage === "task_extraction" && tasks.length > 0 ? "如有遺漏或修改，請直接輸入..." :
                  "輸入訊息，按 Enter 送出"
                }
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                disabled={streaming}
              />
              <Button
                size="icon"
                className="h-11 w-11 rounded-xl shrink-0"
                onClick={handleSend}
                disabled={!input.trim() || streaming}
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Live document panel — right column */}
        <LiveDocPanel
          profile={profile}
          tasks={tasks}
          indicators={behaviorIndicators}
          ksaItems={ksaItems}
          stage={stage}
          currentTaskIndex={currentTaskIndex}
          candidates={candidates}
          ocsDocument={profile.graph_state?.ocs_document}
        />
      </div>
    </div>
  );
}
