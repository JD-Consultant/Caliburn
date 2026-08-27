// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "@tanstack/react-form";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jobAnalysisKeys } from "@/shared/query/jobAnalysisQueries";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/shared/ui/resizable";
import { ConsultantConversation } from "./ConsultantConversation";
import { ConsultantInsightPanel } from "./ConsultantInsightPanel";
import { ConsultantWorkspace } from "./ConsultantWorkspace";
import { InterviewWorkMap } from "./InterviewWorkMap";
import {
  DOCUMENT_ID,
  consultantSnapshotFixture,
} from "./consultantWorkspaceTestFixture";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}));

class FakeEventSource {
  static latest: FakeEventSource | null = null;
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;

  constructor(readonly url: string) {
    FakeEventSource.latest = this;
  }

  addEventListener() {}
  removeEventListener() {}
  close() {
    this.closed = true;
  }
}

class FakeResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
});

function renderWithClient(ui: ReactNode, client = new QueryClient()) {
  return {
    client,
    ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>),
  };
}

function workspaceClient(snapshot = consultantSnapshotFixture()) {
  const client = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, retry: false } },
  });
  client.setQueryData(
    jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID),
    snapshot,
  );
  client.setQueryData(jobAnalysisKeys.consultantDocument(DOCUMENT_ID), {
    document_id: DOCUMENT_ID,
    title: "採購專員訪談",
    created_at: "2026-08-14T10:00:00Z",
    updated_at: "2026-08-14T10:00:02Z",
  });
  return client;
}

afterEach(() => {
  cleanup();
  localStorage.clear();
  FakeEventSource.latest = null;
  vi.unstubAllGlobals();
});

describe("employee consultant workspace integration", () => {
  it("renders the selected resizable and nested-form framework primitives", () => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);

    render(
      <ResizablePanelGroup orientation="horizontal">
        <ResizablePanel>
          <button type="button">收合訪談工作地圖</button>
        </ResizablePanel>
        <ResizableHandle />
        <ResizablePanel>目前 JD</ResizablePanel>
      </ResizablePanelGroup>,
    );

    const separator = screen.getByRole("separator");
    expect(separator).toBeTruthy();
    expect(separator.className).toContain(
      "aria-[orientation=horizontal]:h-px",
    );
    expect(separator.className).not.toContain(
      "aria-[orientation=vertical]:h-px",
    );
    expect(
      (
        screen.getByRole("button", {
          name: "收合訪談工作地圖",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);

    const form = renderHook(() =>
      useForm({ defaultValues: { duties: [] as string[] } }),
    );
    expect(form.result.current.state.values.duties).toEqual([]);
  });

  it("keeps one current JD centered between independently collapsible work-map and conversation regions", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    vi.stubGlobal("EventSource", FakeEventSource);

    renderWithClient(
      <ConsultantWorkspace documentId={DOCUMENT_ID} />,
      workspaceClient(),
    );

    expect(
      screen.getByRole("complementary", { name: "訪談工作地圖" }),
    ).toBeTruthy();
    expect(screen.getByRole("region", { name: "目前 JD" })).toBeTruthy();
    expect(
      screen.getByRole("complementary", { name: "AI 職務分析顧問" }),
    ).toBeTruthy();
    const conversation = screen.getByRole("region", {
      name: "AI 職務分析顧問對話",
    });
    const composer = screen.getByLabelText("回覆顧問");
    expect(composer.closest("form")?.parentElement).toBe(conversation);
    expect(
      screen
        .getByRole("log", { name: "訪談紀錄" })
        .closest('[data-slot="conversation-scroll-region"]'),
    ).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "收合訪談工作地圖" }));
    expect(
      screen.getByRole("button", { name: "顯示訪談工作地圖" }),
    ).toBeTruthy();
    expect(screen.getByRole("region", { name: "目前 JD" })).toBeTruthy();

    await user.click(
      screen.getByRole("button", { name: "收合 AI 職務分析顧問" }),
    );
    expect(
      screen.getByRole("button", { name: "顯示 AI 職務分析顧問" }),
    ).toBeTruthy();
    expect(screen.getByRole("region", { name: "目前 JD" })).toBeTruthy();
  });

  it("locks every document mutation while analysis runs but keeps reading and navigation available", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    snapshot.run = {
      ...snapshot.run!,
      status: "source_saved",
      completed_at: null,
    };
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    vi.stubGlobal("EventSource", FakeEventSource);

    renderWithClient(
      <ConsultantWorkspace documentId={DOCUMENT_ID} />,
      workspaceClient(snapshot),
    );

    const workspace = screen.getByRole("main", { name: "職務分析工作區" });
    expect(workspace.getAttribute("aria-busy")).toBe("true");
    expect(
      (screen.getByLabelText("回覆顧問") as HTMLTextAreaElement).disabled,
    ).toBe(true);
    expect(
      (screen.getByRole("button", { name: "理解正確" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);

    expect(screen.getByRole("heading", { name: "目前 JD" })).toBeTruthy();
    expect(
      (screen.getByLabelText("職務名稱") as HTMLInputElement).readOnly,
    ).toBe(true);
    expect(
      (screen.getByRole("button", { name: "新增職責" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);

    await user.click(screen.getByRole("button", { name: "收合訪談工作地圖" }));
    expect(
      screen.getByRole("button", { name: "顯示訪談工作地圖" }),
    ).toBeTruthy();
    expect(screen.getAllByText("月結差異處理").length).toBeGreaterThan(0);
  });

  it("does not confuse pending review with an active analysis lock", async () => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    vi.stubGlobal("EventSource", FakeEventSource);

    renderWithClient(
      <ConsultantWorkspace documentId={DOCUMENT_ID} />,
      workspaceClient(),
    );

    expect(
      screen
        .getByRole("main", { name: "職務分析工作區" })
        .getAttribute("aria-busy"),
    ).toBe("false");
    expect(
      (screen.getByLabelText("回覆顧問") as HTMLTextAreaElement).disabled,
    ).toBe(false);
    expect(screen.getByRole("heading", { name: "目前 JD" })).toBeTruthy();
    expect(
      (screen.getByLabelText("職務名稱") as HTMLInputElement).readOnly,
    ).toBe(false);
  });

  it("locks the workspace immediately while the employee answer request is being admitted", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("EventSource", FakeEventSource);
    let finishRequest: ((response: Response) => void) | undefined;
    const pendingResponse = new Promise<Response>((resolve) => {
      finishRequest = resolve;
    });
    const fetchMock = vi.fn().mockReturnValue(pendingResponse);
    vi.stubGlobal("fetch", fetchMock);

    const view = renderWithClient(
      <ConsultantWorkspace documentId={DOCUMENT_ID} />,
      workspaceClient(),
    );
    const answer = screen.getByLabelText("回覆顧問");
    expect((answer as HTMLTextAreaElement).disabled).toBe(false);
    fireEvent.change(answer, {
      target: { value: "這項核准由主管決定，我負責準備資料。" },
    });
    const currentAnswer = screen.getByLabelText("回覆顧問");
    expect((currentAnswer as HTMLTextAreaElement).value).toBe(
      "這項核准由主管決定，我負責準備資料。",
    );
    const sendButton = screen.getByRole("button", { name: "送出澄清" });
    expect((sendButton as HTMLButtonElement).disabled).toBe(false);
    await user.click(sendButton);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    await waitFor(() =>
      expect(
        screen
          .getByRole("main", { name: "職務分析工作區" })
          .getAttribute("aria-busy"),
      ).toBe("true"),
    );
    expect((currentAnswer as HTMLTextAreaElement).disabled).toBe(true);
    expect(
      (screen.getByLabelText("職務名稱") as HTMLInputElement).readOnly,
    ).toBe(true);
    expect(
      (screen.getByRole("button", { name: "新增職責" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);

    view.unmount();
    finishRequest?.(
      new Response(JSON.stringify(consultantSnapshotFixture()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  it("flushes the real current JD editor before the workspace admits chat", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    snapshot.required_clarification = null;
    const savedSnapshot = structuredClone(snapshot);
    savedSnapshot.revision += 1;
    savedSnapshot.current_document.job_title = "資深採購專員";
    savedSnapshot.document_review.workspace_generation += 1;
    savedSnapshot.document_review.workspace_digest =
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    let finishCurrentDocument!: (response: Response) => void;
    const fetchMock = vi.fn().mockImplementation((requestUrl: string) => {
      const url = String(requestUrl);
      if (url.endsWith("/current-document")) {
        return new Promise<Response>((resolve) => {
          finishCurrentDocument = resolve;
        });
      }
      if (url.endsWith("/answers")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              run_id: snapshot.run!.run_id,
              source_id: snapshot.run!.source_id,
              status: "source_saved",
            }),
            { status: 202, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify(savedSnapshot), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <ConsultantWorkspace documentId={DOCUMENT_ID} />,
      workspaceClient(snapshot),
    );

    const title = screen.getByLabelText("職務名稱");
    fireEvent.change(title, { target: { value: "資深採購專員" } });
    fireEvent.blur(title);
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).endsWith("/current-document"),
        ),
      ).toBe(true),
    );
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(
      screen
        .getByRole("main", { name: "職務分析工作區" })
        .getAttribute("aria-busy"),
    ).toBe("false");

    const composer = screen.getByLabelText("回覆顧問") as HTMLTextAreaElement;
    expect(composer.disabled).toBe(false);
    fireEvent.change(composer, {
      target: { value: "我想補充這份工作的實際情境。" },
    });
    expect(
      (screen.getByLabelText("回覆顧問") as HTMLTextAreaElement).value,
    ).toBe("我想補充這份工作的實際情境。");
    const sendButton = screen.getByRole("button", { name: "送出回答" });
    expect((sendButton as HTMLButtonElement).disabled).toBe(false);
    await user.click(sendButton);
    expect(screen.getByRole("button", { name: "準備送出…" })).toBeTruthy();
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).endsWith("/answers")),
    ).toBe(false);

    finishCurrentDocument(
      new Response(JSON.stringify(savedSnapshot), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await waitFor(() =>
      expect(
        screen
          .getAllByRole("status")
          .some((status) => status.textContent?.includes("已儲存")),
      ).toBe(true),
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).endsWith("/answers")),
      ).toBe(true),
    );
    const currentIndex = fetchMock.mock.calls.findIndex(([url]) =>
      String(url).endsWith("/current-document"),
    );
    const answerIndex = fetchMock.mock.calls.findIndex(([url]) =>
      String(url).endsWith("/answers"),
    );
    expect(currentIndex).toBeGreaterThanOrEqual(0);
    expect(answerIndex).toBeGreaterThan(currentIndex);
  });

  it("projects unassigned document items in the work map without treating them as interview blockers", () => {
    const snapshot = consultantSnapshotFixture();
    snapshot.current_document.tasks = [
      {
        task_id: "00000000-0000-0000-0000-000000000050",
        duty_id: null,
        statement: "整理臨時採購需求",
        action: "整理",
        object: "臨時採購需求",
        purpose_result: null,
        context: null,
        frequency_text: null,
        responsibility_role: null,
        enablers: [],
        display_order: 0,
        competency_level: null,
      },
    ];
    snapshot.current_document.opks.push({
      item_id: "00000000-0000-0000-0000-000000000051",
      kind: "knowledge",
      text: "採購法規知識",
      display_order: 0,
      task_ids: [],
      indicator_ids: [],
      evidence_source_ids: [snapshot.latest_source_id!],
    });

    renderWithClient(
      <InterviewWorkMap
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        mutationLocked={false}
      />,
    );

    expect(screen.getByText("尚未分組 1 項")).toBeTruthy();
    expect(screen.getByText("K／S 待連結 1 項")).toBeTruthy();
    expect(screen.getByText("整理臨時採購需求")).toBeTruthy();
    expect(document.body.textContent).not.toContain("阻擋匯出");
  });

  it("shows durable question focus and workspace-derived employee decision progress", () => {
    const snapshot = consultantSnapshotFixture();
    snapshot.current_interview = null;
    snapshot.semantic_progress.employee_decisions = {
      pending: 2,
    };

    renderWithClient(
      <ConsultantInsightPanel documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(screen.getByText("目前要釐清的問題")).toBeTruthy();
    expect(screen.getByText("異常判斷依據")).toBeTruthy();
    expect(screen.getByText("待你確認 2 項")).toBeTruthy();
  });

  it("renders the whole durable workspace, reconnect state and single force-export confirmation", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const client = new QueryClient({
      defaultOptions: { queries: { staleTime: Infinity, retry: false } },
    });
    client.setQueryData(
      jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID),
      snapshot,
    );
    client.setQueryData(jobAnalysisKeys.consultantDocument(DOCUMENT_ID), {
      document_id: DOCUMENT_ID,
      title: "採購專員訪談",
      created_at: "2026-08-14T10:00:00Z",
      updated_at: "2026-08-14T10:00:02Z",
    });
    vi.stubGlobal("EventSource", FakeEventSource);

    const view = renderWithClient(
      <ConsultantWorkspace documentId={DOCUMENT_ID} />,
      client,
    );

    expect(screen.getByText("外部 AI 與文件權限")).toBeTruthy();
    expect(
      screen.getByRole("region", { name: "目前 JD 編輯器" }),
    ).toBeTruthy();
    expect(
      screen.queryByRole("region", { name: "AI 文件變更審核" }),
    ).toBeNull();
    expect(screen.getByText("先大致盤點工作")).toBeTruthy();
    expect(screen.getByText("還不知道這項工作交付什麼成果。")).toBeTruthy();
    expect(screen.getByText(/再談一個實例可補齊成果與指標/)).toBeTruthy();
    expect(
      screen.getByText("這項核准是你本人決定，還是主管決定？"),
    ).toBeTruthy();

    await act(async () =>
      FakeEventSource.latest?.onerror?.(new Event("error")),
    );
    expect(screen.getByText(/連線恢復中/)).toBeTruthy();
    await act(async () => FakeEventSource.latest?.onopen?.(new Event("open")));
    expect(screen.getByText(/已連線；變更會自動更新/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "匯出 XLSX" }));
    expect(screen.getByText("匯出前仍有以下缺口")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "我已看過，仍要匯出" }),
    ).toBeTruthy();

    const stream = FakeEventSource.latest;
    view.unmount();
    expect(stream?.closed).toBe(true);
  });

  it("keeps ordinary chat available after failure and offers retry separately", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const unrelatedSourceId = "00000000-0000-0000-0000-000000000040";
    snapshot.run = {
      ...snapshot.run!,
      status: "failed",
      completed_at: null,
      error_code: "provider_unavailable",
    };
    snapshot.employee_messages.push({
      source_id: unrelatedSourceId,
      text: "我也會整理供應商名單。",
      created_at: "2026-08-14T10:01:00Z",
      processing_status: "committed",
    });
    snapshot.required_clarification = null;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          run_id: snapshot.run.run_id,
          source_id: snapshot.run.source_id,
          status: "source_saved",
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <ConsultantConversation documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    const answer = screen.getByLabelText("回覆顧問") as HTMLTextAreaElement;
    expect(answer.disabled).toBe(false);
    expect(screen.queryByRole("button", { name: "更正這段原話" })).toBeNull();
    expect(screen.getByRole("button", { name: "重試同一則回答" })).toBeTruthy();
    await user.type(answer, "我每月會先核對差異明細，再追查原因。");
    await user.click(screen.getByRole("button", { name: "送出回答" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toEqual({
      text: "我每月會先核對差異明細，再追查原因。",
    });
  });

  it("waits for the current JD flush before admitting an employee answer", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    snapshot.required_clarification = null;
    let finishFlush!: () => void;
    const beforeSubmit = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finishFlush = resolve;
        }),
    );
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          run_id: snapshot.run!.run_id,
          source_id: snapshot.run!.source_id,
          status: "source_saved",
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <ConsultantConversation
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        beforeSubmit={beforeSubmit}
      />,
    );

    const answer = screen.getByLabelText("回覆顧問") as HTMLTextAreaElement;
    await user.type(answer, "我想補充剛才的工作內容。");
    await user.click(screen.getByRole("button", { name: "送出回答" }));

    expect(beforeSubmit).toHaveBeenCalledTimes(1);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(answer.value).toBe("我想補充剛才的工作內容。");

    finishFlush();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  });

  it("keeps the chat draft and does not admit an answer when current JD flush fails", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    snapshot.required_clarification = null;
    const beforeSubmit = vi.fn().mockRejectedValue(new Error("save failed"));
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <ConsultantConversation
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        beforeSubmit={beforeSubmit}
      />,
    );

    const answer = screen.getByLabelText("回覆顧問") as HTMLTextAreaElement;
    await user.type(answer, "這段不能因保存失敗而消失。");
    await user.click(screen.getByRole("button", { name: "送出回答" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain(
      "請先完成目前 JD 儲存",
    );
    expect(answer.value).toBe("這段不能因保存失敗而消失。");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uses the conversation composer for free-text required clarification", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const response = structuredClone(snapshot);
    response.revision += 1;
    response.required_clarification = null;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <ConsultantConversation documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(screen.queryByRole("radio")).toBeNull();
    await user.click(screen.getByRole("button", { name: "主管決定" }));
    const answer = screen.getByLabelText("回覆顧問") as HTMLTextAreaElement;
    expect(answer.value).toBe("主管決定");
    await user.type(answer, "，我負責準備資料。");
    await user.click(screen.getByRole("button", { name: "送出澄清" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const [url, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain(
      `/clarifications/${snapshot.required_clarification!.clarification_id}`,
    );
    expect(JSON.parse(String(request.body))).toEqual({
      text: "主管決定，我負責準備資料。",
    });
  });

});
