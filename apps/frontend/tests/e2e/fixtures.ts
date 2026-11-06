import { randomUUID } from 'node:crypto';
import { test as base, expect, type APIRequestContext } from '@playwright/test';
import type { JobDescriptionResponse } from '../../src/shared/api/generated/types.gen';
import {
  validateJobDescriptionResponse,
  validateWorkspaceResponse,
} from '../../src/shared/api/generated/validators.js';

export class SyntheticApi {
  private readonly workspaceIds = new Set<string>();
  readonly request: APIRequestContext;

  constructor(request: APIRequestContext) {
    this.request = request;
  }

  track(workspaceId: string) {
    this.workspaceIds.add(workspaceId);
  }

  async createWorkspace(label = '測試受訪者') {
    const response = await this.request.post('/workspaces', {
      data: { interviewee_name: `${label} ${randomUUID().slice(0, 8)}` },
    });
    expect(response.status(), await response.text()).toBe(201);
    const body: unknown = await response.json();
    if (!validateWorkspaceResponse(body))
      throw new Error('Invalid workspace fixture response');
    this.track(body.workspace_id);
    return body;
  }

  async createCompleteDocument() {
    const workspace = await this.createWorkspace('林怡君・營運規劃');
    const response = await this.request.get(
      `/workspaces/${workspace.workspace_id}/job-description`,
    );
    expect(response.status(), await response.text()).toBe(200);
    const first: unknown = await response.json();
    if (!validateJobDescriptionResponse(first))
      throw new Error('Invalid JD fixture response');
    let jd: JobDescriptionResponse = first;
    const path = `/workspaces/${workspace.workspace_id}/job-descriptions/${jd.job_description_id}`;
    const change = async (resource: string, fields: Record<string, unknown>) => {
      const next = await this.request.fetch(path + resource, {
        method: resource ? 'POST' : 'PATCH',
        data: { expected_version: jd.version, ...fields },
      });
      expect(next.ok(), await next.text()).toBe(true);
      const body: unknown = await next.json();
      if (!validateJobDescriptionResponse(body))
        throw new Error('Invalid JD mutation response');
      jd = body;
    };
    await change('', {
      job_title: '營運規劃與流程改善專員',
      organization_unit: '營運管理處・流程改善組',
      reports_to: '營運管理主管',
      baseline_competency_level: 3,
      purpose:
        '協助團隊把分散的工作資訊整理成可追溯的營運計畫，持續改善跨部門交接品質。\n以訪談、流程觀察與資料核對確認問題，提出可執行的改善方案，並追蹤成果與例外。',
    });
    const dutyNames = ['營運資訊分析', '跨部門流程改善', '工作標準與知識維護'];
    for (const [index, name] of dutyNames.entries()) {
      await change('/duties', {
        name,
        scope:
          '從需求確認、現況整理、風險辨識到成果追蹤，與相關窗口共同維護作業資訊及交付品質。',
      });
      const dutyId = jd.duties.at(-1)?.id;
      if (!dutyId) throw new Error('Missing created duty');
      for (let task = 1; task <= 2; task += 1) {
        const detailedExample = index === 0 && task === 1;
        const knowledge = jd.knowledge.find((item) => item.name === `${name}相關知識`);
        const skill = jd.skills.find((item) => item.name === `${name}整理技能`);
        await change('/tasks', {
          name: `${name}：${task === 1 ? '整理現況與辨識差異' : '確認改善方案並追蹤執行'}`,
          duty_id: dutyId,
          description:
            '定期彙整營運資料，訪談實際執行人員，交叉核對來源、時間範圍與例外原因。\n整理決策所需的摘要，與相關窗口確認後更新追蹤紀錄。',
          competency_level: index + 2,
          outcomes: [
            '具備來源及核對日期的現況分析報告。',
            '責任、完成期限與驗收方式清楚的改善追蹤表。',
            ...(detailedExample
              ? [
                  '跨部門資訊交接清單：逐項列出資料來源、負責窗口、交付時間、核對方式與待確認事項，讓接手人員可以延續追蹤。',
                ]
              : []),
          ],
          requirements: [
            '不同來源數字有落差時，先確認定義與統計範圍。',
            '資料僅供授權窗口使用；保留異動與確認紀錄。',
            ...(detailedExample
              ? [
                  '資料缺漏時記錄未取得的項目、原因與預計補齊時間，不以推測填入正式結果。',
                  '針對需要跨部門確認的數字，逐一註明來源及核對日期。\n如雙方定義不同，先保留差異與待確認事項，再與窗口協調。',
                  '交付前確認責任、完成期限與驗收方式都有具體內容。',
                ]
              : []),
          ],
          knowledge: [
            knowledge
              ? { kind: 'existing', id: knowledge.id }
              : {
                  kind: 'new',
                  name: `${name}相關知識`,
                  description: '熟悉工作流程、資料定義及組織的協作規則。',
                },
          ],
          skills: [
            skill
              ? { kind: 'existing', id: skill.id }
              : {
                  kind: 'new',
                  name: `${name}整理技能`,
                  description: '能進行訪談、資料比對、問題拆解及清楚的書面表達。',
                },
          ],
        });
      }
    }
    await change('/tasks', {
      name: '未分類：長字串與特殊內容核對',
      description: 'DocumentReference_' + 'VeryLongUnbrokenIdentifier'.repeat(9),
      outcomes: ['保留 <script>alert("synthetic")</script> 作為普通文字，不執行內容。'],
      requirements: ['中文、English、數字 0123456789 與換行都應完整可讀。'],
    });
    await change('/collaborations', {
      collaborator_name: '業務、資訊與行政窗口',
      scope:
        '確認資料定義、協調交付時程並釐清跨部門責任；有爭議時記錄待確認事項及處理人。',
    });
    const conditions = [
      ['work_environment', '以辦公室工作為主，視改善議題至現場觀察流程。'],
      ['schedule_travel', '依團隊作業時間協調訪談；偶爾至其他辦公地點進行流程確認。'],
      ['shared_authority', '可提出改善建議及追蹤進度；正式政策與資源配置由主管核定。'],
      ['shared_collaboration', '跨單位協作時，共同確認工作定義、資訊來源與交付時間。'],
      ['qualification', '具備基本資料整理、書面表達與跨部門溝通能力。'],
    ];
    for (const [kind, text] of conditions) await change('/conditions', { kind, text });
    return { workspace, jd };
  }

  async dispose() {
    for (const id of this.workspaceIds) {
      const response = await this.request.delete(`/workspaces/${id}`);
      expect([204, 404], `cleaning this test's workspace ${id}`).toContain(
        response.status(),
      );
    }
    await this.request.dispose();
  }
}

export const test = base.extend<{ synthetic: SyntheticApi }>({
  synthetic: async ({ playwright }, run) => {
    const baseURL = process.env.CALIBURN_E2E_API_URL;
    if (!baseURL) throw new Error('CALIBURN_E2E_API_URL is required');
    const request = await playwright.request.newContext({
      baseURL,
      timeout: 10_000,
    });
    const synthetic = new SyntheticApi(request);
    try {
      await run(synthetic);
    } finally {
      await synthetic.dispose();
    }
  },
});

export { expect };
