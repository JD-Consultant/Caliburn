// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CurrentJobDocumentEditor } from "./CurrentJobDocumentEditor";
import {
  DOCUMENT_ID,
  consultantSnapshotFixture,
} from "./consultantWorkspaceTestFixture";

const DUTY_ID = "00000000-0000-0000-0000-000000000101";
const TASK_ONE = "00000000-0000-0000-0000-000000000102";
const TASK_TWO = "00000000-0000-0000-0000-000000000103";
const OUTPUT_ID = "00000000-0000-0000-0000-000000000104";
const KNOWLEDGE_ID = "00000000-0000-0000-0000-000000000105";
const DUTY_TWO = "00000000-0000-0000-0000-000000000107";
const ADDED_TASK = "00000000-0000-0000-0000-000000000108";
const DELETED_TASK = "00000000-0000-0000-0000-000000000109";

function structuredSnapshot() {
  const snapshot = consultantSnapshotFixture();
  snapshot.current_document.duties = [
    { duty_id: DUTY_ID, statement: "管理採購作業", display_order: 0 },
  ];
  snapshot.current_document.tasks = [
    {
      task_id: TASK_ONE,
      duty_id: DUTY_ID,
      statement: "彙整採購需求",
      action: "彙整",
      object: "採購需求",
      purpose_result: "形成採購清單",
      context: "每月規劃時",
      frequency_text: "每月",
      responsibility_role: "primary",
      enablers: [],
      display_order: 0,
      competency_level: 3,
    },
    {
      task_id: TASK_TWO,
      duty_id: null,
      statement: "追蹤供應商交期",
      action: "追蹤",
      object: "供應商交期",
      purpose_result: null,
      context: null,
      frequency_text: "每週",
      responsibility_role: "shared",
      enablers: [],
      display_order: 1,
      competency_level: null,
    },
  ];
  snapshot.current_document.opks = [
    {
      item_id: OUTPUT_ID,
      kind: "output",
      text: "採購需求清單",
      display_order: 0,
      task_ids: [TASK_ONE],
      indicator_ids: [],
      evidence_source_ids: [snapshot.latest_source_id!],
    },
    {
      item_id: KNOWLEDGE_ID,
      kind: "knowledge",
      text: "採購流程知識",
      display_order: 0,
      task_ids: [TASK_ONE, TASK_TWO],
      indicator_ids: [],
      evidence_source_ids: [snapshot.latest_source_id!],
    },
    ...snapshot.current_document.opks,
  ];
  return snapshot;
}

function semanticSnapshot() {
  const snapshot = structuredSnapshot();
  snapshot.current_document.duties.push({
    duty_id: DUTY_TWO,
    statement: "教育宣導",
    display_order: 1,
  });
  const baselineTask = structuredClone(snapshot.current_document.tasks[0]);
  baselineTask.statement = "每月彙整法規";
  baselineTask.frequency_text = "每月";
  const deletedTask = {
    ...structuredClone(baselineTask),
    task_id: DELETED_TASK,
    statement: "寄送紙本通知",
    display_order: 1,
  };
  snapshot.approved_document = structuredClone(snapshot.current_document);
  snapshot.approved_document.tasks = [
    baselineTask,
    structuredClone(snapshot.current_document.tasks[1]),
    deletedTask,
  ];
  snapshot.current_document.tasks = [
    {
      ...snapshot.current_document.tasks[0],
      duty_id: DUTY_TWO,
      statement: "每週追蹤法規",
      frequency_text: "每週",
    },
    snapshot.current_document.tasks[1],
    {
      ...structuredClone(snapshot.current_document.tasks[0]),
      task_id: ADDED_TASK,
      duty_id: DUTY_ID,
      statement: "整理教育問答",
      display_order: 1,
    },
  ];
  const sourceId = snapshot.latest_source_id!;
  const moveActionId = "00000000-0000-0000-0000-000000000111";
  const action = (
    actionId: string,
    operation: "add" | "revise" | "withdraw" | "reassign",
    path: string,
    before: unknown,
    after: unknown,
    dependsOn: string[] = [],
  ) => ({
    action_id: actionId,
    operation,
    path,
    target_key: path,
    before,
    after,
    source_ids: [sourceId],
    quote_anchors: [
      { source_id: sourceId, start: 0, end: 8, quote: "改成每週追蹤" },
    ],
    read_set: [],
    depends_on_action_ids: dependsOn,
    atomic_subgroup_id: null,
    affected_work_ids: [],
    blocks_dependent_analysis: false,
    status: "pending" as const,
  });
  snapshot.document_review.bundles = [
    {
      changeset_id: "00000000-0000-0000-0000-000000000121",
      summary: "移動並修正法規追蹤工作",
      source_ids: [sourceId],
      created_revision: snapshot.revision,
      acceptance_blocked: false,
      actions: [
        action(
          moveActionId,
          "reassign",
          `/tasks/${TASK_ONE}/duty_id`,
          DUTY_ID,
          DUTY_TWO,
        ),
        action(
          "00000000-0000-0000-0000-000000000112",
          "revise",
          `/tasks/${TASK_ONE}/statement`,
          "每月彙整法規",
          "每週追蹤法規",
          [moveActionId],
        ),
      ],
    },
    {
      changeset_id: "00000000-0000-0000-0000-000000000122",
      summary: "新增教育問答工作",
      source_ids: [sourceId],
      created_revision: snapshot.revision,
      acceptance_blocked: false,
      actions: [
        action(
          "00000000-0000-0000-0000-000000000113",
          "add",
          "/tasks",
          null,
          snapshot.current_document.tasks[2],
        ),
      ],
    },
    {
      changeset_id: "00000000-0000-0000-0000-000000000123",
      summary: "移除紙本通知工作",
      source_ids: [sourceId],
      created_revision: snapshot.revision,
      acceptance_blocked: false,
      actions: [
        action(
          "00000000-0000-0000-0000-000000000114",
          "withdraw",
          `/tasks/${DELETED_TASK}`,
          deletedTask,
          null,
        ),
      ],
    },
  ];
  snapshot.document_review.unresolved_action_count = 4;
  snapshot.employee_messages = [
    {
      source_id: sourceId,
      text: "我剛才說錯，應該改成每週追蹤，也不再寄紙本通知。",
      created_at: "2026-08-27T10:00:00Z",
      processing_status: "committed",
    },
  ];
  return snapshot;
}

function renderWithClient(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const result = render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
  return {
    ...result,
    rerenderWithClient(next: ReactNode) {
      result.rerender(
        <QueryClientProvider client={client}>{next}</QueryClientProvider>,
      );
    },
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("one visible current JD editor", () => {
  it("renders document header, Duty → Task → work details + OPKS, unassigned work and document-level A", () => {
    const snapshot = structuredSnapshot();

    renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    expect((screen.getByLabelText("職務名稱") as HTMLInputElement).value).toBe(
      "採購專員",
    );
    expect(
      screen.getByRole("region", { name: "職責 1 管理採購作業" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("region", { name: "任務 1 彙整採購需求" }),
    ).toBeTruthy();
    expect(screen.getByRole("region", { name: "尚未歸屬任務" })).toBeTruthy();
    expect(
      screen.getByRole("region", { name: "任務 1 追蹤供應商交期" }),
    ).toBeTruthy();
    expect(screen.getByRole("region", { name: "文件層態度 A" })).toBeTruthy();
    expect(
      within(
        screen.getByRole("region", { name: "文件層態度 A" }),
      ).getByDisplayValue("謹慎"),
    ).toBeTruthy();
    expect(document.getElementById(`duty-${DUTY_ID}`)).toBeTruthy();
    expect(document.getElementById(`task-${TASK_ONE}`)).toBeTruthy();
    expect(document.getElementById(`task-${TASK_TWO}`)).toBeTruthy();
    expect(document.body.textContent).not.toContain(DUTY_ID);
    expect(document.body.textContent).not.toContain(TASK_ONE);
  });

  it("projects one canonical K/S under every linked Task and keeps zero-link items in relinking management", () => {
    const snapshot = structuredSnapshot();
    snapshot.current_document.opks.push({
      item_id: "00000000-0000-0000-0000-000000000106",
      kind: "skill",
      text: "供應商溝通技巧",
      display_order: 0,
      task_ids: [],
      indicator_ids: [],
      evidence_source_ids: [],
    });

    renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    expect(screen.getAllByDisplayValue("採購流程知識")).toHaveLength(2);
    expect(screen.getByText("採購流程知識")).toBeTruthy();
    expect(screen.getByText("待重新連結 K／S")).toBeTruthy();
    expect(screen.getAllByText("供應商溝通技巧")).toHaveLength(2);
  });

  it("renders update, add, delete and move semantics inside the same JD skeleton", () => {
    const snapshot = semanticSnapshot();
    renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    const currentStatement = screen.getByDisplayValue("每週追蹤法規");
    expect(currentStatement.closest("[data-review-current='true']")).toBeTruthy();
    expect(
      screen
        .getAllByText("每月彙整法規")
        .some((node) => node.closest("del") !== null),
    ).toBe(true);

    const added = screen.getByRole("region", {
      name: "任務 1 整理教育問答",
    });
    expect(added.closest("[data-review-operation='add']")).toBeTruthy();
    expect(
      screen.getByText("寄送紙本通知").closest("[data-review-operation='delete']"),
    ).toBeTruthy();

    const movedCurrent = screen.getByRole("region", {
      name: "任務 1 每週追蹤法規",
    });
    expect(movedCurrent.closest("[data-review-operation='move']")).toBeTruthy();
    expect(
      document.querySelector(
        `[data-review-location='from'][data-task-id='${TASK_ONE}']`,
      ),
    ).toBeTruthy();
  });

  it("autosaves edits to green current content without deciding its review group", async () => {
    const snapshot = semanticSnapshot();
    const response = structuredClone(snapshot);
    response.revision += 1;
    response.current_document.tasks[0].statement = "每週主動追蹤法規";
    response.document_review.workspace_generation += 1;
    response.document_review.workspace_digest =
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    const field = screen.getByDisplayValue("每週追蹤法規");
    fireEvent.change(field, { target: { value: "每週主動追蹤法規" } });
    fireEvent.blur(field);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(String(fetchMock.mock.calls[0][0])).toContain("/current-document");
    expect(String(fetchMock.mock.calls[0][0])).not.toContain("/reviews/");
    expect(
      screen.getByRole("button", {
        name: "審核修改：任務 1 敘述",
      }),
    ).toBeTruthy();
  });

  it("keeps structured Task and K/S relationship changes reviewable without a separate panel", () => {
    const snapshot = semanticSnapshot();
    const template = snapshot.document_review.bundles[0].actions[1];
    snapshot.approved_document.tasks[0].responsibility_role = "primary";
    snapshot.current_document.tasks[0].responsibility_role = "shared";
    snapshot.current_document.tasks[0].enablers = [
      { kind: "method", name: "使用法規追蹤表" },
    ];
    const knowledge = snapshot.current_document.opks.find(
      (item) => item.item_id === KNOWLEDGE_ID,
    )!;
    const previousTaskIds = [...knowledge.task_ids];
    knowledge.task_ids = [TASK_ONE];
    snapshot.document_review.bundles.push({
      changeset_id: "00000000-0000-0000-0000-000000000124",
      summary: "補充責任與工作方法",
      source_ids: [snapshot.latest_source_id!],
      created_revision: snapshot.revision,
      acceptance_blocked: false,
      actions: [
        {
          ...template,
          action_id: "00000000-0000-0000-0000-000000000115",
          path: `/tasks/${TASK_ONE}/responsibility_role`,
          target_key: `/tasks/${TASK_ONE}/responsibility_role`,
          before: "primary",
          after: "shared",
          depends_on_action_ids: [],
        },
        {
          ...template,
          action_id: "00000000-0000-0000-0000-000000000116",
          path: `/tasks/${TASK_ONE}/enablers`,
          target_key: `/tasks/${TASK_ONE}/enablers`,
          before: [],
          after: [{ kind: "method", name: "使用法規追蹤表" }],
          depends_on_action_ids: [],
        },
      ],
    });
    snapshot.document_review.bundles.push({
      changeset_id: "00000000-0000-0000-0000-000000000125",
      summary: "調整共用知識的任務連結",
      source_ids: [snapshot.latest_source_id!],
      created_revision: snapshot.revision,
      acceptance_blocked: false,
      actions: [
        {
          ...template,
          action_id: "00000000-0000-0000-0000-000000000117",
          path: `/opks/${KNOWLEDGE_ID}/task_ids`,
          target_key: `/opks/${KNOWLEDGE_ID}/task_ids`,
          before: previousTaskIds,
          after: [TASK_ONE],
          depends_on_action_ids: [],
        },
      ],
    });

    renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    expect(
      screen.getByRole("button", {
        name: "審核修改：任務 1 責任角色",
      }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", {
        name: "審核修改：任務 1 工具／方法／促成條件",
      }),
    ).toBeTruthy();
    expect(
      screen.getAllByRole("button", {
        name: /審核修改：知識 K/,
      }).length,
    ).toBeGreaterThan(0);
  });

  it("autosaves visible field edits with fresh authority guards and no Save button", async () => {
    const snapshot = structuredSnapshot();
    const response = structuredClone(snapshot);
    response.revision += 1;
    response.current_document.job_title = "資深採購專員";
    response.approved_document.job_title = "資深採購專員";
    response.document_review.workspace_generation += 1;
    response.document_review.workspace_digest =
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    let finishRequest!: (value: Response) => void;
    const fetchMock = vi.fn().mockImplementation(() => {
      if (fetchMock.mock.calls.length === 1) {
        return new Promise<Response>((resolve) => {
          finishRequest = resolve;
        });
      }
      return Promise.resolve(
        new Response(JSON.stringify(response), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    expect(screen.queryByRole("button", { name: /儲存/ })).toBeNull();
    const title = screen.getByLabelText("職務名稱");
    fireEvent.change(title, { target: { value: "資深採購專員" } });
    fireEvent.blur(title);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await new Promise((resolve) => setTimeout(resolve, 750));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("status").textContent).toContain("儲存中");

    const [url, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain(`/${DOCUMENT_ID}/current-document`);
    expect(request.headers).toMatchObject({
      "X-Expected-Revision": String(snapshot.revision),
    });
    expect(JSON.parse(String(request.body))).toMatchObject({
      document: { job_title: "資深採購專員" },
      workspace_generation: snapshot.document_review.workspace_generation,
      workspace_digest: snapshot.document_review.workspace_digest,
    });

    finishRequest(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain("已儲存"),
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps failed field values visible and retries the same current document", async () => {
    const user = userEvent.setup();
    const snapshot = structuredSnapshot();
    const response = structuredClone(snapshot);
    response.revision += 1;
    response.current_document.job_title = "資深採購專員";
    response.document_review.workspace_generation += 1;
    response.document_review.workspace_digest =
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "暫時無法儲存" }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(response), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    const title = screen.getByLabelText("職務名稱");
    fireEvent.change(title, { target: { value: "資深採購專員" } });
    fireEvent.blur(title);

    expect((await screen.findByRole("alert")).textContent).toContain(
      "你的欄位內容仍保留在畫面上",
    );
    expect((title as HTMLInputElement).value).toBe("資深採購專員");
    expect(screen.getByRole("status").textContent).toContain("尚未儲存");

    await user.click(screen.getByRole("button", { name: "重試儲存" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain("已儲存"),
    );
  });

  it("loads the newer server document after a stale conflict without discarding the rejected edit", async () => {
    const user = userEvent.setup();
    const snapshot = structuredSnapshot();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          type: "https://caliburn.dev/problems/job-analysis/authority-conflict",
          title: "Document revision changed",
          status: 409,
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const view = renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    const title = screen.getByLabelText("職務名稱");
    fireEvent.change(title, { target: { value: "員工剛才輸入的名稱" } });
    fireEvent.blur(title);
    await screen.findByRole("alert");

    const newer = structuredClone(snapshot);
    newer.revision += 1;
    newer.current_document.job_title = "伺服器上的較新名稱";
    newer.document_review.workspace_generation += 1;
    newer.document_review.workspace_digest =
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    view.rerenderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={newer}
        onDirtyChange={() => undefined}
      />,
    );

    await waitFor(() =>
      expect((screen.getByLabelText("職務名稱") as HTMLInputElement).value).toBe(
        "伺服器上的較新名稱",
      ),
    );
    expect(screen.getByRole("alert").textContent).toContain("沒有自動合併");

    await user.click(screen.getByRole("button", { name: "取回剛才內容" }));
    expect((screen.getByLabelText("職務名稱") as HTMLInputElement).value).toBe(
      "員工剛才輸入的名稱",
    );
    expect(screen.getByRole("status").textContent).toContain("尚未儲存");
  });

  it("queues rapid edits and sends the second document with guards from the first response", async () => {
    const snapshot = structuredSnapshot();
    const firstResponse = structuredClone(snapshot);
    firstResponse.revision += 1;
    firstResponse.current_document.job_title = "採購顧問";
    firstResponse.document_review.workspace_generation += 1;
    firstResponse.document_review.workspace_digest =
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const secondResponse = structuredClone(firstResponse);
    secondResponse.revision += 1;
    secondResponse.current_document.job_title = "資深採購顧問";
    secondResponse.document_review.workspace_generation += 1;
    secondResponse.document_review.workspace_digest =
      "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
    let finishFirst!: (value: Response) => void;
    const fetchMock = vi.fn().mockImplementation(() => {
      if (fetchMock.mock.calls.length === 1) {
        return new Promise<Response>((resolve) => {
          finishFirst = resolve;
        });
      }
      return Promise.resolve(
        new Response(JSON.stringify(secondResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    const title = screen.getByLabelText("職務名稱");
    fireEvent.change(title, { target: { value: "採購顧問" } });
    fireEvent.blur(title);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fireEvent.change(title, { target: { value: "資深採購顧問" } });
    fireEvent.blur(title);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    finishFirst(
      new Response(JSON.stringify(firstResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const [, secondRequest] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(secondRequest.headers).toMatchObject({
      "X-Expected-Revision": String(firstResponse.revision),
    });
    expect(JSON.parse(String(secondRequest.body))).toMatchObject({
      document: { job_title: "資深採購顧問" },
      workspace_generation: firstResponse.document_review.workspace_generation,
      workspace_digest: firstResponse.document_review.workspace_digest,
    });
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain("已儲存"),
    );
  });

  it("syncs newer server values into clean fields without overwriting a local dirty field", () => {
    const snapshot = structuredSnapshot();
    const view = renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    fireEvent.change(screen.getByLabelText("職務名稱"), {
      target: { value: "員工正在修改的名稱" },
    });
    const newer = structuredClone(snapshot);
    newer.revision += 1;
    newer.current_document.industry_name = "伺服器更新的產業";
    newer.document_review.workspace_generation += 1;
    newer.document_review.workspace_digest =
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    view.rerenderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={newer}
        onDirtyChange={() => undefined}
      />,
    );

    expect((screen.getByLabelText("職務名稱") as HTMLInputElement).value).toBe(
      "員工正在修改的名稱",
    );
    expect((screen.getByLabelText("行業名稱") as HTMLInputElement).value).toBe(
      "伺服器更新的產業",
    );
  });

  it("uses a typed structural command for adding a Duty and offers bounded Undo", async () => {
    const user = userEvent.setup();
    const snapshot = structuredSnapshot();
    const response = structuredClone(snapshot);
    response.revision += 1;
    response.current_document.duties.push({
      duty_id: "00000000-0000-0000-0000-000000000107",
      statement: "新職責",
      display_order: 1,
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ snapshot: response, undo_token: "undo-duty-1" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    await user.click(screen.getByRole("button", { name: "新增職責" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toMatchObject({
      command: { operation: "create_duty", name: "新職責" },
    });
    expect(
      await screen.findByRole("button", { name: "復原上一個操作" }),
    ).toBeTruthy();
  });

  it("locks editing for the whole structural operation, including its autosave flush", async () => {
    const user = userEvent.setup();
    const snapshot = structuredSnapshot();
    const saved = structuredClone(snapshot);
    saved.revision += 1;
    saved.current_document.job_title = "已編輯名稱";
    saved.document_review.workspace_generation += 1;
    saved.document_review.workspace_digest =
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const commanded = structuredClone(saved);
    commanded.revision += 1;
    commanded.current_document.duties.push({
      duty_id: "00000000-0000-0000-0000-000000000107",
      statement: "新職責",
      display_order: 1,
    });
    commanded.document_review.workspace_generation += 1;
    commanded.document_review.workspace_digest =
      "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
    let finishSave!: (value: Response) => void;
    let finishCommand!: (value: Response) => void;
    const fetchMock = vi.fn().mockImplementation(() => {
      if (fetchMock.mock.calls.length === 1) {
        return new Promise<Response>((resolve) => {
          finishSave = resolve;
        });
      }
      return new Promise<Response>((resolve) => {
        finishCommand = resolve;
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    const title = screen.getByLabelText("職務名稱") as HTMLInputElement;
    fireEvent.change(title, { target: { value: "已編輯名稱" } });
    fireEvent.blur(title);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "新增職責" }));

    expect(title.readOnly).toBe(true);
    await user.type(title, "不應寫入");
    expect(title.value).toBe("已編輯名稱");

    finishSave(
      new Response(JSON.stringify(saved), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(title.readOnly).toBe(true);

    finishCommand(
      new Response(
        JSON.stringify({ snapshot: commanded, undo_token: "undo-duty-1" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    await waitFor(() => expect(title.readOnly).toBe(false));
    expect(title.value).toBe("已編輯名稱");
  });

  it("previews a high-impact cascade and applies it only after explicit confirmation", async () => {
    const user = userEvent.setup();
    const snapshot = structuredSnapshot();
    const response = structuredClone(snapshot);
    response.revision += 1;
    response.current_document.duties = [];
    response.current_document.tasks = response.current_document.tasks.filter(
      (task) => task.duty_id === null,
    );
    response.current_document.opks = response.current_document.opks.filter(
      (item) => item.kind === "attitude" || item.kind === "knowledge",
    );
    response.document_review.workspace_generation += 1;
    response.document_review.workspace_digest =
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const previewDigest =
      "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            preview_digest: previewDigest,
            confirmation_required: true,
            duty_count: 1,
            task_count: 1,
            output_count: 1,
            indicator_count: 0,
            shared_item_count: 1,
            shared_link_count: 1,
            affected_names: ["管理採購作業", "彙整採購需求"],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ snapshot: response, undo_token: "undo-cascade-1" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <CurrentJobDocumentEditor
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        onDirtyChange={() => undefined}
      />,
    );

    await user.click(screen.getByRole("button", { name: "職責 1 操作" }));
    await user.click(await screen.findByText("刪除職責與內容"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(String(fetchMock.mock.calls[0][0])).toContain("/commands/preview");
    expect(screen.getByText("刪除這項職責與內容？")).toBeTruthy();
    expect(screen.getAllByText("彙整採購需求").length).toBeGreaterThan(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "確認刪除" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(String(fetchMock.mock.calls[1][0])).toMatch(/\/commands$/);
    expect(JSON.parse(String(fetchMock.mock.calls[1][1].body))).toMatchObject({
      command: {
        operation: "cascade_delete_duty",
        duty_id: DUTY_ID,
        preview_digest: previewDigest,
      },
    });
  });
});
