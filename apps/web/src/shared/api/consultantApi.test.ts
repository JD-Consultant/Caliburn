import { afterEach, describe, expect, it, vi } from "vitest";

import {
  answerRequiredClarification,
  consultantEventsUrl,
  createConsultantDocument,
  decideUnderstandingCalibration,
  deleteConsultantDocument,
  editCurrentDocument,
  editApprovedDocument,
  exportConsultantDocument,
  getConsultantSnapshot,
  listConsultantDocuments,
  applyCurrentDocumentCommand,
  previewCurrentDocumentCommand,
  reviewDocumentChanges,
  retryConsultantRun,
  submitConsultantAnswer,
} from "./jobAnalysisApi";

const DOCUMENT_ID = "00000000-0000-0000-0000-000000000001";
const ENTITY_ID = "00000000-0000-0000-0000-000000000002";

afterEach(() => vi.unstubAllGlobals());

function jsonResponse(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("purpose-first consultant API client", () => {
  it("uses the consultant catalog, durable snapshot and source-first answer endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ documents: [] }))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            document_id: DOCUMENT_ID,
            title: "採購",
            created_at: "now",
            updated_at: "now",
          },
          201,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse({ document_id: DOCUMENT_ID, revision: 0 }),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          { run_id: ENTITY_ID, source_id: ENTITY_ID, status: "source_saved" },
          202,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          { run_id: ENTITY_ID, source_id: ENTITY_ID, status: "source_saved" },
          202,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(null, 204));
    vi.stubGlobal("fetch", fetchMock);

    await listConsultantDocuments();
    await createConsultantDocument("採購", "create-1");
    await getConsultantSnapshot(DOCUMENT_ID);
    await submitConsultantAnswer(DOCUMENT_ID, "answer-1", {
      text: "我整理需求。",
    });
    await retryConsultantRun(DOCUMENT_ID, ENTITY_ID);
    await deleteConsultantDocument(DOCUMENT_ID);

    expect(
      fetchMock.mock.calls.map((call) => [call[1].method, call[0]]),
    ).toEqual([
      ["GET", "http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents"],
      [
        "POST",
        "http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents",
      ],
      [
        "GET",
        `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/snapshot`,
      ],
      [
        "POST",
        `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/answers`,
      ],
      [
        "POST",
        `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/runs/${ENTITY_ID}/retry`,
      ],
      [
        "DELETE",
        `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}`,
      ],
    ]);
    expect(fetchMock.mock.calls[1][1].headers).toMatchObject({
      "Idempotency-Key": "create-1",
    });
    expect(fetchMock.mock.calls[3][1].headers).toMatchObject({
      "Idempotency-Key": "answer-1",
    });
  });

  it("keeps review, calibration, clarification and direct edit as distinct employee commands", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(
          jsonResponse({ document_id: DOCUMENT_ID, revision: 4 }),
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await reviewDocumentChanges(DOCUMENT_ID, ENTITY_ID, "review-1", 3, {
      command: "accept_changes",
      action_ids: [ENTITY_ID],
      rejection_reason: null,
    });
    await decideUnderstandingCalibration(
      DOCUMENT_ID,
      ENTITY_ID,
      "calibrate-1",
      3,
      {
        decision: "confirm",
        employee_text: "理解正確",
      },
    );
    await answerRequiredClarification(DOCUMENT_ID, ENTITY_ID, "clarify-1", 3, {
      text: "最後由我核准",
    });
    await editApprovedDocument(DOCUMENT_ID, "edit-1", 3, {
      schema_version: 1,
      document_id: DOCUMENT_ID,
      job_title: "採購專員",
      occupation_category_name: null,
      occupation_name: null,
      occupation_code: null,
      industry_name: null,
      industry_code: null,
      work_description: null,
      competency_level: null,
      notes: null,
      duties: [],
      tasks: [],
      opks: [],
    });

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/reviews/${ENTITY_ID}`,
      `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/calibrations/${ENTITY_ID}`,
      `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/clarifications/${ENTITY_ID}`,
      `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/approved-document`,
    ]);
    for (const call of fetchMock.mock.calls) {
      expect(call[1].headers).toMatchObject({ "X-Expected-Revision": "3" });
    }
  });

  it("sends current autosave and lifecycle intents through guarded authority endpoints", async () => {
    const document = {
      schema_version: 1 as const,
      document_id: DOCUMENT_ID,
      job_title: "採購專員",
      occupation_category_name: null,
      occupation_name: null,
      occupation_code: null,
      industry_name: null,
      industry_code: null,
      work_description: null,
      competency_level: null,
      notes: null,
      duties: [],
      tasks: [],
      opks: [],
    };
    const guards = {
      expectedRevision: 3,
      workspaceGeneration: 4,
      workspaceDigest:
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    };
    const command = { operation: "create_duty" as const, name: "採購管理" };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ document_id: DOCUMENT_ID, revision: 4 }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          preview_digest:
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
          confirmation_required: false,
          duty_count: 0,
          task_count: 0,
          output_count: 0,
          indicator_count: 0,
          shared_item_count: 0,
          shared_link_count: 0,
          affected_names: [],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          snapshot: { document_id: DOCUMENT_ID, revision: 5 },
          undo_token: "undo-1",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await editCurrentDocument(DOCUMENT_ID, "autosave-1", guards, document);
    await previewCurrentDocumentCommand(DOCUMENT_ID, guards, command);
    await applyCurrentDocumentCommand(
      DOCUMENT_ID,
      "command-1",
      guards,
      command,
    );

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/current-document`,
      `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/current-document/commands/preview`,
      `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/current-document/commands`,
    ]);
    expect(fetchMock.mock.calls[0][1].headers).toMatchObject({
      "Idempotency-Key": "autosave-1",
      "X-Expected-Revision": "3",
    });
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toEqual({
      document,
      workspace_generation: 4,
      workspace_digest: guards.workspaceDigest,
    });
    expect(fetchMock.mock.calls[1][1].headers).toMatchObject({
      "X-Expected-Revision": "3",
    });
    expect(fetchMock.mock.calls[2][1].headers).toMatchObject({
      "Idempotency-Key": "command-1",
      "X-Expected-Revision": "3",
    });
    for (const index of [1, 2]) {
      expect(JSON.parse(String(fetchMock.mock.calls[index][1].body))).toEqual({
        command,
        workspace_generation: 4,
        workspace_digest: guards.workspaceDigest,
      });
    }
  });

  it("has one export endpoint and adds force only after explicit confirmation", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(new Response("xlsx", { status: 200 })),
      );
    vi.stubGlobal("fetch", fetchMock);

    await exportConsultantDocument(DOCUMENT_ID, false);
    await exportConsultantDocument(DOCUMENT_ID, true);

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/export`,
      `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/export?force=true`,
    ]);
    expect(consultantEventsUrl(DOCUMENT_ID)).toBe(
      `http://127.0.0.1:8001/api/v1/job-analysis/consultant-documents/${DOCUMENT_ID}/events`,
    );
  });
});
