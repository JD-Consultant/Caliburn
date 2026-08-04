import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  JdHeaderWrite,
  JdTaskWrite,
  OpksItemWrite,
  OpksProposalDecisionWrite,
  ProposalDecisionWrite,
} from "@caliburn/job-analysis-contract";

import {
  JobAnalysisApiError,
  createDocument,
  addOpksItem,
  addTask,
  decideOpksProposal,
  deleteTask,
  deleteOpksItem,
  editTask,
  editOpksItem,
  generateOpksProposals,
  getDocument,
  getConsultation,
  jobAnalysisProblemMessage,
  listDocuments,
  putDocument,
  putJdHeader,
  reorderTasks,
  submitEmployeeTurn,
  decideProposal,
} from "./jobAnalysisApi";

const DOCUMENT_ID = "00000000-0000-0000-0000-000000000045";

afterEach(() => {
  vi.unstubAllGlobals();
});

function response(body: unknown, status = 200, contentType = "application/json") {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": contentType },
  });
}

describe("job-analysis document client", () => {
  it("uses only the greenfield document endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(
        response({
          document_id: DOCUMENT_ID,
          title: "門市營運專員",
          updated_at: "2026-07-30T10:00:00Z",
        }),
      )
      .mockResolvedValueOnce(
        response({
          document_id: DOCUMENT_ID,
          title: "門市營運專員",
          updated_at: "2026-07-30T10:00:00Z",
          tasks: [],
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await listDocuments();
    await putDocument(DOCUMENT_ID, "門市營運專員");
    await getDocument(DOCUMENT_ID);

    expect(fetchMock.mock.calls[0]).toEqual([
      "http://127.0.0.1:8001/api/v1/job-analysis/documents",
      expect.objectContaining({ method: "GET" }),
    ]);
    expect(fetchMock.mock.calls[1]).toEqual([
      `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}`,
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ title: "門市營運專員" }),
      }),
    ]);
    expect(fetchMock.mock.calls[1][1].headers).not.toHaveProperty(
      "Idempotency-Key",
    );
    expect(fetchMock.mock.calls[2][0]).toBe(
      `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}`,
    );
  });

  it("creates with the caller-provided local identity", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response({
        document_id: DOCUMENT_ID,
        title: "設備維護工程師",
        updated_at: "2026-07-30T10:00:00Z",
      }, 201),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createDocument("設備維護工程師", DOCUMENT_ID);

    expect(fetchMock.mock.calls[0][0]).toContain(DOCUMENT_ID);
  });

  it("keeps a typed problem and ignores unknown extensions", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          {
            type: "https://caliburn.dev/problems/job-analysis/document-not-found",
            title: "Document not found",
            status: 404,
            future_extension: { anything: true },
          },
          404,
          "application/problem+json",
        ),
      ),
    );

    const error = await getDocument(DOCUMENT_ID).catch((value) => value);

    expect(error).toBeInstanceOf(JobAnalysisApiError);
    expect(error.problem?.type).toBe(
      "https://caliburn.dev/problems/job-analysis/document-not-found",
    );
  });
});

describe("Current JD Task client", () => {
  const task: JdTaskWrite = {
    statement: "盤點耗材",
    purpose_result: null,
    context: null,
    frequency_text: null,
    responsibility_role: null,
    enablers: [],
  };

  it("uses the caller-owned retry key for every mutation", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ...task, task_id: "task-1", display_order: 0 }, 201))
      .mockResolvedValueOnce(response({ ...task, task_id: "task-1", display_order: 0 }))
      .mockResolvedValueOnce(response([{ ...task, task_id: "task-1", display_order: 0 }]))
      .mockResolvedValueOnce(response(null, 204));
    vi.stubGlobal("fetch", fetchMock);

    await addTask(DOCUMENT_ID, task, "operation-1");
    await editTask(DOCUMENT_ID, "task-1", task, "operation-1");
    await reorderTasks(DOCUMENT_ID, ["task-1"], "operation-1");
    await deleteTask(DOCUMENT_ID, "task-1", "operation-1");

    for (const call of fetchMock.mock.calls) {
      expect(call[1].headers).toMatchObject({ "Idempotency-Key": "operation-1" });
    }
    expect(fetchMock.mock.calls.map((call) => [call[1].method, call[0]])).toEqual([
      ["POST", `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/tasks`],
      ["PUT", `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/tasks/task-1`],
      ["PUT", `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/task-order`],
      ["DELETE", `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/tasks/task-1`],
    ]);
  });
});

describe("JD header client", () => {
  const header: JdHeaderWrite = {
    competency_name: "資訊安全維運人員",
    occupation_category_name: null,
    occupation_name: null,
    occupation_code: null,
    industry_name: null,
    industry_code: null,
    work_description: "維運企業資訊安全設備並處理資安事件。",
    competency_level: 4,
    notes: null,
  };

  it("PUTs the header with the caller-owned retry key", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(header));
    vi.stubGlobal("fetch", fetchMock);

    await putJdHeader(DOCUMENT_ID, header, "header-1");

    const [url, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("PUT");
    expect(url).toBe(
      `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/jd-header`,
    );
    expect(init.headers).toMatchObject({ "Idempotency-Key": "header-1" });
    expect(JSON.parse(init.body)).toEqual(header);
  });

  it("surfaces a rejected no-op edit as a readable message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        response(
          {
            type: "https://caliburn.dev/problems/job-analysis/invalid-request",
            title: "Invalid request",
            status: 422,
          },
          422,
        ),
      ),
    );

    await expect(putJdHeader(DOCUMENT_ID, header, "header-1")).rejects.toThrow(
      "請檢查輸入內容",
    );
  });
});

describe("Current JD OPKS client", () => {
  const item: OpksItemWrite = {
    entity_kind: "knowledge",
    text: "營運指標定義",
    task_refs: ["task-1"],
    indicator_refs: [],
  };

  it("uses the explicit OPKS authoring, generation, and decision routes", async () => {
    const view = {
      ...item,
      entity_id: "knowledge-1",
      evidence_quotes: [],
    };
    const generation = {
      outcome: "proposed",
      proposal_ids: ["generation-1-op0"],
    };
    const consultation = {
      document: {
        document_id: DOCUMENT_ID,
        title: "門市營運專員",
        updated_at: "2026-08-01T10:00:00Z",
      },
      conversation: [],
      active_question: null,
      proposals: [],
      opks_proposals: [],
      tasks: [],
      opks_items: [],
    };
    const decision: OpksProposalDecisionWrite = { decision: "accepted" };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(view, 201))
      .mockResolvedValueOnce(response(view))
      .mockResolvedValueOnce(response(null, 204))
      .mockResolvedValueOnce(response(generation))
      .mockResolvedValueOnce(response(consultation));
    vi.stubGlobal("fetch", fetchMock);

    await addOpksItem(DOCUMENT_ID, item, "opks-add");
    await editOpksItem(DOCUMENT_ID, "knowledge-1", item, "opks-edit");
    await deleteOpksItem(DOCUMENT_ID, "knowledge-1", "opks-delete");
    await generateOpksProposals(DOCUMENT_ID, "task-1", "opks-generate");
    await decideOpksProposal(
      DOCUMENT_ID,
      "proposal-1",
      "opks-decide",
      decision,
    );

    expect(fetchMock.mock.calls.map((call) => [call[1].method, call[0]])).toEqual([
      ["POST", `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/opks`],
      ["PUT", `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/opks/knowledge-1`],
      ["DELETE", `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/opks/knowledge-1`],
      ["POST", `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/tasks/task-1/opks-proposals`],
      ["POST", `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/opks-proposals/proposal-1/decisions`],
    ]);
    expect(fetchMock.mock.calls.map((call) => call[1].headers)).toEqual(
      ["opks-add", "opks-edit", "opks-delete", "opks-generate", "opks-decide"].map(
        (key) => expect.objectContaining({ "Idempotency-Key": key }),
      ),
    );
    expect(fetchMock.mock.calls[4][1].body).toBe(JSON.stringify(decision));
  });
});

describe("jobAnalysisProblemMessage", () => {
  it.each([
    ["document-not-found", "找不到這份職務說明書"],
    ["task-not-found", "找不到這項工作"],
    ["opks-item-not-found", "找不到這項職務內容"],
    ["idempotency-conflict", "這次操作內容已經改變"],
    ["authority-conflict", "內容已有更新"],
    ["invalid-task-order", "工作順序不正確"],
    ["invalid-request", "請檢查輸入內容"],
    ["proposal-not-found", "找不到這項提案"],
    ["consultant-unavailable", "顧問暫時無法完成分析，請稍後重試"],
  ])("maps %s without parsing detail", (suffix, message) => {
    expect(
      jobAnalysisProblemMessage(
        `https://caliburn.dev/problems/job-analysis/${suffix}`,
      ),
    ).toBe(message);
  });

  it("uses one generic fallback for a future problem type", () => {
    expect(jobAnalysisProblemMessage("https://example.test/future")).toBe(
      "操作失敗，請稍後再試",
    );
  });
});

describe("consultant loop client", () => {
  const consultation = {
    document: {
      document_id: DOCUMENT_ID,
      title: "門市營運專員",
      updated_at: "2026-07-30T10:00:00Z",
    },
    conversation: [],
    active_question: null,
    proposals: [],
    tasks: [],
  };

  it("uses only the new consultation routes and caller-owned retry keys", async () => {
    const decision: ProposalDecisionWrite = { decision: "accepted" };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(consultation))
      .mockResolvedValueOnce(response(consultation))
      .mockResolvedValueOnce(response(consultation));
    vi.stubGlobal("fetch", fetchMock);

    await getConsultation(DOCUMENT_ID);
    await submitEmployeeTurn(DOCUMENT_ID, "turn-op-1", "我每週彙整營運週報");
    await decideProposal(DOCUMENT_ID, "proposal-1", "decision-op-1", decision);

    expect(fetchMock.mock.calls.map((call) => [call[1].method, call[0]])).toEqual([
      ["GET", `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/consultation`],
      ["POST", `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/turns`],
      ["POST", `http://127.0.0.1:8001/api/v1/job-analysis/documents/${DOCUMENT_ID}/proposals/proposal-1/decisions`],
    ]);
    expect(fetchMock.mock.calls[1][1]).toMatchObject({
      headers: expect.objectContaining({ "Idempotency-Key": "turn-op-1" }),
      body: JSON.stringify({ text: "我每週彙整營運週報" }),
    });
    expect(fetchMock.mock.calls[2][1]).toMatchObject({
      headers: expect.objectContaining({ "Idempotency-Key": "decision-op-1" }),
      body: JSON.stringify(decision),
    });
  });
});
