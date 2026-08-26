// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { DocumentPatchActionView } from "@caliburn/job-analysis-contract";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { jobAnalysisKeys } from "@/shared/query/jobAnalysisQueries";
import { ConsultantConversation } from "./ConsultantConversation";
import { ConsultantInsightPanel } from "./ConsultantInsightPanel";
import { ConsultantWorkspace } from "./ConsultantWorkspace";
import { CurrentDocumentEditor } from "./CurrentDocumentEditor";
import { CurrentDocumentReview } from "./CurrentDocumentReview";
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

function hierarchicalSnapshotFixture() {
  const snapshot = consultantSnapshotFixture();
  const sourceId = snapshot.latest_source_id!;
  const dutyId = "00000000-0000-0000-0000-000000000101";
  const emptyDutyId = "00000000-0000-0000-0000-000000000102";
  const taskId = "00000000-0000-0000-0000-000000000103";
  const unassignedTaskId = "00000000-0000-0000-0000-000000000104";

  snapshot.current_document = {
    ...snapshot.current_document,
    duties: [
      { duty_id: dutyId, statement: "客戶服務", display_order: 0 },
      { duty_id: emptyDutyId, statement: "行政管理", display_order: 1 },
    ],
    tasks: [
      {
        task_id: taskId,
        duty_id: dutyId,
        statement: "處理申訴案件",
        action: "處理",
        object: "客戶申訴",
        purpose_result: "維持服務品質",
        context: null,
        frequency_text: "每日",
        responsibility_role: "primary",
        enablers: [],
        display_order: 0,
        competency_level: null,
      },
      {
        task_id: unassignedTaskId,
        duty_id: null,
        statement: "尚待歸類的工作",
        action: "追蹤",
        object: "待確認事項",
        purpose_result: null,
        context: null,
        frequency_text: null,
        responsibility_role: null,
        enablers: [],
        display_order: 1,
        competency_level: null,
      },
    ],
    opks: [
      {
        item_id: "00000000-0000-0000-0000-000000000105",
        kind: "output",
        text: "完成申訴處理",
        display_order: 0,
        task_ids: [taskId],
        indicator_ids: [],
        evidence_source_ids: [sourceId],
      },
      {
        item_id: "00000000-0000-0000-0000-000000000106",
        kind: "indicator",
        text: "回覆時效",
        display_order: 0,
        task_ids: [taskId],
        indicator_ids: [],
        evidence_source_ids: [sourceId],
      },
      {
        item_id: "00000000-0000-0000-0000-000000000107",
        kind: "knowledge",
        text: "客訴處理規範",
        display_order: 0,
        task_ids: [taskId, unassignedTaskId],
        indicator_ids: [],
        evidence_source_ids: [sourceId],
      },
      {
        item_id: "00000000-0000-0000-0000-000000000108",
        kind: "skill",
        text: "溝通協調",
        display_order: 0,
        task_ids: [taskId, unassignedTaskId],
        indicator_ids: [],
        evidence_source_ids: [sourceId],
      },
      {
        item_id: "00000000-0000-0000-0000-000000000109",
        kind: "attitude",
        text: "耐心",
        display_order: 0,
        task_ids: [],
        indicator_ids: [],
        evidence_source_ids: [sourceId],
      },
    ],
  };
  snapshot.approved_document = structuredClone(snapshot.current_document);
  return snapshot;
}

function semanticReviewSnapshotFixture() {
  const snapshot = hierarchicalSnapshotFixture();
  const sourceId = snapshot.latest_source_id!;
  const [dutyOne, dutyTwo] = snapshot.current_document.duties;
  const [frequencyTask, reassignedTask] = snapshot.current_document.tasks;
  const frequencyActionId = "00000000-0000-0000-0000-000000000201";
  const reassignmentActionId = "00000000-0000-0000-0000-000000000202";

  snapshot.approved_document = structuredClone(snapshot.current_document);
  snapshot.approved_document.tasks[0].frequency_text = "每月彙整";
  snapshot.current_document.tasks[0].frequency_text =
    "每週追蹤；重大修法即時通報";
  snapshot.approved_document.tasks[1].duty_id = dutyTwo.duty_id;
  snapshot.current_document.tasks[1].duty_id = dutyOne.duty_id;
  snapshot.document_review = {
    ...snapshot.document_review,
    workspace_status: "pending",
    unresolved_action_count: 2,
    bundles: [
      {
        changeset_id: "00000000-0000-0000-0000-000000000203",
        summary: "更新追蹤頻率",
        source_ids: [sourceId],
        created_revision: snapshot.revision,
        acceptance_blocked: false,
        actions: [
          {
            action_id: frequencyActionId,
            operation: "revise",
            path: `/tasks/${frequencyTask.task_id}/frequency_text`,
            target_key: `frequency:${frequencyTask.task_id}`,
            before: "每月彙整",
            after: "每週追蹤；重大修法即時通報",
            source_ids: [sourceId],
            quote_anchors: [],
            read_set: [],
            depends_on_action_ids: [],
            atomic_subgroup_id: null,
            affected_work_ids: [],
            blocks_dependent_analysis: false,
            status: "pending",
          },
        ],
      },
      {
        changeset_id: "00000000-0000-0000-0000-000000000204",
        summary: "調整工作歸屬",
        source_ids: [sourceId],
        created_revision: snapshot.revision,
        acceptance_blocked: false,
        actions: [
          {
            action_id: reassignmentActionId,
            operation: "reassign",
            path: `/tasks/${reassignedTask.task_id}/duty_id`,
            target_key: `reassign:${reassignedTask.task_id}`,
            before: dutyTwo.duty_id,
            after: dutyOne.duty_id,
            source_ids: [sourceId],
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
    ],
  };
  return snapshot;
}

function seedWorkspace(client: QueryClient, snapshot: ReturnType<typeof consultantSnapshotFixture>) {
  client.setQueryData(jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID), snapshot);
  client.setQueryData(jobAnalysisKeys.consultantDocument(DOCUMENT_ID), {
    document_id: DOCUMENT_ID,
    title: "採購專員訪談",
    created_at: "2026-08-14T10:00:00Z",
    updated_at: "2026-08-14T10:00:02Z",
  });
}

function renderWorkspaceFixture(
  snapshot = hierarchicalSnapshotFixture(),
  client = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, retry: false } },
  }),
) {
  seedWorkspace(client, snapshot);
  vi.stubGlobal("EventSource", FakeEventSource);
  return renderWithClient(<ConsultantWorkspace documentId={DOCUMENT_ID} />, client);
}

afterEach(() => {
  cleanup();
  localStorage.clear();
  FakeEventSource.latest = null;
  vi.unstubAllGlobals();
});

describe("employee consultant workspace integration", () => {
  it("renders one current-JD hierarchy with unassigned work and shared K/S", () => {
    renderWorkspaceFixture();

    expect(screen.getByRole("heading", { name: "目前 JD" })).toBeTruthy();
    const duty = screen.getByRole("region", { name: "Duty 1 客戶服務" });
    expect(
      within(duty).getByRole("heading", { name: "處理申訴案件" }),
    ).toBeTruthy();
    const unassigned = screen.getByRole("region", { name: "尚未歸屬" });
    expect(
      within(unassigned).getByRole("heading", { name: "尚待歸類的工作" }),
    ).toBeTruthy();
    expect(screen.getAllByText("共用於 2 項工作").length).toBeGreaterThan(0);
    expect(screen.queryByRole("heading", { name: /AI 草稿/ })).toBeNull();
  });

  it("keeps structural editing inside the current-JD hierarchy", async () => {
    const user = userEvent.setup();
    renderWorkspaceFixture();

    await user.click(screen.getByRole("button", { name: "新增工作" }));
    const unassigned = screen.getByRole("region", { name: "尚未歸屬" });
    expect(
      within(unassigned).getByRole("article", { name: "Task 3 新工作" }),
    ).toBeTruthy();

    await user.selectOptions(screen.getByLabelText("Task 3 所屬職責"), [
      "客戶服務",
    ]);
    const duty = screen.getByRole("region", { name: "Duty 1 客戶服務" });
    const movedTask = within(duty).getByRole("article", {
      name: "Task 3 新工作",
    });
    await user.click(
      within(movedTask).getByRole("button", { name: "新增產出 O" }),
    );
    expect(
      within(movedTask).getByLabelText("Task 3 O 1 內容"),
    ).toBeTruthy();
  });

  it("does not guess a Task when an unassigned K or S becomes O or P", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          type: "https://caliburn.dev/problems/job-analysis/invalid-request",
          title: "Invalid request",
          status: 422,
        }),
        {
          status: 422,
          headers: { "Content-Type": "application/problem+json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWorkspaceFixture();

    const unassigned = screen.getByRole("region", { name: "尚未歸屬" });
    await user.click(
      within(unassigned).getByRole("button", { name: "未歸屬 K" }),
    );
    await user.selectOptions(
      within(unassigned).getByLabelText("尚未歸屬 K 1 類型"),
      "output",
    );

    expect(
      (
        within(unassigned).getByLabelText(
          "尚未歸屬 O 1 連結工作",
        ) as HTMLSelectElement
      ).value,
    ).toBe("");

    await user.click(screen.getByRole("button", { name: "儲存目前 JD" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(request.body));
    expect(body.document.opks.at(-1)).toMatchObject({
      kind: "output",
      task_ids: [],
    });
    expect(screen.getByRole("alert").textContent).toContain(
      "送出的內容無法處理",
    );
  });

  it("reviews a changed field in place on the current-JD skeleton", async () => {
    const user = userEvent.setup();
    renderWorkspaceFixture(semanticReviewSnapshotFixture());

    await user.click(screen.getByRole("button", { name: "審核變更 2" }));

    expect(screen.getByRole("heading", { name: "審核變更" })).toBeTruthy();
    expect(screen.getByText("每月彙整").className).toContain("line-through");
    expect(
      screen
        .getAllByText("每週追蹤；重大修法即時通報")
        .some((element) => element.className.includes("text-emerald")),
    ).toBe(true);
    expect(
      screen.getByRole("button", { name: "接受這項變更" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "拒絕這項變更" }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /稍後處理/ })).toBeNull();
  });

  it("shows every dependency included by edit-and-accept before sending it", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const primaryActionId = "dependency-primary-action";
    const dependencyActionId = "dependency-prerequisite-action";
    const baseAction = snapshot.document_review.bundles[0].actions[0];
    snapshot.document_review.bundles = [
      {
        ...snapshot.document_review.bundles[0],
        changeset_id: "dependency-visibility-changeset",
        summary: "更新職務內容並補齊前置變更",
        actions: [
          {
            ...baseAction,
            action_id: primaryActionId,
            path: "/job_title",
            target_key: "/job_title",
            before: "採購專員",
            after: "資深採購專員",
            depends_on_action_ids: [dependencyActionId],
            atomic_subgroup_id: null,
          },
          {
            ...baseAction,
            action_id: dependencyActionId,
            path: "/work_description",
            target_key: "/work_description",
            before: null,
            after: "前置工作描述建議",
            depends_on_action_ids: [],
            atomic_subgroup_id: null,
          },
        ],
      },
    ];
    snapshot.document_review.unresolved_action_count = 2;
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
      <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(screen.getAllByText("工作描述").length).toBeGreaterThan(0);
    await user.click(screen.getByText("先修改 AI 建議再接受"));
    expect(screen.getByLabelText("工作描述")).toBeTruthy();
    const title = screen.getByLabelText("職務名稱");
    await user.clear(title);
    await user.type(title, "資深採購與供應專員");
    await user.click(screen.getByRole("button", { name: "修改後接受" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const body = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
    expect(body).toMatchObject({
      command: "edit_and_accept_changes",
      action_ids: [primaryActionId, dependencyActionId],
      edited_after_by_action_id: {
        [primaryActionId]: "資深採購與供應專員",
      },
    });
  });

  it("shows one reassignment decision at both its old and new Duty positions", async () => {
    const user = userEvent.setup();
    renderWorkspaceFixture(semanticReviewSnapshotFixture());

    await user.click(screen.getByRole("button", { name: "審核變更 2" }));
    await user.click(screen.getByRole("button", { name: "下一組" }));

    const oldDuty = screen.getByRole("region", {
      name: "Duty 2 行政管理",
    });
    const newDuty = screen.getByRole("region", {
      name: "Duty 1 客戶服務",
    });
    expect(within(oldDuty).getByText("尚待歸類的工作")).toBeTruthy();
    expect(within(oldDuty).getByText("從此職責移出")).toBeTruthy();
    expect(within(newDuty).getByText("尚待歸類的工作")).toBeTruthy();
    expect(within(newDuty).getByText("移入此職責")).toBeTruthy();
    expect(
      screen.getAllByRole("button", { name: "接受這項變更" }),
    ).toHaveLength(1);
  });

  it("shows friendly order and performance-indicator labels for semantic actions", () => {
    const snapshot = hierarchicalSnapshotFixture();
    const sourceId = snapshot.latest_source_id!;
    const duty = snapshot.current_document.duties[0];
    const task = snapshot.current_document.tasks[0];
    const knowledge = snapshot.current_document.opks.find((item) => item.kind === "knowledge")!;
    const indicator = snapshot.current_document.opks.find((item) => item.kind === "indicator")!;
    const secondIndicator = {
      ...indicator,
      item_id: "00000000-0000-0000-0000-000000000110",
      text: "申訴結案率",
      display_order: 1,
    };
    snapshot.current_document.opks.push(secondIndicator);
    snapshot.approved_document = structuredClone(snapshot.current_document);
    snapshot.approved_document.duties[0].display_order = 0;
    snapshot.current_document.duties[0].display_order = 1;
    snapshot.approved_document.tasks[0].display_order = 0;
    snapshot.current_document.tasks[0].display_order = 1;
    snapshot.approved_document.opks.find((item) => item.item_id === knowledge.item_id)!.display_order = 0;
    snapshot.current_document.opks.find((item) => item.item_id === knowledge.item_id)!.display_order = 1;
    snapshot.approved_document.opks.find((item) => item.item_id === knowledge.item_id)!.indicator_ids = [];
    snapshot.current_document.opks.find((item) => item.item_id === knowledge.item_id)!.indicator_ids = [
      indicator.item_id,
      secondIndicator.item_id,
    ];

    const baseAction = snapshot.document_review.bundles[0].actions[0];
    const action = (overrides: Partial<DocumentPatchActionView>): DocumentPatchActionView => ({
      ...baseAction,
      atomic_subgroup_id: "order-and-indicator-group",
      ...overrides,
    });
    snapshot.document_review.bundles = [
      {
        ...snapshot.document_review.bundles[0],
        changeset_id: "order-and-indicator-changeset",
        source_ids: [sourceId],
        actions: [
          action({
            action_id: "duty-order-action",
            operation: "reorder",
            path: `/duties/${duty.duty_id}/display_order`,
            target_key: `duty:${duty.duty_id}`,
            before: 0,
            after: 1,
          }),
          action({
            action_id: "task-order-action",
            operation: "reorder",
            path: `/tasks/${task.task_id}/display_order`,
            target_key: `task:${task.task_id}`,
            before: 0,
            after: 1,
          }),
          action({
            action_id: "item-order-action",
            operation: "reorder",
            path: `/opks/${knowledge.item_id}/display_order`,
            target_key: `opks:${knowledge.item_id}`,
            before: 0,
            after: 1,
          }),
          action({
            action_id: "indicator-relation-action",
            operation: "revise",
            path: `/opks/${knowledge.item_id}/indicator_ids`,
            target_key: `opks:${knowledge.item_id}:indicator_ids`,
            before: [indicator.item_id],
            after: [indicator.item_id, secondIndicator.item_id],
          }),
        ],
      },
    ];
    snapshot.document_review.unresolved_action_count = 4;

    renderWithClient(
      <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(screen.getAllByText("第 1 項").length).toBeGreaterThan(0);
    expect(screen.getAllByText("第 2 項").length).toBeGreaterThan(0);
    expect(screen.getAllByText("P 1、P 2").length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toContain(indicator.item_id);
    expect(document.body.textContent).not.toContain(secondIndicator.item_id);
  });

  it("opens the approved export baseline as a secondary read-only view", async () => {
    const user = userEvent.setup();
    renderWorkspaceFixture(semanticReviewSnapshotFixture());

    await user.click(
      screen.getByRole("button", { name: "查看匯出版本" }),
    );

    const dialog = screen.getByRole("dialog", { name: "匯出版本" });
    expect(within(dialog).getByText("每月彙整")).toBeTruthy();
    expect(within(dialog).getByText(/待審 AI 變更不會出現在匯出檔案/)).toBeTruthy();
    expect(within(dialog).queryByRole("textbox")).toBeNull();
  });

  it("collapses interview and work-map columns without hiding unassigned work", async () => {
    const user = userEvent.setup();
    renderWorkspaceFixture();
    const main = screen.getByRole("main");

    expect(main.getAttribute("data-layout")).toBe(
      "work-map-document-interview",
    );
    expect(
      screen.getByRole("region", { name: "AI 職務分析顧問對話" }),
    ).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "收合訪談" }));
    expect(main.getAttribute("data-layout")).toBe("work-map-document");
    expect(screen.getByRole("button", { name: "開啟訪談" })).toBeTruthy();
    expect(
      screen.queryByRole("region", { name: "AI 職務分析顧問對話" }),
    ).toBeNull();
    expect(screen.getByRole("region", { name: "尚未歸屬" })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "收合工作地圖" }));
    expect(main.getAttribute("data-layout")).toBe("document");
    expect(screen.getByRole("button", { name: "開啟工作地圖" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "尚未歸屬" })).toBeTruthy();
  });

  it("saves the current JD with the exact revision and workspace guards", async () => {
    const user = userEvent.setup();
    const snapshot = hierarchicalSnapshotFixture();
    snapshot.current_document.duties.forEach((duty, index) => {
      duty.display_order = (index + 1) * 10;
    });
    snapshot.current_document.tasks.forEach((task, index) => {
      task.display_order = (index + 1) * 10;
    });
    snapshot.current_document.opks.forEach((item, index) => {
      item.display_order = (index + 1) * 10;
    });
    const existingOrders = {
      duties: snapshot.current_document.duties.map((duty) => duty.display_order),
      tasks: snapshot.current_document.tasks.map((task) => task.display_order),
      opks: snapshot.current_document.opks.map((item) => item.display_order),
    };
    const response = structuredClone(snapshot);
    response.revision += 1;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWorkspaceFixture(snapshot);

    const title = screen.getByLabelText("職務名稱");
    await user.clear(title);
    await user.type(title, "資深客服專員");
    await user.click(screen.getByRole("button", { name: "儲存目前 JD" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          (call) => (call[1] as RequestInit).method === "PUT",
        ),
      ).toBe(true),
    );
    const request = fetchMock.mock.calls.find(
      (call) => (call[1] as RequestInit).method === "PUT",
    )?.[1] as RequestInit;
    const headers = new Headers(request.headers);
    const body = JSON.parse(String(request.body));
    expect(headers.get("X-Expected-Revision")).toBe(String(snapshot.revision));
    expect(body).toMatchObject({
      workspace_generation: snapshot.document_review.workspace_generation,
      workspace_digest: snapshot.document_review.workspace_digest,
    });
    expect(body.document.job_title).toBe("資深客服專員");
    expect(body.document.duties.map((duty: { display_order: number }) => duty.display_order)).toEqual(
      existingOrders.duties,
    );
    expect(body.document.tasks.map((task: { display_order: number }) => task.display_order)).toEqual(
      existingOrders.tasks,
    );
    expect(body.document.opks.map((item: { display_order: number }) => item.display_order)).toEqual(
      existingOrders.opks,
    );
  });

  it("keeps a 409 draft and offers a reload action", async () => {
    const user = userEvent.setup();
    const snapshot = hierarchicalSnapshotFixture();
    const fetchMock = vi.fn().mockImplementation(
      (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PUT") {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                type: "https://caliburn.dev/problems/job-analysis/authority-conflict",
                title: "Document revision changed",
                status: 409,
              }),
              {
                status: 409,
                headers: { "Content-Type": "application/json" },
              },
            ),
          );
        }
        const url = String(_input);
        const payload = url.endsWith("/snapshot")
          ? snapshot
          : {
              document_id: DOCUMENT_ID,
              title: "採購專員訪談",
              created_at: "2026-08-14T10:00:00Z",
              updated_at: "2026-08-14T10:00:02Z",
            };
        return Promise.resolve(
          new Response(JSON.stringify(payload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWorkspaceFixture(snapshot);

    const title = screen.getByLabelText("職務名稱");
    await user.clear(title);
    await user.type(title, "保留中的 JD 草稿");
    await user.click(screen.getByRole("button", { name: "儲存目前 JD" }));

    const editor = screen.getByRole("region", { name: "目前 JD 編輯器" });
    expect((await within(editor).findByRole("alert")).textContent).toContain(
      "草稿仍保留",
    );
    expect((screen.getByLabelText("職務名稱") as HTMLInputElement).value).toBe(
      "保留中的 JD 草稿",
    );
    expect(
      screen.getByRole("button", { name: "重新載入並捨棄草稿" }),
    ).toBeTruthy();
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
    expect(screen.queryByText(/你已延後/)).toBeNull();
  });

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

  it("keeps a pending review from blocking a new AI interview turn", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    snapshot.document_review.bundles[0].actions[0].status = "pending";

    renderWithClient(<ConsultantConversation documentId={DOCUMENT_ID} snapshot={snapshot} />);

    const answer = screen.getByLabelText("回覆顧問") as HTMLTextAreaElement;
    await user.type(answer, "我也會整理供應商名單。");
    expect(answer.disabled).toBe(false);
    expect((screen.getByRole("button", { name: "送出回答" }) as HTMLButtonElement).disabled).toBe(
      false,
    );
  });

  it("restores a non-authoritative direct-edit draft after leaving and returning", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const first = renderWithClient(
      <CurrentDocumentEditor
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
      <CurrentDocumentEditor
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
      <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={renderedSnapshot} />,
      client,
    );

    await user.click(screen.getByRole("button", { name: "接受這項變更" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    expect(
      client.getQueryData<{ revision: number }>(
        jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID),
      )?.revision,
    ).toBe(5);
  });

  it("reuses the idempotency key and decision body when a review is retried", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const response = structuredClone(snapshot);
    response.revision += 1;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            type: "https://caliburn.dev/problems/job-analysis/provider-unavailable",
            title: "Provider unavailable",
            status: 503,
          }),
          { status: 503, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(response), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    await user.click(screen.getByRole("button", { name: "接受這項變更" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("alert")).toBeTruthy();
    const firstRequest = fetchMock.mock.calls[0][1] as RequestInit;
    const firstHeaders = firstRequest.headers as Record<string, string>;

    await user.click(screen.getByRole("button", { name: "接受這項變更" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const secondRequest = fetchMock.mock.calls[1][1] as RequestInit;
    const secondHeaders = secondRequest.headers as Record<string, string>;

    expect(secondRequest.body).toBe(firstRequest.body);
    expect(secondHeaders["Idempotency-Key"]).toBe(firstHeaders["Idempotency-Key"]);
    expect(secondHeaders["X-Expected-Revision"]).toBe(
      firstHeaders["X-Expected-Revision"],
    );
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
      edit: "ui-review-edit-internal",
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
            action_id: actionIds.edit,
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
      <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(screen.getByRole("region", { name: "審核變更" })).toBeTruthy();
    expect(document.body.textContent).not.toContain(actionIds.accept);
    expect(document.body.textContent).not.toContain("write_file");
    expect(document.body.textContent).not.toContain("/candidate/");

    const decideWithKeyboard = async (name: string) => {
      const button = screen.getByRole("button", { name });
      button.focus();
      await user.keyboard("{Enter}");
    };

    await decideWithKeyboard("接受這項變更");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(
      JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body)),
    ).toMatchObject({
      command: "accept_changes",
      action_ids: [actionIds.accept],
    });

    await user.click(screen.getByRole("button", { name: "下一組" }));
    expect(screen.getByText("修改工作描述建議")).toBeTruthy();
    await user.click(screen.getByText("先修改 AI 建議再接受"));
    const description = screen.getByLabelText("工作描述");
    await user.clear(description);
    await user.type(description, "員工確認後的工作描述");
    await decideWithKeyboard("修改後接受");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(
      JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body)),
    ).toMatchObject({
      command: "edit_and_accept_changes",
      action_ids: [actionIds.edit],
      edited_after_by_action_id: {
        [actionIds.edit]: "員工確認後的工作描述",
      },
    });

    await user.click(screen.getByRole("button", { name: "下一組" }));
    expect(screen.getByText("移除不適用建議")).toBeTruthy();
    const rejectionReason = screen.getByLabelText("若要拒絕，請簡短說明原因");
    await user.type(rejectionReason, "目前正式文件仍需要這項內容");
    await decideWithKeyboard("拒絕這項變更");
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
      <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(screen.getByRole("status").textContent).toContain("AI 正在修正目前 JD 的工作內容");
    expect(screen.getByText("工作草稿有內容需要 AI 修正。")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "接受這項變更" })).toBeNull();
    expect(document.body.textContent).not.toContain("/workspace/");
  });

  it("shows conflicted diagnostics safely while keeping rejection available", async () => {
    const snapshot = consultantSnapshotFixture();
    const internalCode = "workspace-conflict-internal";
    const internalPath = "/workspace/private/00000000-0000-0000-0000-000000000099";
    snapshot.document_review = {
      ...snapshot.document_review,
      workspace_status: "conflicted",
      diagnostics: [
        {
          code: internalCode,
          path: internalPath,
          message: "目前文件內容需要重新確認，請先查看最新內容。",
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
      <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(
      screen.getByRole("status", { name: "文件內容需要重新確認" }).textContent,
    ).toContain("目前文件內容需要重新確認");
    expect(
      screen.getByText(/這項變更暫時不能接受，請先確認文件目前內容/),
    ).toBeTruthy();
    expect(
      (screen.getByRole("button", { name: "接受這項變更" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    await userEvent.setup().click(screen.getByText("先修改 AI 建議再接受"));
    expect(
      (screen.getByRole("button", { name: "修改後接受" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(
      (screen.getByRole("button", { name: "拒絕這項變更" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
    expect(document.body.textContent).not.toContain(internalCode);
    expect(document.body.textContent).not.toContain(internalPath);
    expect(document.body.textContent).not.toContain("Store");
    expect(document.body.textContent).not.toContain("00000000-0000-0000-0000-000000000099");
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
        <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={snapshot} />,
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

  it("shows pending semantic review without a defer action", () => {
    renderWithClient(
      <CurrentDocumentReview
        documentId={DOCUMENT_ID}
        snapshot={consultantSnapshotFixture()}
      />,
    );

    expect(screen.getByRole("region", { name: "審核變更" })).toBeTruthy();
    expect(screen.getByText("更新工作描述")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /稍後處理/ })).toBeNull();
  });

  it("blocks acceptance for an unsafe semantic group while leaving rejection available", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    snapshot.document_review = {
      ...snapshot.document_review,
      bundles: [
        {
          ...snapshot.document_review.bundles[0],
          acceptance_blocked: true,
        },
      ],
    };

    renderWithClient(
      <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    expect(document.body.textContent).not.toMatch(/Store|UUID/i);
    expect(
      (screen.getByRole("button", { name: "接受這項變更" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    await user.click(screen.getByText("先修改 AI 建議再接受"));
    expect(
      (screen.getByRole("button", { name: "修改後接受" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(
      (screen.getByRole("button", { name: "拒絕這項變更" }) as HTMLButtonElement).disabled,
    ).toBe(false);
  });

  it("keeps separate semantic groups as separate decisions", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    const base = snapshot.document_review.bundles[0].actions[0];
    const actionIds = [
      "00000000-0000-0000-0000-000000000020",
      "00000000-0000-0000-0000-000000000021",
    ];
    snapshot.document_review = {
      ...snapshot.document_review,
      bundles: [
        {
          ...snapshot.document_review.bundles[0],
          summary: "先接受的變更",
          actions: [{
            ...base,
            action_id: actionIds[0],
            atomic_subgroup_id: null,
            path: "/work_description",
          }],
        },
        {
          ...snapshot.document_review.bundles[0],
          changeset_id: "second-independent-review-group",
          summary: "再拒絕的變更",
          actions: [{
            ...base,
            action_id: actionIds[1],
            atomic_subgroup_id: null,
            path: "/job_title",
          }],
        },
      ],
      unresolved_action_count: 2,
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(snapshot), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    await user.click(screen.getByRole("button", { name: "接受這項變更" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(
      JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body)).action_ids,
    ).toEqual([actionIds[0]]);

    await user.click(screen.getByRole("button", { name: "下一組" }));
    await user.type(screen.getByLabelText("若要拒絕，請簡短說明原因"), "這項內容不適用目前職務");
    await user.click(screen.getByRole("button", { name: "拒絕這項變更" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(
      JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body)),
    ).toMatchObject({
      command: "reject_changes",
      action_ids: [actionIds[1]],
    });
  });

  it("clears stale selections after a 409 and refetches the current review", async () => {
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
      <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={snapshot} />,
      client,
    );

    await user.click(screen.getByRole("button", { name: "接受這項變更" }));

    await waitFor(() =>
      expect(
        client.getQueryState(jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID))
          ?.isInvalidated,
      ).toBe(true),
    );
    expect(
      screen.getAllByRole("alert").some((alert) =>
        alert.textContent?.includes("文件變更已更新，請重新查看後再決定。"),
      ),
    ).toBe(true);
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
      <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    await user.click(screen.getByText("先修改 AI 建議再接受"));
    const statement = screen.getByLabelText("主要職責內容");
    expect(document.body.textContent).not.toContain(dutyId);
    await user.clear(statement);
    await user.type(statement, "統籌採購與覆核作業");
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
      depends_on_action_ids: [],
      atomic_subgroup_id: "00000000-0000-0000-0000-000000000040",
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
      <CurrentDocumentReview documentId={DOCUMENT_ID} snapshot={snapshot} />,
    );

    await user.click(screen.getByText("先修改 AI 建議再接受"));
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

  it("keeps normal typing and retry available after an analysis failure", async () => {
    const user = userEvent.setup();
    const snapshot = consultantSnapshotFixture();
    snapshot.run = {
      ...snapshot.run!,
      status: "failed",
      completed_at: null,
      error_code: "provider_unavailable",
    };
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
    expect(screen.getByRole("button", { name: "重試同一則回答" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "更正這段原話" })).toBeNull();
    await user.type(answer, "我每月會先核對差異明細，再追查原因。");
    expect((screen.getByRole("button", { name: "送出回答" }) as HTMLButtonElement).disabled).toBe(
      false,
    );
    await user.click(screen.getByRole("button", { name: "送出回答" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toMatchObject({
      text: "我每月會先核對差異明細，再追查原因。",
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
      <CurrentDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
      client,
    );
    const title = screen.getByLabelText("職務名稱");
    await user.clear(title);
    await user.type(title, "資深採購專員");
    await user.click(screen.getByRole("button", { name: "儲存目前 JD" }));

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
