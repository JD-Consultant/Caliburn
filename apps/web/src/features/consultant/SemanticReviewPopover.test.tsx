// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { jobAnalysisKeys } from "@/shared/query/jobAnalysisQueries";
import type { ReviewDecoration } from "./consultantWorkspaceModel";
import { SemanticReviewPopover } from "./SemanticReviewPopover";
import {
  DOCUMENT_ID,
  consultantSnapshotFixture,
} from "./consultantWorkspaceTestFixture";

const ACTION_ONE = "00000000-0000-0000-0000-000000000301";
const ACTION_TWO = "00000000-0000-0000-0000-000000000302";
const LATEST_ACTION = "00000000-0000-0000-0000-000000000304";
const LATEST_CHANGESET = "00000000-0000-0000-0000-000000000305";

function decoration(): ReviewDecoration {
  return {
    actionId: ACTION_TWO,
    path: "/job_title",
    entityPath: null,
    operation: "update",
    baseline: "採購專員",
    current: "資深採購專員",
    group: {
      changesetId: "00000000-0000-0000-0000-000000000303",
      summary: "依訪談修正職務名稱",
      actionIds: [ACTION_ONE, ACTION_TWO],
      acceptanceBlocked: false,
      dependencyActionIds: [ACTION_ONE],
      evidence: [
        {
          sourceId: "00000000-0000-0000-0000-000000000002",
          sourceText: "我主要負責資深採購工作。",
          createdAt: "2026-08-27T10:00:00Z",
          quote: "資深採購工作",
        },
      ],
    },
  };
}

function snapshotWithReview() {
  const snapshot = consultantSnapshotFixture();
  const review = decoration();
  snapshot.current_document.job_title = String(review.current);
  snapshot.document_review.bundles = [
    {
      changeset_id: review.group.changesetId,
      summary: review.group.summary,
      source_ids: [snapshot.latest_source_id!],
      created_revision: snapshot.revision,
      acceptance_blocked: false,
      actions: [
        {
          action_id: ACTION_ONE,
          operation: "revise",
          path: "/occupation_name",
          target_key: "/occupation_name",
          before: "採購人員",
          after: "採購管理人員",
          source_ids: [snapshot.latest_source_id!],
          quote_anchors: [],
          read_set: [],
          depends_on_action_ids: [],
          atomic_subgroup_id: null,
          affected_work_ids: [],
          blocks_dependent_analysis: false,
          status: "pending",
        },
        {
          action_id: ACTION_TWO,
          operation: "revise",
          path: "/job_title",
          target_key: "/job_title",
          before: review.baseline,
          after: review.current,
          source_ids: [snapshot.latest_source_id!],
          quote_anchors: [],
          read_set: [],
          depends_on_action_ids: [ACTION_ONE],
          atomic_subgroup_id: null,
          affected_work_ids: [],
          blocks_dependent_analysis: false,
          status: "pending",
        },
      ],
    },
  ];
  snapshot.document_review.unresolved_action_count = 2;
  return snapshot;
}

function renderWithClient(
  ui: ReactNode,
  cacheSnapshot = consultantSnapshotFixture(),
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  client.setQueryData(
    jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID),
    cacheSnapshot,
  );
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
    ),
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("contextual semantic review", () => {
  it("replaces the server's generic workspace summary with employee wording", async () => {
    const user = userEvent.setup();
    const review = decoration();
    review.group.summary = "Workspace semantic review";
    renderWithClient(
      <SemanticReviewPopover
        documentId={DOCUMENT_ID}
        snapshot={consultantSnapshotFixture()}
        decoration={review}
        mutationLocked={false}
        beforeDecision={() => Promise.resolve()}
        triggerLabel="審核修改：職務名稱"
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "審核修改：職務名稱" }),
    );
    expect(screen.getByText("AI 修改職務名稱")).toBeTruthy();
    expect(screen.queryByText("Workspace semantic review")).toBeNull();
  });

  it("opens only from the changed content, shows Evidence, and dismisses with Escape", async () => {
    const user = userEvent.setup();
    renderWithClient(
      <SemanticReviewPopover
        documentId={DOCUMENT_ID}
        snapshot={consultantSnapshotFixture()}
        decoration={decoration()}
        mutationLocked={false}
        beforeDecision={() => Promise.resolve()}
        triggerLabel="審核修改：職務名稱"
      />,
    );

    expect(screen.queryByText("依訪談修正職務名稱")).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "審核修改：職務名稱" }),
    );
    expect(screen.getByText("依訪談修正職務名稱")).toBeTruthy();
    expect(screen.getByText("此組 2 項變更會一起處理")).toBeTruthy();
    expect(screen.getByText(/相依內容收進同一組/)).toBeTruthy();
    await user.click(screen.getByText("查看訪談依據"));
    expect(screen.getByText("資深採購工作")).toBeTruthy();
    expect(screen.queryByText("稍後處理")).toBeNull();
    expect(screen.queryByText("編輯後接受")).toBeNull();

    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByText("依訪談修正職務名稱")).toBeNull(),
    );
  });

  it("flushes current edits and accepts the whole server bundle", async () => {
    const user = userEvent.setup();
    const snapshot = snapshotWithReview();
    const response = structuredClone(snapshot);
    response.revision += 1;
    response.document_review.bundles = [];
    response.document_review.workspace_status = "clean";
    response.document_review.unresolved_action_count = 0;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const beforeDecision = vi.fn().mockResolvedValue(undefined);
    renderWithClient(
      <SemanticReviewPopover
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        decoration={decoration()}
        mutationLocked={false}
        beforeDecision={beforeDecision}
        triggerLabel="審核修改：職務名稱"
      />,
      snapshot,
    );

    await user.click(
      screen.getByRole("button", { name: "審核修改：職務名稱" }),
    );
    await user.click(screen.getByRole("button", { name: "接受整組變更" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(beforeDecision).toHaveBeenCalledTimes(1);
    const [url, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain(`/reviews/${decoration().group.changesetId}`);
    expect(JSON.parse(String(request.body))).toEqual({
      command: "accept_changes",
      action_ids: [ACTION_ONE, ACTION_TWO],
      rejection_reason: null,
    });
  });

  it("re-resolves the latest server bundle after autosave changes review identities", async () => {
    const user = userEvent.setup();
    const initial = snapshotWithReview();
    const latest = structuredClone(initial);
    latest.revision += 1;
    latest.document_review.bundles = [
      {
        changeset_id: LATEST_CHANGESET,
        summary: "依員工編輯重新導出職務名稱變更",
        source_ids: [latest.latest_source_id!],
        created_revision: latest.revision,
        acceptance_blocked: false,
        actions: [
          {
            action_id: LATEST_ACTION,
            operation: "revise",
            path: "/job_title",
            target_key: "/job_title",
            before: "採購專員",
            after: "資深採購管理師",
            source_ids: [latest.latest_source_id!],
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
    ];
    const response = structuredClone(latest);
    response.revision += 1;
    response.document_review.bundles = [];
    response.document_review.unresolved_action_count = 0;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const rendered = renderWithClient(
      <SemanticReviewPopover
        documentId={DOCUMENT_ID}
        snapshot={initial}
        decoration={decoration()}
        mutationLocked={false}
        beforeDecision={() => {
          rendered.client.setQueryData(
            jobAnalysisKeys.consultantSnapshot(DOCUMENT_ID),
            latest,
          );
          return Promise.resolve();
        }}
        triggerLabel="審核修改：職務名稱"
      />,
      initial,
    );

    await user.click(
      screen.getByRole("button", { name: "審核修改：職務名稱" }),
    );
    await user.click(screen.getByRole("button", { name: "接受整組變更" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain(`/reviews/${LATEST_CHANGESET}`);
    expect(JSON.parse(String(request.body))).toMatchObject({
      action_ids: [LATEST_ACTION],
    });
  });

  it("keeps review readable while analysis locks both decisions", async () => {
    const user = userEvent.setup();
    renderWithClient(
      <SemanticReviewPopover
        documentId={DOCUMENT_ID}
        snapshot={consultantSnapshotFixture()}
        decoration={decoration()}
        mutationLocked
        beforeDecision={() => Promise.resolve()}
        triggerLabel="審核修改：職務名稱"
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "審核修改：職務名稱" }),
    );
    expect(screen.getByText("依訪談修正職務名稱")).toBeTruthy();
    expect(
      (screen.getByRole("button", {
        name: "接受整組變更",
      }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(
      (screen.getByRole("button", {
        name: "拒絕整組變更",
      }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("requires a short employee reason before rejecting the whole bundle", async () => {
    const user = userEvent.setup();
    const snapshot = snapshotWithReview();
    const response = structuredClone(snapshot);
    response.revision += 1;
    response.document_review.bundles = [];
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithClient(
      <SemanticReviewPopover
        documentId={DOCUMENT_ID}
        snapshot={snapshot}
        decoration={decoration()}
        mutationLocked={false}
        beforeDecision={() => Promise.resolve()}
        triggerLabel="審核修改：職務名稱"
      />,
      snapshot,
    );

    await user.click(
      screen.getByRole("button", { name: "審核修改：職務名稱" }),
    );
    await user.click(screen.getByRole("button", { name: "拒絕整組變更" }));
    const reason = screen.getByLabelText("拒絕原因");
    expect(
      (screen.getByRole("button", {
        name: "確認拒絕",
      }) as HTMLButtonElement).disabled,
    ).toBe(true);
    await user.type(reason, "這不是我的工作範圍");
    await user.click(screen.getByRole("button", { name: "確認拒絕" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toEqual({
      command: "reject_changes",
      action_ids: [ACTION_ONE, ACTION_TWO],
      rejection_reason: "這不是我的工作範圍",
    });
  });
});
