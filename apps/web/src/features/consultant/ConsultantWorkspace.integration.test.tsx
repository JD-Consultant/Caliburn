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
import type { DocumentPatchActionView } from "@caliburn/job-analysis-contract";
import { useForm } from "@tanstack/react-form";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jobAnalysisKeys } from "@/shared/query/jobAnalysisQueries";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/shared/ui/resizable";
import { ApprovedDocumentEditor } from "./ApprovedDocumentEditor";
import { ConsultantConversation } from "./ConsultantConversation";
import { ConsultantInsightPanel } from "./ConsultantInsightPanel";
import { ConsultantWorkspace } from "./ConsultantWorkspace";
import { DocumentReviewPanel } from "./DocumentReviewPanel";
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

    expect(screen.getByRole("separator")).toBeTruthy();
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
      (screen.getAllByRole("checkbox")[0] as HTMLInputElement).disabled,
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
    expect(
      (screen.getAllByRole("checkbox")[0] as HTMLInputElement).disabled,
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
      (screen.getAllByRole("checkbox")[0] as HTMLInputElement).disabled,
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

  it("shows the blocked branch without blocking ordinary employee chat", () => {
    const snapshot = consultantSnapshotFixture();
    snapshot.document_review = {
      ...snapshot.document_review,
      safe_interview_work_available: false,
      decision_required_before_more_interview: true,
      explanation: "目前沒有其他可安全深入的工作，需先處理所列文件結構決定。",
      blocked_branches: [
        {
          work_id: snapshot.current_interview!.work_id,
          title: "月結差異處理",
          decision_action_ids: [
            snapshot.document_review.bundles[0].actions[0].action_id,
          ],
          reason: "需先確認這項工作應歸入哪一項主要職責。",
        },
      ],
    };

    renderWithClient(
      <>
        <ConsultantConversation documentId={DOCUMENT_ID} snapshot={snapshot} />
        <DocumentReviewPanel documentId={DOCUMENT_ID} snapshot={snapshot} />
      </>,
    );

    expect(
      (screen.getByLabelText("回覆顧問") as HTMLTextAreaElement).disabled,
    ).toBe(false);
    expect(screen.getByText("月結差異處理")).toBeTruthy();
    expect(
      screen.getByText("需先確認這項工作應歸入哪一項主要職責。"),
    ).toBeTruthy();
    expect(screen.queryByText(/先完成下方相關文件決定/)).toBeNull();
  });

  it("restores a non-authoritative direct-edit draft after leaving and returning", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const first = renderWithClient(
      <ApprovedDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );
    const title = screen.getByLabelText("職務名稱");
    await user.clear(title);
    await user.type(title, "資深採購專員");
    first.unmount();

    renderWithClient(
      <ApprovedDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    expect((screen.getByLabelText("職務名稱") as HTMLInputElement).value).toBe(
      "資深採購專員",
    );
    expect(screen.getByText("有未儲存的員工修改")).toBeTruthy();
  });

  it("keeps a newer SSE snapshot when a delayed review response arrives", async () => {
    const user = userEvent.setup();
    const renderedSnapshot = consultantSnapshotFixture();
    const delayedResponse = structuredClone(renderedSnapshot);
    delayedResponse.revision = 4;
    const newerSnapshot = structuredClone(renderedSnapshot);
    newerSnapshot.revision = 5;
    const client = new QueryClient();
    client.setQueryData(
      jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID),
      newerSnapshot,
    );
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(delayedResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <DocumentReviewPanel
        documentId={DOCUMENT_ID}
        snapshot={renderedSnapshot}
      />,
      client,
    );

    await user.click(screen.getAllByRole("checkbox")[0]);
    await user.click(screen.getByRole("button", { name: "接受 AI 建議" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    expect(
      client.getQueryData<{ revision: number }>(
        jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID),
      )?.revision,
    ).toBe(5);
  });

  it("supports keyboard semantic review decisions without exposing internal action details", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const baseAction = snapshot.document_review.bundles[0].actions[0];
    const action = (
      overrides: Partial<DocumentPatchActionView>,
    ): DocumentPatchActionView => ({
      ...baseAction,
      atomic_subgroup_id: null,
      ...overrides,
    });
    const actionIds = {
      accept: "ui-review-accept-internal",
      secondAccept: "ui-review-second-accept-internal",
      reject: "ui-review-reject-internal",
    };
    snapshot.document_review.bundles = [
      {
        changeset_id: "ui-review-changeset-accept",
        summary: "接受職務名稱建議",
        created_revision: snapshot.revision,
        source_ids: [snapshot.latest_source_id!],
        acceptance_blocked: false,
        actions: [
          action({
            action_id: actionIds.accept,
            operation: "add",
            path: "/job_title",
            target_key: "/job_title",
            before: null,
            after: "採購專員",
          }),
        ],
      },
      {
        changeset_id: "ui-review-changeset-edit",
        summary: "修改工作描述建議",
        created_revision: snapshot.revision,
        source_ids: [snapshot.latest_source_id!],
        acceptance_blocked: false,
        actions: [
          action({
            action_id: actionIds.secondAccept,
            operation: "revise",
            path: "/work_description",
            target_key: "/work_description",
            before: "目前工作描述",
            after: "AI 建議工作描述",
          }),
        ],
      },
      {
        changeset_id: "ui-review-changeset-reject",
        summary: "移除不適用建議",
        created_revision: snapshot.revision,
        source_ids: [snapshot.latest_source_id!],
        acceptance_blocked: false,
        actions: [
          action({
            action_id: actionIds.reject,
            operation: "withdraw",
            path: "/job_title",
            target_key: "/job_title",
            before: "目前職務名稱",
            after: null,
          }),
        ],
      },
    ];
    snapshot.document_review.unresolved_action_count = 3;
    const response = structuredClone(snapshot);
    response.revision += 1;
    const fetchMock = vi.fn().mockImplementation(
      async () =>
        new Response(JSON.stringify(response), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <DocumentReviewPanel documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(
      screen.getByRole("region", { name: "AI 文件變更審核" }),
    ).toBeTruthy();
    expect(document.body.textContent).not.toContain(actionIds.accept);
    expect(document.body.textContent).not.toContain("write_file");
    expect(document.body.textContent).not.toContain("/candidate/");

    const selectWithKeyboard = async (name: string) => {
      const checkbox = screen.getByRole("checkbox", { name });
      checkbox.focus();
      await user.keyboard(" ");
      expect(checkbox).toHaveProperty("checked", true);
    };
    const decideWithKeyboard = async (name: string) => {
      const button = screen.getByRole("button", { name });
      button.focus();
      await user.keyboard("{Enter}");
    };

    await selectWithKeyboard(
      "選取第 1 組第 1 項新增變更：職務名稱（接受職務名稱建議）",
    );
    await decideWithKeyboard("接受 AI 建議");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(
      JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body)),
    ).toMatchObject({
      command: "accept_changes",
      action_ids: [actionIds.accept],
    });

    await selectWithKeyboard(
      "選取第 2 組第 1 項修改變更：工作描述（修改工作描述建議）",
    );
    await decideWithKeyboard("接受 AI 建議");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(
      JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body)),
    ).toMatchObject({
      command: "accept_changes",
      action_ids: [actionIds.secondAccept],
    });

    await selectWithKeyboard(
      "選取第 3 組第 1 項移除變更：職務名稱（移除不適用建議）",
    );
    const rejectionReason = screen.getByLabelText("若要拒絕，可補充原因");
    await user.type(rejectionReason, "目前正式文件仍需要這項內容");
    await decideWithKeyboard("拒絕");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(
      JSON.parse(String((fetchMock.mock.calls[2][1] as RequestInit).body)),
    ).toMatchObject({
      command: "reject_changes",
      action_ids: [actionIds.reject],
      rejection_reason: "目前正式文件仍需要這項內容",
    });
  });

  it("shows an employee-safe repair state without review actions when the working draft is invalid", () => {
    const snapshot = consultantSnapshotFixture();
    snapshot.document_review = {
      ...snapshot.document_review,
      workspace_status: "invalid",
      diagnostics: [
        {
          code: "json-syntax",
          path: "工作內容",
          message: "工作草稿有內容需要 AI 修正。",
        },
      ],
    };

    renderWithClient(
      <DocumentReviewPanel documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(screen.getByRole("status").textContent).toContain(
      "AI 正在修正工作草稿",
    );
    expect(screen.getByText("工作草稿有內容需要 AI 修正。")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "接受 AI 建議" })).toBeNull();
    expect(document.body.textContent).not.toContain("/workspace/");
  });

  it("renders repeated employee-safe diagnostics without React key collisions", () => {
    const snapshot = consultantSnapshotFixture();
    const repeatedDiagnostic = {
      code: "skill-unloaded",
      path: "工作內容",
      message: "工作草稿有一項內容需要 AI 確認。",
    };
    snapshot.document_review = {
      ...snapshot.document_review,
      workspace_status: "invalid",
      diagnostics: [repeatedDiagnostic, { ...repeatedDiagnostic }],
      bundles: [],
      unresolved_action_count: 0,
    };
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);

    try {
      renderWithClient(
        <DocumentReviewPanel documentId={DOCUMENT_ID} snapshot={snapshot} />,
      );

      expect(
        screen.getAllByText("工作草稿有一項內容需要 AI 確認。"),
      ).toHaveLength(2);
      expect(consoleError.mock.calls.flat().join(" ")).not.toContain(
        "same key",
      );
    } finally {
      consoleError.mockRestore();
    }
  });

  it("announces pending document changes as a status update", () => {
    renderWithClient(
      <DocumentReviewPanel
        documentId={DOCUMENT_ID}
        snapshot={consultantSnapshotFixture()}
      />,
    );

    expect(screen.getByRole("status").textContent).toContain(
      "AI 建議的文件變更",
    );
  });

  it("gives each review checkbox a distinct employee-semantic name", () => {
    renderWithClient(
      <DocumentReviewPanel
        documentId={DOCUMENT_ID}
        snapshot={consultantSnapshotFixture()}
      />,
    );

    expect(
      screen.getByRole("checkbox", {
        name: "選取第 1 組第 1 項修改變更：工作敘述（更新工作描述）；必須整組決定",
      }),
    ).toBeTruthy();
    expect(
      screen.getByRole("checkbox", {
        name: "選取第 1 組第 2 項修改變更：工作敘述（更新工作描述）；必須整組決定",
      }),
    ).toBeTruthy();
  });

  it("distinguishes identical semantic review controls across groups", () => {
    const snapshot = consultantSnapshotFixture();
    const firstBundle = snapshot.document_review.bundles[0];
    const firstAction = firstBundle.actions[0];
    snapshot.document_review.bundles = [
      {
        ...firstBundle,
        summary: "更新工作內容",
        actions: [firstAction],
      },
      {
        ...firstBundle,
        changeset_id: "second-identical-review-group",
        summary: "更新工作內容",
        actions: [
          {
            ...firstAction,
            action_id: "second-identical-review-action",
          },
        ],
      },
    ];

    renderWithClient(
      <DocumentReviewPanel documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(
      screen.getByRole("checkbox", {
        name: "選取第 1 組第 1 項修改變更：工作敘述（更新工作內容）；必須整組決定",
      }),
    ).toBeTruthy();
    expect(
      screen.getByRole("checkbox", {
        name: "選取第 2 組第 1 項修改變更：工作敘述（更新工作內容）；必須整組決定",
      }),
    ).toBeTruthy();
  });

  it("explains a working-draft conflict in employee language while leaving safe choices available", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    snapshot.document_review = {
      ...snapshot.document_review,
      workspace_status: "conflicted",
      diagnostics: [
        {
          code: "workspace-rebase-conflict",
          path: "工作內容",
          message:
            "正式文件與工作草稿的同一內容已有變動，請先選擇要保留的內容。",
        },
      ],
      bundles: [
        {
          ...snapshot.document_review.bundles[0],
          acceptance_blocked: true,
        },
      ],
    };

    renderWithClient(
      <DocumentReviewPanel documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(screen.getByRole("alert").textContent).toContain(
      "正式文件與工作草稿的同一內容已有變動",
    );
    expect(document.body.textContent).not.toMatch(
      /Store|workspace-rebase-conflict|UUID/i,
    );
    const checkbox = screen.getAllByRole("checkbox")[0];
    await user.click(checkbox);
    expect(
      (
        screen.getByRole("button", {
          name: "接受 AI 建議",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(screen.queryByRole("button", { name: "修改後接受" })).toBeNull();
    expect(
      (screen.getByRole("button", { name: "拒絕" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
    expect(screen.queryByRole("button", { name: "稍後處理" })).toBeNull();
  });

  it("lets an employee accept nine changes and reject the remaining one", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const base = snapshot.document_review.bundles[0].actions[0];
    const actionIds = Array.from(
      { length: 10 },
      (_, index) =>
        `00000000-0000-0000-0000-${String(index + 20).padStart(12, "0")}`,
    );
    snapshot.document_review = {
      ...snapshot.document_review,
      bundles: [
        {
          ...snapshot.document_review.bundles[0],
          acceptance_blocked: false,
          actions: actionIds.map((actionId, index) => ({
            ...base,
            action_id: actionId,
            atomic_subgroup_id: null,
            path: `/tasks/task-${index}/statement`,
          })),
        },
      ],
      unresolved_action_count: 10,
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(snapshot), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <DocumentReviewPanel documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    const checkboxes = screen.getAllByRole("checkbox");
    for (const checkbox of checkboxes.slice(0, 9)) await user.click(checkbox);
    expect(screen.getByText("已選 9 項")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "接受 AI 建議" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(
      JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))
        .action_ids,
    ).toEqual(actionIds.slice(0, 9));

    await user.click(screen.getAllByRole("checkbox")[9]);
    await user.type(
      screen.getByLabelText("若要拒絕，可補充原因"),
      "這項內容不適用目前職務",
    );
    await user.click(screen.getByRole("button", { name: "拒絕" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(
      JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body)),
    ).toMatchObject({
      command: "reject_changes",
      action_ids: [actionIds[9]],
    });
  });

  it("clears stale selections after a 409 and refetches the current review", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const client = new QueryClient();
    client.setQueryData(
      jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID),
      snapshot,
    );
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            type: "https://caliburn.dev/problems/job-analysis/authority-conflict",
            title: "Document revision changed",
            status: 409,
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    renderWithClient(
      <DocumentReviewPanel documentId={DOCUMENT_ID} snapshot={snapshot} />,
      client,
    );

    await user.click(screen.getAllByRole("checkbox")[0]);
    await user.click(screen.getByRole("button", { name: "接受 AI 建議" }));

    await waitFor(() =>
      expect(
        client.getQueryState(jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID))
          ?.isInvalidated,
      ).toBe(true),
    );
    expect(screen.queryByText("已選 2 項")).toBeNull();
  });

  it("reviews a structural Duty suggestion without a second edit form or raw IDs", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const actionId = "00000000-0000-0000-0000-000000000020";
    const dutyId = "00000000-0000-0000-0000-000000000021";
    snapshot.document_review.bundles = [
      {
        changeset_id: "00000000-0000-0000-0000-000000000022",
        summary: "新增主要職責",
        created_revision: snapshot.revision,
        source_ids: [snapshot.latest_source_id!],
        acceptance_blocked: false,
        actions: [
          {
            action_id: actionId,
            operation: "add",
            path: "/duties",
            target_key: "new-duty",
            before: null,
            after: {
              duty_id: dutyId,
              statement: "管理採購作業",
              display_order: 0,
            },
            source_ids: [snapshot.latest_source_id!],
            quote_anchors: [],
            read_set: [],
            depends_on_action_ids: [],
            atomic_subgroup_id: null,
            affected_work_ids: [],
            blocks_dependent_analysis: true,
            status: "pending",
          },
        ],
      },
    ];
    const response = structuredClone(snapshot);
    response.revision += 1;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <DocumentReviewPanel documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(document.body.textContent).toContain("管理採購作業");
    expect(screen.queryByLabelText("主要職責內容")).toBeNull();
    expect(document.body.textContent).not.toContain(dutyId);
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "接受 AI 建議" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(request.body));
    expect(body).toEqual({
      command: "accept_changes",
      action_ids: [actionId],
      rejection_reason: null,
    });
  });

  it("reviews field-level relationships without a second edit form or stringifying IDs", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const dutyId = "00000000-0000-0000-0000-000000000030";
    const taskOne = "00000000-0000-0000-0000-000000000031";
    const taskTwo = "00000000-0000-0000-0000-000000000032";
    const knowledgeId = "00000000-0000-0000-0000-000000000033";
    const indicatorOne = "00000000-0000-0000-0000-000000000034";
    const indicatorTwo = "00000000-0000-0000-0000-000000000035";
    const enablerAction = "00000000-0000-0000-0000-000000000036";
    const taskLinkAction = "00000000-0000-0000-0000-000000000037";
    const indicatorLinkAction = "00000000-0000-0000-0000-000000000038";
    snapshot.approved_document.duties = [
      { duty_id: dutyId, statement: "管理採購作業", display_order: 0 },
    ];
    snapshot.approved_document.tasks = [
      {
        task_id: taskOne,
        duty_id: dutyId,
        statement: "建立請購單",
        action: "建立",
        object: "請購單",
        purpose_result: null,
        context: null,
        frequency_text: null,
        responsibility_role: "primary",
        enablers: [],
        display_order: 0,
        competency_level: null,
      },
      {
        task_id: taskTwo,
        duty_id: dutyId,
        statement: "覆核請購內容",
        action: "覆核",
        object: "請購內容",
        purpose_result: null,
        context: null,
        frequency_text: null,
        responsibility_role: "shared",
        enablers: [],
        display_order: 1,
        competency_level: null,
      },
    ];
    snapshot.approved_document.opks = [
      {
        item_id: knowledgeId,
        kind: "knowledge",
        text: "採購流程知識",
        display_order: 0,
        task_ids: [taskOne],
        indicator_ids: [indicatorOne],
        evidence_source_ids: [snapshot.latest_source_id!],
      },
      {
        item_id: indicatorOne,
        kind: "indicator",
        text: "資料正確",
        display_order: 0,
        task_ids: [taskOne],
        indicator_ids: [],
        evidence_source_ids: [snapshot.latest_source_id!],
      },
      {
        item_id: indicatorTwo,
        kind: "indicator",
        text: "準時完成",
        display_order: 1,
        task_ids: [taskTwo],
        indicator_ids: [],
        evidence_source_ids: [snapshot.latest_source_id!],
      },
    ];
    const baseAction = {
      source_ids: [snapshot.latest_source_id!],
      quote_anchors: [],
      read_set: [],
      depends_on_action_ids: [],
      atomic_subgroup_id: null,
      affected_work_ids: [],
      blocks_dependent_analysis: false,
      status: "pending" as const,
    };
    snapshot.document_review.bundles = [
      {
        changeset_id: "00000000-0000-0000-0000-000000000039",
        summary: "調整工作方法與 O／P／K／S 關聯",
        created_revision: snapshot.revision,
        source_ids: [snapshot.latest_source_id!],
        acceptance_blocked: false,
        actions: [
          {
            ...baseAction,
            action_id: enablerAction,
            operation: "revise",
            path: `/tasks/${taskOne}/enablers`,
            target_key: `/tasks/${taskOne}/enablers`,
            before: [],
            after: [{ kind: "method", name: "使用核對清單" }],
          },
          {
            ...baseAction,
            action_id: taskLinkAction,
            operation: "revise",
            path: `/opks/${knowledgeId}/task_ids`,
            target_key: `/opks/${knowledgeId}/task_ids`,
            before: [taskOne],
            after: [taskOne],
          },
          {
            ...baseAction,
            action_id: indicatorLinkAction,
            operation: "revise",
            path: `/opks/${knowledgeId}/indicator_ids`,
            target_key: `/opks/${knowledgeId}/indicator_ids`,
            before: [indicatorOne],
            after: [indicatorOne],
          },
        ],
      },
    ];
    const response = structuredClone(snapshot);
    response.revision += 1;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <DocumentReviewPanel documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(screen.queryByLabelText("名稱")).toBeNull();
    expect(screen.queryByLabelText("關聯工作")).toBeNull();
    expect(screen.queryByLabelText("關聯績效指標")).toBeNull();
    expect(document.body.textContent).not.toContain(taskOne);
    expect(document.body.textContent).not.toContain(indicatorOne);
    for (const checkbox of screen.getAllByRole("checkbox")) {
      await user.click(checkbox);
    }
    await user.click(screen.getByRole("button", { name: "接受 AI 建議" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(request.body));
    expect(body).toMatchObject({
      command: "accept_changes",
      action_ids: [enablerAction, taskLinkAction, indicatorLinkAction],
      rejection_reason: null,
    });
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

  it("preserves the draft and invalidates durable state after an authority conflict", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const client = new QueryClient();
    client.setQueryData(
      jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID),
      snapshot,
    );
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            type: "https://caliburn.dev/problems/job-analysis/authority-conflict",
            title: "Document revision changed",
            status: 409,
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    renderWithClient(
      <ApprovedDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
      client,
    );
    const title = screen.getByLabelText("職務名稱");
    await user.clear(title);
    await user.type(title, "資深採購專員");
    await user.click(screen.getByRole("button", { name: "儲存正式文件" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "草稿仍保留",
    );
    expect((screen.getByLabelText("職務名稱") as HTMLInputElement).value).toBe(
      "資深採購專員",
    );
    await waitFor(() =>
      expect(
        client.getQueryState(jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID))
          ?.isInvalidated,
      ).toBe(true),
    );
  });
});
