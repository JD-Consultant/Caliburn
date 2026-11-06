import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  requestJson,
  requestEmpty,
  requestBlob,
  HttpError,
  InvalidResponseError,
} from './http';
import { validateWorkspaceResponse } from './generated/validators';

const workspace = {
  workspace_id: '00112233-4455-6677-8899-aabbccddeeff',
  interviewee_name: '合成受訪者',
};

afterEach(() => vi.useRealTimers());

describe('HTTP 契約邊界', () => {
  it.each([
    { delay: 20_000, status: 200 },
    { delay: 60_001, status: 504 },
  ])('PDF 等待後端列印結果：$delay ms / $status', async ({ delay, status }) => {
    vi.useFakeTimers();
    vi.spyOn(AbortSignal, 'timeout').mockImplementation((milliseconds) => {
      const controller = new AbortController();
      setTimeout(() => controller.abort(), milliseconds);
      return controller.signal;
    });
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof globalThis.fetch>(
        (_input, options) =>
          new Promise<Response>((resolve, reject) => {
            options?.signal?.addEventListener('abort', () =>
              reject(new DOMException('Aborted', 'AbortError')),
            );
            setTimeout(
              () =>
                resolve(
                  status === 200
                    ? new Response('%PDF-1.7', {
                        headers: { 'Content-Type': 'application/pdf' },
                      })
                    : Response.json(
                        { detail: { code: 'pdf_render_timeout' } },
                        { status },
                      ),
                ),
              delay,
            );
          }),
      ),
    );
    const result = requestBlob('/export', {});
    const expectation =
      status === 200
        ? expect(result.then((blob) => blob.text())).resolves.toBe('%PDF-1.7')
        : expect(result).rejects.toMatchObject({
            status: 504,
            body: { detail: { code: 'pdf_render_timeout' } },
          });
    await Promise.all([expectation, vi.advanceTimersByTimeAsync(delay)]);
  });
  it('PDF 等待期間仍接受呼叫端取消，且不重送', async () => {
    const controller = new AbortController();
    const fetch = vi.fn<typeof globalThis.fetch>(
      (_input, options) =>
        new Promise<Response>((_resolve, reject) => {
          options?.signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          );
        }),
    );
    vi.stubGlobal('fetch', fetch);
    const result = requestBlob('/export', { signal: controller.signal });
    controller.abort();
    await expect(result).rejects.toMatchObject({ name: 'AbortError' });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it('PDF 匯出回傳 binary，沿同源與取消政策送出', async () => {
    const signal = new AbortController().signal;
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(
      new Response('%PDF-1.7', {
        headers: { 'Content-Type': 'application/pdf' },
      }),
    );
    vi.stubGlobal('fetch', fetch);
    const blob = await requestBlob('/export', { signal });
    expect(await blob.text()).toBe('%PDF-1.7');
    expect(fetch).toHaveBeenCalledTimes(1);
    const options = fetch.mock.calls[0]?.[1];
    expect(new Headers(options?.headers).get('Accept')).toBe('application/pdf');
    expect(options?.credentials).toBe('same-origin');
    expect(options?.signal).toBeDefined();
  });
  it.each([
    { status: 202, type: 'application/pdf' },
    { status: 200, type: 'application/json' },
    { status: 200, type: 'text/html' },
  ])('非正式 PDF 成功回覆不變成下載：$status $type', async ({ status, type }) => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('body', {
          status,
          headers: { 'Content-Type': type },
        }),
      ),
    );
    await expect(requestBlob('/export', {})).rejects.toBeInstanceOf(InvalidResponseError);
  });
  it('PDF 錯誤保留狀態與 JSON body，不吞成檔案', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(Response.json({ detail: 'unavailable' }, { status: 503 })),
    );
    await expect(requestBlob('/export', {})).rejects.toMatchObject({
      status: 503,
      body: { detail: 'unavailable' },
    });
  });
  it.each([200, 201])('引用可接受契約明列的成功狀態 %s', async (status) => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(Response.json(workspace, { status })),
    );
    await expect(
      requestJson('/reference', { method: 'PUT' }, validateWorkspaceResponse, [200, 201]),
    ).resolves.toEqual(workspace);
  });
  it('多個合法狀態不會放寬成任意 2xx', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(Response.json(workspace, { status: 202 })),
    );
    await expect(
      requestJson('/reference', { method: 'PUT' }, validateWorkspaceResponse, [200, 201]),
    ).rejects.toBeInstanceOf(InvalidResponseError);
  });
  it('寫入收到無法解碼的成功回覆時拒絕且不重送', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('not json'));
    vi.stubGlobal('fetch', fetch);
    await expect(
      requestJson('/reference', { method: 'PUT' }, validateWorkspaceResponse),
    ).rejects.toBeInstanceOf(InvalidResponseError);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it('非預期的成功狀態不能冒充已完成的操作', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(Response.json(workspace, { status: 202 })),
    );
    await expect(
      requestJson('/workspaces/one', {}, validateWorkspaceResponse),
    ).rejects.toBeInstanceOf(InvalidResponseError);
  });
  it.each([
    'wrong',
    'urn:uuid:' + workspace.workspace_id,
    workspace.workspace_id.replaceAll('-', ''),
    workspace.workspace_id + '\n',
  ])('回覆 UUID 不符合正式契約時拒絕：%s', async (workspaceId) => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(Response.json({ ...workspace, workspace_id: workspaceId })),
    );
    await expect(
      requestJson('/workspaces/one', {}, validateWorkspaceResponse),
    ).rejects.toBeInstanceOf(InvalidResponseError);
  });
  it('整份刪除的 204 不解析不存在的 JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );
    await expect(
      requestEmpty('/workspaces/one', { method: 'DELETE' }),
    ).resolves.toBeUndefined();
  });
  it('寫入失聯只送一次，不能把未知結果當作未提交', async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError('network'));
    vi.stubGlobal('fetch', fetch);
    await expect(
      requestJson(
        '/workspaces',
        { method: 'POST', body: JSON.stringify({ interviewee_name: '合成受訪者' }) },
        validateWorkspaceResponse,
      ),
    ).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it('保留 HTTP 狀態供各功能判別，不把拒絕轉成空資料', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          Response.json({ detail: { code: 'workspace_not_found' } }, { status: 404 }),
        ),
    );
    await expect(
      requestJson('/workspaces/one', {}, validateWorkspaceResponse),
    ).rejects.toMatchObject({
      status: 404,
      body: { detail: { code: 'workspace_not_found' } },
    } satisfies Partial<HttpError>);
  });
});
