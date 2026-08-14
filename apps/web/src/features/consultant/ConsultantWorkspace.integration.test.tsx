// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { jobAnalysisKeys } from "@/shared/query/jobAnalysisQueries";
import { ApprovedDocumentEditor } from "./ApprovedDocumentEditor";
import { ConsultantConversation } from "./ConsultantConversation";
import { ConsultantWorkspace } from "./ConsultantWorkspace";
import { DocumentReviewPanel } from "./DocumentReviewPanel";
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

function renderWithClient(ui: ReactNode, client = new QueryClient()) {
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
    ),
  };
}

afterEach(() => {
  cleanup();
  localStorage.clear();
  FakeEventSource.latest = null;
  vi.unstubAllGlobals();
});

describe("employee consultant workspace integration", () => {
  it("renders the whole durable workspace, reconnect state and single force-export confirmation", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const client = new QueryClient({
      defaultOptions: { queries: { staleTime: Infinity, retry: false } },
    });
    client.setQueryData(jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID), snapshot);
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
    expect(screen.getByText("這項核准是你本人決定，還是主管決定？")).toBeTruthy();

    await act(async () => FakeEventSource.latest?.onerror?.(new Event("error")));
    expect(screen.getByText(/連線恢復中/)).toBeTruthy();
    await act(async () => FakeEventSource.latest?.onopen?.(new Event("open")));
    expect(screen.getByText(/已連線；變更會自動更新/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "匯出 XLSX" }));
    expect(screen.getByText("匯出前仍有以下缺口")).toBeTruthy();
    expect(screen.getByRole("button", { name: "我已看過，仍要匯出" })).toBeTruthy();

    const stream = FakeEventSource.latest;
    view.unmount();
    expect(stream?.closed).toBe(true);
  });

  it("shows the blocked branch and prevents only a new AI interview turn when no safe branch remains", () => {
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
          decision_action_ids: [snapshot.document_review.bundles[0].actions[0].action_id],
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

    expect((screen.getByLabelText("回覆顧問") as HTMLTextAreaElement).disabled).toBe(
      true,
    );
    expect(screen.getByText("月結差異處理")).toBeTruthy();
    expect(
      screen.getByText("需先確認這項工作應歸入哪一項主要職責。"),
    ).toBeTruthy();
    expect(screen.getByText(/先完成下方相關文件決定/)).toBeTruthy();
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
      <DocumentReviewPanel documentId={DOCUMENT_ID} snapshot={renderedSnapshot} />,
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

  it("edits a structural Duty suggestion through employee fields without exposing raw JSON or IDs", async () => {
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
            target_ids: [dutyId],
            depends_on_action_ids: [],
            atomic_subgroup_id: null,
            affected_work_ids: [],
            blocks_dependent_analysis: true,
            status: "pending",
            employee_after: null,
            rejection_reason: null,
            stale_reason: null,
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

    const statement = screen.getByLabelText("主要職責內容");
    expect(document.body.textContent).not.toContain(dutyId);
    await user.clear(statement);
    await user.type(statement, "統籌採購與覆核作業");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "修改後接受" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(request.body));
    expect(body.edited_after_by_action_id[actionId]).toEqual({
      duty_id: dutyId,
      statement: "統籌採購與覆核作業",
      display_order: 0,
    });
  });

  it("edits field-level relationships and enablers without showing or stringifying IDs", async () => {
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
      target_ids: [],
      depends_on_action_ids: [],
      atomic_subgroup_id: null,
      affected_work_ids: [],
      blocks_dependent_analysis: false,
      status: "pending" as const,
      employee_after: null,
      rejection_reason: null,
      stale_reason: null,
    };
    snapshot.document_review.bundles = [
      {
        changeset_id: "00000000-0000-0000-0000-000000000039",
        summary: "調整工作方法與 O／P／K／S 關聯",
        created_revision: snapshot.revision,
        source_ids: [snapshot.latest_source_id!],
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

    const enablerName = screen.getByLabelText("名稱");
    const taskLinks = screen.getByLabelText("關聯工作");
    const indicatorLinks = screen.getByLabelText("關聯績效指標");
    expect(document.body.textContent).not.toContain(taskOne);
    expect(document.body.textContent).not.toContain(indicatorOne);
    await user.clear(enablerName);
    await user.type(enablerName, "依採購覆核表逐項核對");
    await user.deselectOptions(taskLinks, taskOne);
    await user.selectOptions(taskLinks, taskTwo);
    await user.deselectOptions(indicatorLinks, indicatorOne);
    await user.selectOptions(indicatorLinks, indicatorTwo);
    for (const checkbox of screen.getAllByRole("checkbox")) {
      await user.click(checkbox);
    }
    await user.click(screen.getByRole("button", { name: "修改後接受" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(request.body));
    expect(body.edited_after_by_action_id).toMatchObject({
      [enablerAction]: [{ kind: "method", name: "依採購覆核表逐項核對" }],
      [taskLinkAction]: [taskTwo],
      [indicatorLinkAction]: [indicatorTwo],
    });
  });

  it("lets a failed answer be corrected but disables unrelated new answers and corrections", async () => {
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
      validity: "current",
      supersedes_source_id: null,
      superseded_by_source_id: null,
    });
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
    const correctionButtons = screen.getAllByRole("button", {
      name: "更正這段原話",
    }) as HTMLButtonElement[];
    expect(answer.disabled).toBe(true);
    expect(correctionButtons[0].disabled).toBe(false);
    expect(correctionButtons[1].disabled).toBe(true);

    await user.click(correctionButtons[0]);
    expect(answer.disabled).toBe(false);
    await user.clear(answer);
    await user.type(answer, "我每月會先核對差異明細，再追查原因。");
    await user.click(screen.getByRole("button", { name: "送出回答" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toMatchObject({
      text: "我每月會先核對差異明細，再追查原因。",
      supersedes_source_id: snapshot.run.source_id,
    });
  });

  it("preserves the draft and invalidates durable state after an authority conflict", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const client = new QueryClient();
    client.setQueryData(jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID), snapshot);
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

    expect((await screen.findByRole("alert")).textContent).toContain("草稿仍保留");
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
