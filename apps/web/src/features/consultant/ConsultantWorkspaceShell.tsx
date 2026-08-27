"use client";

import { Drawer } from "@base-ui/react/drawer";
import { PanelLeft, PanelRight, X } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useDefaultLayout, usePanelRef } from "react-resizable-panels";

import { Button } from "@/shared/ui/button";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/shared/ui/resizable";

type WorkspaceMode = "desktop" | "medium" | "narrow";

function useWorkspaceMode(): WorkspaceMode {
  const [mode, setMode] = useState<WorkspaceMode>("desktop");

  useEffect(() => {
    const update = () => {
      setMode(
        window.innerWidth >= 960
          ? "desktop"
          : window.innerWidth >= 720
            ? "medium"
            : "narrow",
      );
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  return mode;
}

function PanelToolbar({
  leftOpen,
  rightOpen,
  onToggleLeft,
  onToggleRight,
}: {
  leftOpen: boolean;
  rightOpen: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-b border-stone-200 bg-white px-3 py-2">
      <Button
        type="button"
        size="sm"
        variant="ghost"
        aria-label={`${leftOpen ? "收合" : "顯示"}訪談工作地圖`}
        aria-expanded={leftOpen}
        onClick={onToggleLeft}
      >
        <PanelLeft />
        <span className="hidden sm:inline">工作地圖</span>
      </Button>
      <p className="truncate text-xs text-stone-500">
        左右面板可收合；中央目前 JD 會一直保留
      </p>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        aria-label={`${rightOpen ? "收合" : "顯示"} AI 職務分析顧問`}
        aria-expanded={rightOpen}
        onClick={onToggleRight}
      >
        <span className="hidden sm:inline">顧問</span>
        <PanelRight />
      </Button>
    </div>
  );
}

function SideDrawer({
  open,
  onOpenChange,
  side,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  side: "left" | "right";
  title: string;
  children: ReactNode;
}) {
  return (
    <Drawer.Root
      open={open}
      onOpenChange={(nextOpen) => onOpenChange(nextOpen)}
      swipeDirection={side}
    >
      <Drawer.Portal>
        <Drawer.Backdrop className="fixed inset-0 z-40 bg-stone-950/20 backdrop-blur-[1px]" />
        <Drawer.Viewport
          className={`fixed inset-0 z-50 flex ${
            side === "left" ? "justify-start" : "justify-end"
          }`}
        >
          <Drawer.Popup className="h-full w-[min(92vw,28rem)] border-stone-200 bg-stone-50 shadow-2xl data-[ending-style]:translate-x-[calc(var(--drawer-swipe-direction-x)*100%)] data-[starting-style]:translate-x-[calc(var(--drawer-swipe-direction-x)*100%)]">
            <div className="flex h-full min-h-0 flex-col">
              <div className="flex shrink-0 items-center justify-between border-b border-stone-200 bg-white px-4 py-3">
                <Drawer.Title className="font-semibold">{title}</Drawer.Title>
                <Drawer.Close
                  className="rounded-lg p-2 text-stone-500 hover:bg-stone-100 hover:text-stone-950"
                  aria-label={`關閉${title}`}
                >
                  <X className="size-4" />
                </Drawer.Close>
              </div>
              <Drawer.Content className="min-h-0 flex-1 overflow-hidden">
                {children}
              </Drawer.Content>
            </div>
          </Drawer.Popup>
        </Drawer.Viewport>
      </Drawer.Portal>
    </Drawer.Root>
  );
}

function WorkMapRegion({ children }: { children: ReactNode }) {
  return (
    <aside
      aria-label="訪談工作地圖"
      className="h-full min-h-0 overflow-y-auto bg-stone-50 p-4"
    >
      {children}
    </aside>
  );
}

function CurrentDocumentRegion({ children }: { children: ReactNode }) {
  return (
    <section
      aria-label="目前 JD"
      className="h-full min-h-0 overflow-y-auto bg-white px-4 py-5 lg:px-6"
    >
      {children}
    </section>
  );
}

function ConversationRegion({ children }: { children: ReactNode }) {
  return (
    <aside
      aria-label="AI 職務分析顧問"
      className="h-full min-h-0 overflow-hidden bg-stone-50 p-4"
    >
      {children}
    </aside>
  );
}

function DesktopWorkspace({
  documentId,
  workMap,
  currentDocument,
  conversation,
}: {
  documentId: string;
  workMap: ReactNode;
  currentDocument: ReactNode;
  conversation: ReactNode;
}) {
  const leftRef = usePanelRef();
  const rightRef = usePanelRef();
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const { defaultLayout, onLayoutChanged } = useDefaultLayout({
    id: `consultant-workspace:${documentId}`,
    panelIds: ["work-map", "current-jd", "conversation"],
    storage: typeof window === "undefined" ? undefined : window.localStorage,
    onlySaveAfterUserInteractions: true,
  });

  return (
    <>
      <PanelToolbar
        leftOpen={!leftCollapsed}
        rightOpen={!rightCollapsed}
        onToggleLeft={() => {
          setLeftCollapsed(!leftCollapsed);
          if (leftCollapsed) leftRef.current?.expand();
          else leftRef.current?.collapse();
        }}
        onToggleRight={() => {
          setRightCollapsed(!rightCollapsed);
          if (rightCollapsed) rightRef.current?.expand();
          else rightRef.current?.collapse();
        }}
      />
      <ResizablePanelGroup
        id={`consultant-workspace:${documentId}`}
        orientation="horizontal"
        defaultLayout={defaultLayout}
        onLayoutChanged={onLayoutChanged}
        className="min-h-0 flex-1"
      >
        <ResizablePanel
          id="work-map"
          panelRef={leftRef}
          defaultSize="22"
          minSize="16%"
          maxSize="32%"
          collapsedSize="0%"
          collapsible
          onResize={(size) => setLeftCollapsed(size.asPercentage < 0.5)}
        >
          <WorkMapRegion>{workMap}</WorkMapRegion>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel id="current-jd" defaultSize="52" minSize="34%">
          <CurrentDocumentRegion>{currentDocument}</CurrentDocumentRegion>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel
          id="conversation"
          panelRef={rightRef}
          defaultSize="26"
          minSize="20%"
          maxSize="38%"
          collapsedSize="0%"
          collapsible
          onResize={(size) => setRightCollapsed(size.asPercentage < 0.5)}
        >
          <ConversationRegion>{conversation}</ConversationRegion>
        </ResizablePanel>
      </ResizablePanelGroup>
    </>
  );
}

function CompactWorkspace({
  mode,
  workMap,
  currentDocument,
  conversation,
}: {
  mode: Exclude<WorkspaceMode, "desktop">;
  workMap: ReactNode;
  currentDocument: ReactNode;
  conversation: ReactNode;
}) {
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(mode === "medium");
  const rightInline = mode === "medium" && rightOpen;

  return (
    <>
      <PanelToolbar
        leftOpen={leftOpen}
        rightOpen={rightOpen}
        onToggleLeft={() => setLeftOpen((current) => !current)}
        onToggleRight={() => setRightOpen((current) => !current)}
      />
      <div
        className={`grid min-h-0 flex-1 ${
          rightInline
            ? "grid-cols-[minmax(0,1fr)_minmax(20rem,40%)]"
            : "grid-cols-1"
        }`}
      >
        <CurrentDocumentRegion>{currentDocument}</CurrentDocumentRegion>
        {rightInline ? (
          <ConversationRegion>{conversation}</ConversationRegion>
        ) : null}
      </div>
      <SideDrawer
        open={leftOpen}
        onOpenChange={setLeftOpen}
        side="left"
        title="訪談工作地圖"
      >
        <WorkMapRegion>{workMap}</WorkMapRegion>
      </SideDrawer>
      {mode === "narrow" ? (
        <SideDrawer
          open={rightOpen}
          onOpenChange={setRightOpen}
          side="right"
          title="AI 職務分析顧問"
        >
          <ConversationRegion>{conversation}</ConversationRegion>
        </SideDrawer>
      ) : null}
    </>
  );
}

export function ConsultantWorkspaceShell({
  documentId,
  mutationLocked,
  workMap,
  currentDocument,
  conversation,
}: {
  documentId: string;
  mutationLocked: boolean;
  workMap: ReactNode;
  currentDocument: ReactNode;
  conversation: ReactNode;
}) {
  const mode = useWorkspaceMode();

  return (
    <main
      aria-label="職務分析工作區"
      aria-busy={mutationLocked}
      className="flex h-[calc(100dvh-73px)] min-h-[38rem] flex-col overflow-hidden bg-white"
    >
      {mode === "desktop" ? (
        <DesktopWorkspace
          documentId={documentId}
          workMap={workMap}
          currentDocument={currentDocument}
          conversation={conversation}
        />
      ) : (
        <CompactWorkspace
          mode={mode}
          workMap={workMap}
          currentDocument={currentDocument}
          conversation={conversation}
        />
      )}
    </main>
  );
}
