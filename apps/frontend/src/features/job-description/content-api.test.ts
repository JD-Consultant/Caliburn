import { describe, expect, it, vi } from 'vitest';
import { jobDescription, workspaceId } from '../../../tests/fixtures';
import {
  HttpError,
  InvalidRequestError,
  InvalidResponseError,
} from '../../shared/api/http';
import {
  validateAddTaskRequest,
  validateUpdateTaskRequest,
  validateUpdateConditionRequest,
} from '../../shared/api/generated/validators';
import * as api from './content-api';

const jdId = jobDescription.job_description_id;
const taskId = '22112233-4455-6677-8899-aabbccddeeff';
const itemId = '33112233-4455-6677-8899-aabbccddeeff';
const beforeId = '44112233-4455-6677-8899-aabbccddeeff';
const base = `/api/workspaces/${workspaceId}/job-descriptions/${jdId}`;
const write = { expected_version: 3 };
const named = { ...write, name: '合成項目' };
const text = { ...write, text: '合成正文' };
const move = { ...write, before_id: beforeId };
const saved = { ...jobDescription, version: 4 };

it.each([
  [255, true],
  [256, false],
] as const)('Task與內嵌K/S依清洗後的%d字元驗證', (length, accepted) => {
  const name = '\u001c ' + '😀'.repeat(length) + '\u3000\n';
  expect(validateAddTaskRequest({ ...write, name })).toBe(accepted);
  expect(
    validateAddTaskRequest({
      ...named,
      knowledge: [{ kind: 'new', name }],
      skills: [{ kind: 'new', name }],
    }),
  ).toBe(accepted);
  expect(
    validateUpdateTaskRequest({
      ...write,
      changes: [
        { action: 'create_and_link_knowledge', name },
        { action: 'create_and_link_skill', name },
      ],
    }),
  ).toBe(accepted);
});

describe('具名 JD 操作的 HTTP 契約', () => {
  it.each([
    {
      name: '基本資料',
      suffix: '',
      method: 'PATCH',
      body: { ...write, purpose: null },
      run: () => api.updateJobDescription(workspaceId, jdId, { ...write, purpose: null }),
    },
    {
      name: '新增職責',
      suffix: '/duties',
      method: 'POST',
      body: named,
      status: 201,
      run: () => api.addDuty(workspaceId, jdId, named),
    },
    {
      name: '更新職責',
      suffix: `/duties/${itemId}`,
      method: 'PATCH',
      body: named,
      run: () => api.updateDuty(workspaceId, jdId, itemId, named),
    },
    {
      name: '職責排序',
      suffix: `/duties/${itemId}`,
      method: 'PATCH',
      body: { ...write, placement: { before_id: beforeId } },
      run: () => api.moveDuty(workspaceId, jdId, itemId, move),
    },
    {
      name: '新增任務',
      suffix: '/tasks',
      method: 'POST',
      body: named,
      status: 201,
      run: () => api.addTask(workspaceId, jdId, named),
    },
    {
      name: '更新任務',
      suffix: `/tasks/${taskId}`,
      method: 'PATCH',
      body: named,
      run: () => api.updateTask(workspaceId, jdId, taskId, named),
    },
    {
      name: '任務移組',
      suffix: `/tasks/${taskId}`,
      method: 'PATCH',
      body: { ...write, placement: { destination_duty_id: null } },
      run: () =>
        api.moveTask(workspaceId, jdId, taskId, { ...write, destination_duty_id: null }),
    },
    {
      name: '新增成果',
      suffix: `/tasks/${taskId}`,
      method: 'PATCH',
      body: { ...write, changes: [{ action: 'add_outcome', text: '合成正文' }] },
      run: () => api.addOutcome(workspaceId, jdId, taskId, text),
    },
    {
      name: '更新成果',
      suffix: `/tasks/${taskId}`,
      method: 'PATCH',
      body: {
        ...write,
        changes: [{ action: 'update_outcome', id: itemId, text: '合成正文' }],
      },
      run: () => api.updateOutcome(workspaceId, jdId, taskId, itemId, text),
    },
    {
      name: '成果排序',
      suffix: `/tasks/${taskId}`,
      method: 'PATCH',
      body: {
        ...write,
        changes: [{ action: 'move_outcome', id: itemId, before_id: beforeId }],
      },
      run: () => api.moveOutcome(workspaceId, jdId, taskId, itemId, move),
    },
    {
      name: '新增要求',
      suffix: `/tasks/${taskId}`,
      method: 'PATCH',
      body: { ...write, changes: [{ action: 'add_requirement', text: '合成正文' }] },
      run: () => api.addRequirement(workspaceId, jdId, taskId, text),
    },
    {
      name: '更新要求',
      suffix: `/tasks/${taskId}`,
      method: 'PATCH',
      body: {
        ...write,
        changes: [{ action: 'update_requirement', id: itemId, text: '合成正文' }],
      },
      run: () => api.updateRequirement(workspaceId, jdId, taskId, itemId, text),
    },
    {
      name: '要求排序',
      suffix: `/tasks/${taskId}`,
      method: 'PATCH',
      body: {
        ...write,
        changes: [{ action: 'move_requirement', id: itemId, before_id: beforeId }],
      },
      run: () => api.moveRequirement(workspaceId, jdId, taskId, itemId, move),
    },
    {
      name: '新增知識',
      suffix: '/knowledge',
      method: 'POST',
      body: named,
      status: 201,
      run: () => api.addKnowledge(workspaceId, jdId, named),
    },
    {
      name: '更新知識',
      suffix: `/knowledge/${itemId}`,
      method: 'PATCH',
      body: named,
      run: () => api.updateKnowledge(workspaceId, jdId, itemId, named),
    },
    {
      name: '知識排序',
      suffix: `/knowledge/${itemId}`,
      method: 'PATCH',
      body: { ...write, placement: { before_id: beforeId } },
      run: () => api.moveKnowledge(workspaceId, jdId, itemId, move),
    },
    {
      name: '新增技能',
      suffix: '/skills',
      method: 'POST',
      body: named,
      status: 201,
      run: () => api.addSkill(workspaceId, jdId, named),
    },
    {
      name: '更新技能',
      suffix: `/skills/${itemId}`,
      method: 'PATCH',
      body: named,
      run: () => api.updateSkill(workspaceId, jdId, itemId, named),
    },
    {
      name: '技能排序',
      suffix: `/skills/${itemId}`,
      method: 'PATCH',
      body: { ...write, placement: { before_id: beforeId } },
      run: () => api.moveSkill(workspaceId, jdId, itemId, move),
    },
    {
      name: '引用知識',
      suffix: `/tasks/${taskId}`,
      method: 'PATCH',
      body: { ...write, changes: [{ action: 'link_knowledge', id: itemId }] },
      run: () => api.linkKnowledge(workspaceId, jdId, taskId, itemId, write),
    },
    {
      name: '知識引用排序',
      suffix: `/tasks/${taskId}`,
      method: 'PATCH',
      body: {
        ...write,
        changes: [
          { action: 'move_knowledge_reference', id: itemId, before_id: beforeId },
        ],
      },
      run: () => api.moveKnowledgeReference(workspaceId, jdId, taskId, itemId, move),
    },
    {
      name: '引用技能',
      suffix: `/tasks/${taskId}`,
      method: 'PATCH',
      body: { ...write, changes: [{ action: 'link_skill', id: itemId }] },
      run: () => api.linkSkill(workspaceId, jdId, taskId, itemId, write),
    },
    {
      name: '技能引用排序',
      suffix: `/tasks/${taskId}`,
      method: 'PATCH',
      body: {
        ...write,
        changes: [{ action: 'move_skill_reference', id: itemId, before_id: beforeId }],
      },
      run: () => api.moveSkillReference(workspaceId, jdId, taskId, itemId, move),
    },
    {
      name: '新增協作',
      suffix: '/collaborations',
      method: 'POST',
      body: { ...write, collaborator_name: '合成對象' },
      status: 201,
      run: () =>
        api.addCollaboration(workspaceId, jdId, {
          ...write,
          collaborator_name: '合成對象',
        }),
    },
    {
      name: '更新協作',
      suffix: `/collaborations/${itemId}`,
      method: 'PATCH',
      body: { ...write, scope: '' },
      run: () =>
        api.updateCollaboration(workspaceId, jdId, itemId, { ...write, scope: '' }),
    },
    {
      name: '協作排序',
      suffix: `/collaborations/${itemId}`,
      method: 'PATCH',
      body: { ...write, placement: { before_id: beforeId } },
      run: () => api.moveCollaboration(workspaceId, jdId, itemId, move),
    },
    {
      name: '新增條件',
      suffix: '/conditions',
      method: 'POST',
      body: { ...text, kind: 'qualification' },
      status: 201,
      run: () => api.addCondition(workspaceId, jdId, { ...text, kind: 'qualification' }),
    },
    {
      name: '更新條件',
      suffix: `/conditions/${itemId}`,
      method: 'PATCH',
      body: text,
      run: () => api.updateCondition(workspaceId, jdId, itemId, text),
    },
    {
      name: '條件排序',
      suffix: `/conditions/${itemId}`,
      method: 'PATCH',
      body: { ...write, placement: { before_id: beforeId } },
      run: () => api.moveCondition(workspaceId, jdId, itemId, move),
    },
    {
      name: '條件分類',
      suffix: `/conditions/${itemId}`,
      method: 'PATCH',
      body: { ...write, kind: 'work_environment' },
      run: () =>
        api.reclassifyCondition(workspaceId, jdId, itemId, {
          ...write,
          kind: 'work_environment',
        }),
    },
  ])(
    '$name 使用正式路徑、方法及完整回覆',
    async ({ suffix, method, body, status = 200, run }) => {
      const fetch = vi.fn().mockResolvedValue(Response.json(saved, { status }));
      vi.stubGlobal('fetch', fetch);
      await expect(run()).resolves.toEqual(saved);
      expect(fetch).toHaveBeenCalledWith(
        base + suffix,
        expect.objectContaining({ method, body: JSON.stringify(body) }),
      );
    },
  );

  it.each([
    {
      name: '職責',
      suffix: `/duties/${itemId}`,
      run: () => api.deleteDuty(workspaceId, jdId, itemId, 3),
    },
    {
      name: '任務',
      suffix: `/tasks/${taskId}`,
      run: () => api.deleteTask(workspaceId, jdId, taskId, 3),
    },
    {
      name: '知識',
      suffix: `/knowledge/${itemId}`,
      run: () => api.deleteKnowledge(workspaceId, jdId, itemId, 3),
    },
    {
      name: '技能',
      suffix: `/skills/${itemId}`,
      run: () => api.deleteSkill(workspaceId, jdId, itemId, 3),
    },
    {
      name: '協作',
      suffix: `/collaborations/${itemId}`,
      run: () => api.deleteCollaboration(workspaceId, jdId, itemId, 3),
    },
    {
      name: '條件',
      suffix: `/conditions/${itemId}`,
      run: () => api.deleteCondition(workspaceId, jdId, itemId, 3),
    },
  ])('刪除 $name 以 query 核版、沒有body且回完整JD', async ({ suffix, run }) => {
    const fetch = vi.fn().mockResolvedValue(Response.json(saved));
    vi.stubGlobal('fetch', fetch);
    await expect(run()).resolves.toEqual(saved);
    expect(fetch).toHaveBeenCalledWith(
      base + suffix + '?expected_version=3',
      expect.objectContaining({ method: 'DELETE' }),
    );
    expect(fetch.mock.calls[0]?.[1]).not.toHaveProperty('body');
  });

  it.each([
    {
      name: '成果',
      action: 'delete_outcome',
      run: () => api.deleteOutcome(workspaceId, jdId, taskId, itemId, 3),
    },
    {
      name: '要求',
      action: 'delete_requirement',
      run: () => api.deleteRequirement(workspaceId, jdId, taskId, itemId, 3),
    },
    {
      name: '知識引用',
      action: 'unlink_knowledge',
      run: () => api.unlinkKnowledge(workspaceId, jdId, taskId, itemId, 3),
    },
    {
      name: '技能引用',
      action: 'unlink_skill',
      run: () => api.unlinkSkill(workspaceId, jdId, taskId, itemId, 3),
    },
  ])('刪除／解除 $name 使用單次Task PATCH', async ({ action, run }) => {
    const fetch = vi.fn().mockResolvedValue(Response.json(saved));
    vi.stubGlobal('fetch', fetch);
    await expect(run()).resolves.toEqual(saved);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith(
      `${base}/tasks/${taskId}`,
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ ...write, changes: [{ action, id: itemId }] }),
      }),
    );
  });

  it.each([api.linkKnowledge, api.linkSkill])(
    '已存在引用的200 no-op仍是合法完整回覆',
    async (link) => {
      const unchanged = { ...jobDescription, version: 3 };
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(unchanged)));
      await expect(link(workspaceId, jdId, taskId, itemId, write)).resolves.toEqual(
        unchanged,
      );
    },
  );

  it.each([
    {
      name: '職責排序',
      body: {
        expected_version: 3,
        correlation_id: 'ui-write',
        placement: { before_id: beforeId },
      },
      run: () =>
        api.moveDuty(workspaceId, jdId, itemId, { ...move, correlation_id: 'ui-write' }),
    },
    {
      name: '任務移組',
      body: {
        expected_version: 3,
        correlation_id: 'ui-write',
        placement: { destination_duty_id: null },
      },
      run: () =>
        api.moveTask(workspaceId, jdId, taskId, {
          ...write,
          correlation_id: 'ui-write',
          destination_duty_id: null,
        }),
    },
    {
      name: '成果新增',
      body: {
        expected_version: 3,
        correlation_id: 'ui-write',
        changes: [{ action: 'add_outcome', text: '合成正文' }],
      },
      run: () =>
        api.addOutcome(workspaceId, jdId, taskId, {
          ...text,
          correlation_id: 'ui-write',
        }),
    },
    {
      name: '成果排序',
      body: {
        expected_version: 3,
        correlation_id: 'ui-write',
        changes: [{ action: 'move_outcome', id: itemId, before_id: beforeId }],
      },
      run: () =>
        api.moveOutcome(workspaceId, jdId, taskId, itemId, {
          ...move,
          correlation_id: 'ui-write',
        }),
    },
    {
      name: '引用知識',
      body: {
        expected_version: 3,
        correlation_id: 'ui-write',
        changes: [{ action: 'link_knowledge', id: itemId }],
      },
      run: () =>
        api.linkKnowledge(workspaceId, jdId, taskId, itemId, {
          ...write,
          correlation_id: 'ui-write',
        }),
    },
    {
      name: '建立並引用技能',
      body: {
        expected_version: 3,
        correlation_id: 'ui-write',
        changes: [{ action: 'create_and_link_skill', name: '合成項目' }],
      },
      run: () =>
        api.createAndLinkSkill(workspaceId, jdId, taskId, {
          ...named,
          correlation_id: 'ui-write',
        }),
    },
  ])('$name 保留根層追查資訊', async ({ body, run }) => {
    const fetch = vi.fn().mockResolvedValue(Response.json(saved));
    vi.stubGlobal('fetch', fetch);
    await expect(run()).resolves.toEqual(saved);
    expect(fetch).toHaveBeenCalledTimes(1);
    const request: unknown = fetch.mock.calls[0]?.[1];
    expect(request).toMatchObject({ body: JSON.stringify(body), method: 'PATCH' });
  });

  it('建立Task保留多筆O/P、新定義、既有引用與空值，一次送出', async () => {
    const body = {
      ...named,
      description: '',
      duty_id: null,
      competency_level: null,
      outcomes: ['成果甲', '成果乙'],
      requirements: ['要求甲'],
      knowledge: [{ kind: 'new' as const, name: '合成知識', description: null }],
      skills: [{ kind: 'existing' as const, id: itemId }],
    };
    const fetch = vi.fn().mockResolvedValue(Response.json(saved, { status: 201 }));
    vi.stubGlobal('fetch', fetch);
    await api.addTask(workspaceId, jdId, body);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]?.[1]).toMatchObject({ body: JSON.stringify(body) });
  });

  it('Task複合PATCH保留欄位、移組與有序changes，同次回完整JD', async () => {
    const body = {
      ...write,
      name: '共同保存的任務',
      description: null,
      placement: { destination_duty_id: itemId, before_id: null },
      changes: [
        { action: 'add_outcome' as const, text: '新增成果' },
        { action: 'update_requirement' as const, id: itemId, text: '修訂要求' },
        { action: 'create_and_link_knowledge' as const, name: '新知識', description: '' },
        { action: 'link_skill' as const, id: itemId },
        { action: 'move_skill_reference' as const, id: itemId, before_id: beforeId },
      ],
    };
    const fetch = vi.fn().mockResolvedValue(Response.json(saved));
    vi.stubGlobal('fetch', fetch);
    await expect(api.updateTask(workspaceId, jdId, taskId, body)).resolves.toEqual(saved);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith(
      `${base}/tasks/${taskId}`,
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    );
  });

  it.each([
    { ...write, changes: [] },
    { ...write, changes: null },
    { ...write, placement: null },
    { ...write, placement: {} },
    { ...write, changes: [{ action: 'add_outcome', text: '  ' }] },
    { ...write, changes: [{ action: 'link_knowledge', id: 'invalid' }] },
    {
      ...write,
      changes: [{ action: 'update_outcome', id: itemId, text: '成果', changes: [] }],
    },
  ])('生成Task PATCH驗證器拒絕無修改意圖與不合契約的change', (body) => {
    expect(validateUpdateTaskRequest(body)).toBe(false);
  });

  it('生成PATCH驗證器接受本體搭配空changes，以及條件文字分類排序共同修改', () => {
    expect(validateUpdateTaskRequest({ ...write, name: '任務', changes: [] })).toBe(true);
    expect(
      validateUpdateConditionRequest({
        ...write,
        text: '分類後的條件',
        kind: 'work_environment',
        placement: {},
      }),
    ).toBe(true);
  });

  it.each([
    0,
    -1,
    1.5,
    Number.NaN,
    Number.POSITIVE_INFINITY,
    Number.MAX_SAFE_INTEGER + 1,
  ])('刪除前以正式query契約拒絕無效版本 %s', async (version) => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    await expect(
      api.deleteTask(workspaceId, jdId, taskId, version),
    ).rejects.toBeInstanceOf(InvalidRequestError);
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    () => api.updateJobDescription(workspaceId, jdId, write),
    () => api.addDuty(workspaceId, jdId, { ...write, name: '  ' }),
    () => api.updateTask(workspaceId, jdId, taskId, { ...write, competency_level: 7 }),
    () => api.deleteTask(workspaceId, jdId, taskId, Number.NaN),
  ])('不合法請求在外送前拒絕', async (run) => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    await expect(run()).rejects.toBeInstanceOf(InvalidRequestError);
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    { ...saved, workspace_id: itemId },
    { ...saved, job_description_id: itemId },
    { ...saved, version: 0 },
    { ...saved, unexpected: 'field' },
  ])('跨作用域或不合契約的成功回覆不能更新JD', async (response) => {
    const fetch = vi.fn().mockResolvedValue(Response.json(response));
    vi.stubGlobal('fetch', fetch);
    await expect(
      api.updateJobDescription(workspaceId, jdId, { ...write, purpose: null }),
    ).rejects.toBeInstanceOf(InvalidResponseError);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('伺服器的未知提交錯誤原樣交給保存協調，不重試', async () => {
    const error = { detail: { code: 'jd_persistence_error', commit_status: 'unknown' } };
    const fetch = vi.fn().mockResolvedValue(Response.json(error, { status: 500 }));
    vi.stubGlobal('fetch', fetch);
    await expect(api.addTask(workspaceId, jdId, named)).rejects.toMatchObject({
      status: 500,
      body: error,
    } satisfies Partial<HttpError>);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
