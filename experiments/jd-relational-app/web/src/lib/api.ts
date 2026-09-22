import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import workSchema from '../../../contracts/jd-work.schema.json' with { type: 'json' };
import readSchema from '../../../contracts/jd-read.schema.json' with { type: 'json' };
import resultSchema from '../../../contracts/jd-result.schema.json' with { type: 'json' };
import httpSchema from '../../../contracts/jd-http.schema.json' with { type: 'json' };
import querySchema from '../../../contracts/jd-query-http.schema.json' with { type: 'json' };
import manualSchema from '../../../contracts/jd-manual-http.schema.json' with { type: 'json' };
import catalogSchema from '../../../contracts/jd-catalog-http.schema.json' with { type: 'json' };
import chatSchema from '../../../contracts/jd-chat-http.schema.json' with { type: 'json' };
import type { ReadInput, ReadPage, ChangeReadPage, RestorePreviewPage, SourceReadPage } from '../../../src/jd_relational/generated/jd-read';
import type { ManualSaveInput, ManualOperationState, ManualDocumentState } from '../../../src/jd_relational/generated/jd-manual-http';
import type { MutationResult } from '../../../src/jd_relational/generated/jd-result';
import type { CatalogPage, CatalogCreateInput, CatalogCreationResult, CatalogCreationLookup, CatalogDocument, CatalogMetadataInput } from '../../../src/jd_relational/generated/jd-catalog-http';
import type { CatalogProblem } from '../../../src/jd_relational/generated/jd-catalog-http';
import type { ManualProblem } from '../../../src/jd_relational/generated/jd-manual-http';
import type { HttpProblem } from '../../../src/jd_relational/generated/jd-http';
import type { QueryProblem } from '../../../src/jd_relational/generated/jd-query-http';
import type { ChatStartInput, ChatRunState, ChatHistoryPage, ChatProblem, ChatRunChangePage } from '../../../src/jd_relational/generated/jd-chat-http';

export type ChatMessagesOptions =
  | { cursor?: null; anchor?: never; anchorRunId?: never; limit?: number }
  | { cursor: string; anchor: string; anchorRunId: string; limit?: number };

export class ApiError extends Error {
  code: string;
  constructor(code: string, message = '目前無法確認服務回覆，請保留輸入並重新查看狀態。') {
    super(message); this.name = 'ApiError'; this.code = code;
  }
}

const ajv = new Ajv2020({ strict: true, coerceTypes: false, useDefaults: false, removeAdditional: false });
addFormats(ajv);
for (const [name, schema] of Object.entries({ work: workSchema, read: readSchema, result: resultSchema,
  http: httpSchema, 'query-http': querySchema, 'manual-http': manualSchema, 'catalog-http': catalogSchema,
  'chat-http': chatSchema })) {
  ajv.addSchema(schema, `jd-${name}.schema.json`);
}
const checks = new Map<string, ReturnType<typeof ajv.compile>>();
const REQUEST_TIMEOUT_MS = 15_000;

export function decode<T>(file: string, name: string, value: unknown): T {
  // These two authoritative contracts define their response at the root.
  const root = file === 'http' && name === 'HttpProblem' || file === 'query-http' && name === 'QueryProblem';
  const ref = `jd-${file}.schema.json${root ? '' : `#/$defs/${name}`}`;
  try {
    let check = checks.get(ref);
    if (!check) { check = ajv.compile({ $ref: ref }); checks.set(ref, check); }
    if (!check(value)) throw new Error();
  } catch { throw new ApiError('invalid_response', '服務回覆格式不符，已保留輸入。請確認 App 與服務版本一致。'); }
  return value as T;
}
function invalid(): never { throw new ApiError('invalid_response'); }
function strongEtag(value: string | null): string {
  // Opaque HTTP representation validator: check syntax, never recreate its hash.
  if (value === null || !/^"[\x21\x23-\x7e\x80-\xff]*"$/.test(value)) invalid();
  return value;
}
export function validateManualRequest(value: unknown): asserts value is ManualSaveInput {
  decode<ManualSaveInput>('manual-http', 'ManualSaveInput', value);
}
export function validateChatRequest(value: unknown): asserts value is ChatStartInput {
  let input: ChatStartInput;
  try { input = decode<ChatStartInput>('chat-http', 'ChatStartInput', value); }
  catch { throw new ApiError('invalid_input', '這次訪談內容不符送出格式；請保留輸入並確認內容。'); }
  // The existing server boundary measures original UTF-8, not code points.
  if (!input.text.isWellFormed() || new TextEncoder().encode(input.text).length > 128 * 1024)
    throw new ApiError('invalid_input', '這次訪談文字無法送出；請保留輸入並確認內容與長度。');
}
export function validateOrigin(value: string): string {
  let url: URL;
  try { url = new URL(value); } catch { throw new ApiError('configuration_required', '尚未設定本機資料服務。'); }
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname) || url.origin !== value)
    throw new ApiError('configuration_required', '資料服務必須使用明確的本機位址。');
  return url.origin;
}

export class JdApi {
  origin: string;
  datasetId: string | null = null;
  private fetcher: typeof fetch;
  constructor(origin: string, fetcher: typeof fetch = fetch) { this.origin = validateOrigin(origin); this.fetcher = fetcher; }

  private async request(path: string, body?: unknown, options: {
    method?: string; etag?: string; mutation?: boolean; chat?: boolean; accepted?: boolean;
  } = {}) {
    const method = options.method ?? (body === undefined ? 'GET' : 'POST');
    if (method !== 'GET' && !this.datasetId) throw new ApiError('dataset_required', '請先讀取文件列表。');
    let response: Response;
    try {
      const send = this.fetcher; // Browser fetch must not receive JdApi as its receiver.
      response = await send(this.origin + path, { method, cache: 'no-store', credentials: 'omit', redirect: 'error',
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS), headers: {
          ...(body === undefined ? {} : { 'Content-Type': method === 'PATCH' ? 'application/merge-patch+json' : 'application/json' }),
          ...(this.datasetId ? { 'X-JD-Dataset': this.datasetId } : {}),
          ...(options.etag ? { 'If-Match': options.etag } : {}),
        }, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch { throw new ApiError('response_unknown', options.chat
      ? '連線中斷或服務未回應；請保留原輸入，並用原回合查看狀態。'
      : '連線中斷或服務未回應；保存結果須用原操作查回。'); }
    const media = response.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase();
    if (media !== (response.ok ? 'application/json' : 'application/problem+json')) invalid();
    let value: unknown;
    try { value = await response.json(); }
    catch (error) {
      if (error instanceof SyntaxError) throw new ApiError('invalid_response');
      throw new ApiError('response_unknown', options.chat
        ? '連線中斷或服務未回應；請保留原輸入，並用原回合查看狀態。'
        : '連線中斷或服務未回應；保存結果須用原操作查回。');
    }
    if (!response.ok) {
      // Preserve the same domain result; a transport Problem is not a new result.
      if (value && typeof value === 'object' && 'jd_result' in value) {
        const problem = decode<HttpProblem>('http', 'HttpProblem', value);
        if (!options.mutation || problem.status !== response.status) invalid();
        return { value: problem.jd_result, response };
      }
      if (options.chat) {
        const problem = decode<ChatProblem>('chat-http', 'ChatProblem', value);
        if (problem.status !== response.status) invalid();
        throw new ApiError(problem.code, problem.detail);
      }
      let problem: CatalogProblem | ManualProblem | QueryProblem | null = null;
      const definitions = [['catalog-http', 'CatalogProblem'], ['manual-http', 'ManualProblem'], ['query-http', 'QueryProblem']];
      for (const [file, name] of definitions) {
        try { problem = decode<CatalogProblem | ManualProblem | QueryProblem>(file, name, value); break; } catch { /* Try only the other published Problem shapes. */ }
      }
      if (!problem || problem.status !== response.status) invalid();
      throw new ApiError('jd_read_error' in problem ? problem.jd_read_error.code : problem.code, problem.detail);
    }
    if (response.status !== 200 && !((options.mutation || options.accepted) && response.status === 202)) invalid();
    return { value, response };
  }

  async list(archived: 'false' | 'true' | 'all' = 'false'): Promise<CatalogPage> {
    let after: string | null = null, dataset: string | null = null;
    const documents: CatalogDocument[] = [], seen = new Set<string>();
    do {
      const { value } = await this.request(`/api/documents?archived=${archived}${after ? '&after=' + encodeURIComponent(after) : ''}`);
      const page = decode<CatalogPage>('catalog-http', 'CatalogPage', value);
      if (dataset && dataset !== page.dataset_id) throw new ApiError('dataset_changed', '資料集已更換，請重新開啟。');
      dataset = page.dataset_id;
      if (page.next_after !== null && (page.documents.length === 0
          || page.next_after !== page.documents.at(-1)!.document_id)) invalid();
      for (const document of page.documents) {
        if (after && document.document_id <= after) invalid();
        if (seen.has(document.document_id)) throw new ApiError('invalid_response');
        seen.add(document.document_id); documents.push(document);
      }
      if (page.next_after === after && after) throw new ApiError('invalid_response');
      after = page.next_after;
    } while (after);
    if (this.datasetId && this.datasetId !== dataset) throw new ApiError('dataset_changed', '資料集已更換，請重新開啟；原候選已保留。');
    this.datasetId = dataset;
    return { dataset_id: dataset!, documents, next_after: null };
  }
  async metadata(id: string) {
    const { value, response } = await this.request(`/api/documents/${encodeURIComponent(id)}/metadata`);
    const document = decode<CatalogDocument>('catalog-http', 'CatalogDocument', value);
    if (document.document_id !== id) invalid();
    return { document, etag: strongEtag(response.headers.get('ETag')) };
  }
  async updateMetadata(id: string, input: CatalogMetadataInput, etag: string) {
    decode('catalog-http', 'CatalogMetadataInput', input);
    strongEtag(etag);
    const { value, response } = await this.request(`/api/documents/${encodeURIComponent(id)}/metadata`, input, { method: 'PATCH', etag });
    const document = decode<CatalogDocument>('catalog-http', 'CatalogDocument', value);
    if (document.document_id !== id) invalid();
    strongEtag(response.headers.get('ETag'));
    return document;
  }
  private creationInput(input: CatalogCreateInput) {
    decode('catalog-http', 'CatalogCreateInput', input);
    if (this.datasetId !== input.dataset_id) throw new ApiError('dataset_changed', '資料集已變更，原建立請求已保留。');
  }
  async create(input: CatalogCreateInput) {
    this.creationInput(input);
    const value = decode<CatalogCreationResult>('catalog-http', 'CatalogCreationResult', (await this.request('/api/documents', input)).value);
    if (value.request_key !== input.request_key || value.dataset_id !== input.dataset_id) throw new ApiError('invalid_response');
    return value;
  }
  async lookupCreation(input: CatalogCreateInput) {
    this.creationInput(input);
    const value = decode<CatalogCreationLookup>('catalog-http', 'CatalogCreationLookup', (await this.request('/api/document-creations/lookup', input)).value);
    if (value.request_key !== input.request_key || value.dataset_id !== input.dataset_id) invalid();
    return value;
  }
  async read(id: string, input: ReadInput = { view: 'current', target_ref: null, cursor: null }): Promise<ReadPage> {
    decode('read', 'ReadInput', input);
    // This method assembles a complete view; raw cursor suffixes are not one.
    if (input.cursor !== null) invalid();
    let all: ReadPage | null = null;
    let cursor: string | null = input.cursor;
    const seen = new Set<string>();
    do {
      const page: ReadPage = decode('read', 'ReadPage', (await this.request(`/api/documents/${encodeURIComponent(id)}/jd/read`, { ...input, cursor })).value);
      if (page.view !== input.view || input.view === 'current' && page.access !== 'current'
          || input.view === 'history' && page.access !== 'history'
          || page.has_more !== (page.next_cursor !== null)
          || page.has_more && page.records.length === 0
          || page.oversized_unit && page.records.length !== 1) invalid();
      if (all && (page.revision_ref !== all.revision_ref || page.access !== all.access))
        throw new ApiError('stale_view', '讀取期間版本已變更，請重新讀取完整內容。');
      if (all && (page.start_index !== all.records.length || page.total_records !== all.total_records)) invalid();
      if (!all) { if (page.start_index !== 0) throw new ApiError('invalid_response'); all = { ...page, records: [] }; }
      all.records.push(...page.records);
      if (all.total_records !== null && (all.records.length > all.total_records
          || page.has_more !== (all.records.length < all.total_records))) invalid();
      cursor = page.next_cursor;
      if (cursor && seen.has(cursor)) throw new ApiError('invalid_response');
      if (cursor) seen.add(cursor);
    } while (cursor);
    if (all.total_records !== null && all.total_records !== all.records.length) throw new ApiError('invalid_response');
    return { ...all, has_more: false, next_cursor: null };
  }
  async state(id: string) { return decode<ManualDocumentState>('manual-http', 'ManualDocumentState',
    (await this.request(`/api/documents/${encodeURIComponent(id)}/jd/state`)).value); }
  async save(id: string, request: ManualSaveInput) {
    validateManualRequest(request);
    const { value, response } = await this.request(`/api/documents/${encodeURIComponent(id)}/jd/edits`, request, { mutation: true });
    const result = decode<MutationResult>('result', 'MutationResult', value);
    if (response.status === 200 && !(result.status === 'committed' || result.status === 'no_change')
        || response.status === 202 && !(result.operation_ref !== null && result.next_action === 'reconcile_operation')) invalid();
    return result;
  }
  async operation(id: string, operationId: string, recover = false) {
    const path = `/api/documents/${encodeURIComponent(id)}/jd/operations/${encodeURIComponent(operationId)}`;
    const result = decode<ManualOperationState>('manual-http', 'ManualOperationState',
      (await this.request(path + (recover ? '/recover' : ''), recover ? {} : undefined)).value);
    if (result.operation_id !== operationId) throw new ApiError('invalid_response');
    return result;
  }
  private chatScope(id: string, runId?: string): string {
    if (!this.datasetId) throw new ApiError('dataset_required', '請先讀取文件列表。');
    decode('chat-http', 'ChatUuid', this.datasetId);
    decode('chat-http', 'ChatUuid', id);
    if (runId !== undefined) decode('chat-http', 'ChatUuid', runId);
    return this.datasetId;
  }
  private sameChatDataset(dataset: string) {
    if (this.datasetId !== dataset)
      throw new ApiError('dataset_changed', '資料集已變更，原輸入已保留。請重新查看文件。');
  }
  private chatResult(id: string, runId: string, dataset: string, value: unknown, response: Response, control: boolean) {
    this.sameChatDataset(dataset);
    const result = decode<ChatRunState>('chat-http', 'ChatRunState', value);
    if (result.dataset_id !== dataset || result.document_id !== id || result.run_id !== runId) invalid();
    if (control) {
      const pending = ['running', 'closing', 'recovery_required'].includes(result.run_status);
      if (response.status !== (pending ? 202 : 200)) invalid();
      const location = response.headers.get('Location');
      if (!location) invalid();
      let target: URL;
      try { target = new URL(location, this.origin); } catch { invalid(); }
      if (target.origin !== this.origin || target.pathname !== `/api/documents/${id}/chat/runs/${runId}`
          || target.search || target.hash || target.username || target.password) invalid();
    }
    return result;
  }
  async chatStart(id: string, input: ChatStartInput): Promise<ChatRunState> {
    const dataset = this.chatScope(id);
    validateChatRequest(input);
    const runId = input.run_id;
    const { value, response } = await this.request(`/api/documents/${id}/chat/runs`, input, { chat: true, accepted: true });
    return this.chatResult(id, runId, dataset, value, response, true);
  }
  async chatStatus(id: string, runId: string): Promise<ChatRunState> {
    const dataset = this.chatScope(id, runId);
    const { value, response } = await this.request(`/api/documents/${id}/chat/runs/${runId}`, undefined, { chat: true });
    return this.chatResult(id, runId, dataset, value, response, false);
  }
  private async chatControl(id: string, runId: string, action: 'cancel' | 'recover'): Promise<ChatRunState> {
    const dataset = this.chatScope(id, runId);
    const { value, response } = await this.request(`/api/documents/${id}/chat/runs/${runId}/${action}`, {}, { chat: true, accepted: true });
    return this.chatResult(id, runId, dataset, value, response, true);
  }
  async chatCancel(id: string, runId: string): Promise<ChatRunState> { return this.chatControl(id, runId, 'cancel'); }
  async chatRecover(id: string, runId: string): Promise<ChatRunState> { return this.chatControl(id, runId, 'recover'); }
  async chatMessages(id: string, options: ChatMessagesOptions = {}): Promise<ChatHistoryPage> {
    const dataset = this.chatScope(id);
    if (options === null || typeof options !== 'object' || Array.isArray(options)
        || Object.keys(options).some(key => !['cursor', 'anchor', 'anchorRunId', 'limit'].includes(key))) invalid();
    const cursor = options.cursor ?? null;
    const limit = options.limit === undefined ? 50 : options.limit;
    if (!Number.isInteger(limit) || limit < 1 || limit > 50) invalid();
    if (cursor === null) {
      if ('anchor' in options || 'anchorRunId' in options) invalid();
    } else {
      decode('chat-http', 'ChatOpaqueRef', cursor);
      decode('chat-http', 'ChatOpaqueRef', options.anchor);
      decode('chat-http', 'ChatUuid', options.anchorRunId);
    }
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor !== null) query.set('cursor', cursor);
    const { value } = await this.request(`/api/documents/${id}/chat/messages?${query}`, undefined, { chat: true });
    this.sameChatDataset(dataset);
    const page = decode<ChatHistoryPage>('chat-http', 'ChatHistoryPage', value);
    if (page.dataset_id !== dataset || page.document_id !== id
        || page.messages.length > limit || page.next_cursor !== null && page.messages.length === 0
        || cursor === null && page.anchor !== null && page.messages.at(-1)?.run_id !== page.anchor_run_id
        || cursor !== null && (page.anchor !== options.anchor || page.anchor_run_id !== options.anchorRunId
          || page.messages.length === 0 || page.next_cursor === cursor)) invalid();
    const seen = new Set<string>();
    let messageRun: string | null = null;
    for (const message of page.messages) {
      if (seen.has(message.message_id)) invalid();
      seen.add(message.message_id);
      if (message.role === 'user') {
        if (message.message_id !== message.run_id) invalid();
        messageRun = message.run_id;
      } else {
        if (messageRun !== null && message.run_id !== messageRun) invalid();
        messageRun = message.run_id;
      }
    }
    // One fixed page only: initial page is the latest window, later pages are
    // older (all pages remain chronological). The UI prepends older pages and
    // checks cross-page duplicates; disposed views must ignore late responses.
    return page;
  }
  async runChanges(id: string, runId: string): Promise<ChatRunChangePage> {
    const dataset = this.chatScope(id, runId);
    let all: ChatRunChangePage | null = null, cursor: string | null = null;
    const seen = new Set<string>();
    do {
      const suffix = cursor === null ? '' : `?${new URLSearchParams({ cursor })}`;
      const { value } = await this.request(`/api/documents/${id}/chat/runs/${runId}/changes${suffix}`, undefined, { chat: true });
      this.sameChatDataset(dataset);
      const page = decode<ChatRunChangePage>('chat-http', 'ChatRunChangePage', value);
      if (page.dataset_id !== dataset || page.document_id !== id || page.run_id !== runId
          || page.has_more !== (page.next_cursor !== null) || page.has_more && page.records.length === 0
          || page.oversized_unit && page.records.length !== 1
          || (all && (page.format_version !== all.format_version || page.capture_ref !== all.capture_ref
            || page.effects_state !== all.effects_state || page.continuity !== all.continuity
            || page.captured_operation_count !== all.captured_operation_count
            || page.base_revision_ref !== all.base_revision_ref || page.result_revision_ref !== all.result_revision_ref
            || page.total_records !== all.total_records || page.total_changes !== all.total_changes
            || page.start_index !== all.records.length))) invalid();
      if (!all && page.start_index !== 0) invalid();
      all ??= { ...page, records: [] };
      all.records.push(...page.records);
      if (all.records.length > all.total_records || page.has_more !== (all.records.length < all.total_records)) invalid();
      cursor = page.next_cursor;
      if (cursor && seen.has(cursor)) invalid();
      if (cursor) seen.add(cursor);
    } while (cursor);
    if (all.total_records !== all.records.length) invalid();
    // Validate complete transport framing, not the meaning of the JD changes.
    let group = -1;
    for (const row of all.records) {
      if (row.type === 'change') {
        if (row.change_index !== group + 1) invalid();
        group = row.change_index;
      } else if (group < 0 || row.change_index !== group) invalid();
      if (row.change_index >= all.total_changes) invalid();
    }
    if (group + 1 !== all.total_changes) invalid();
    return { ...all, has_more: false, next_cursor: null };
  }
  async restorePreview(id: string, targetRevisionRef: string): Promise<RestorePreviewPage> {
    // Reading only. Framing is checked exactly as a saved change is; the
    // business difference itself is never recomputed here.
    let all: RestorePreviewPage | null = null, cursor: string | null = null;
    const seen = new Set<string>();
    do {
      const page: RestorePreviewPage = decode('read', 'RestorePreviewPage',
        (await this.request(`/api/documents/${encodeURIComponent(id)}/jd/restore/preview`,
          { target_revision_ref: targetRevisionRef, cursor })).value);
      if (page.target_revision_ref !== targetRevisionRef || page.has_more !== (page.next_cursor !== null)
          || page.has_more && page.records.length === 0 || page.oversized_unit && page.records.length !== 1
          || (all && (page.base_revision_ref !== all.base_revision_ref || page.start_index !== all.records.length
            || page.total_records !== all.total_records || page.total_changes !== all.total_changes))) invalid();
      if (!all && page.start_index !== 0) invalid();
      all ??= { ...page, records: [] };
      all.records.push(...page.records); cursor = page.next_cursor;
      if (all.records.length > all.total_records || page.has_more !== (all.records.length < all.total_records)) invalid();
      if (cursor && seen.has(cursor)) throw new ApiError('invalid_response');
      if (cursor) seen.add(cursor);
    } while (cursor);
    if (all.total_records !== all.records.length) throw new ApiError('invalid_response');
    return { ...all, has_more: false, next_cursor: null };
  }

  /** The saved interview behind one JD marker. One page; the server bounds it. */
  async sourceRead(id: string, sourceRef: string): Promise<SourceReadPage> {
    const page: SourceReadPage = decode('read', 'SourceReadPage',
      (await this.request(`/api/documents/${encodeURIComponent(id)}/jd/sources/read`,
        { source_ref: sourceRef })).value);
    if (page.source_ref !== sourceRef) invalid();
    return page;
  }

  async changes(id: string, changeRef: string): Promise<ChangeReadPage> {
    let all: ChangeReadPage | null = null, cursor: string | null = null;
    const seen = new Set<string>();
    do {
      const page: ChangeReadPage = decode('read', 'ChangeReadPage', (await this.request(`/api/documents/${encodeURIComponent(id)}/jd/changes/read`, { change_ref: changeRef, cursor })).value);
      if (page.change_ref !== changeRef || page.has_more !== (page.next_cursor !== null)
          || page.has_more && page.records.length === 0 || page.oversized_unit && page.records.length !== 1
          || (all && (page.operation_ref !== all.operation_ref || page.start_index !== all.records.length
            || page.base_revision_ref !== all.base_revision_ref || page.result_revision_ref !== all.result_revision_ref
            || page.origin !== all.origin || page.total_records !== all.total_records || page.total_changes !== all.total_changes))) invalid();
      if (!all && page.start_index !== 0) invalid();
      all ??= { ...page, records: [] };
      all.records.push(...page.records); cursor = page.next_cursor;
      if (all.records.length > all.total_records || page.has_more !== (all.records.length < all.total_records)) invalid();
      if (cursor && seen.has(cursor)) throw new ApiError('invalid_response');
      if (cursor) seen.add(cursor);
    } while (cursor);
    if (all.total_records !== all.records.length) throw new ApiError('invalid_response');
    // A complete transport must contain each declared group exactly once, in
    // order. This checks framing; it does not recompute any business changes.
    let group = -1;
    for (const row of all.records) {
      if (row.type === 'change') {
        if (row.change_index !== group + 1) invalid();
        group = row.change_index;
      } else if (row.change_index !== group || group < 0) invalid();
      if (row.change_index >= all.total_changes) invalid();
    }
    if (group + 1 !== all.total_changes) invalid();
    return { ...all, has_more: false, next_cursor: null };
  }
}
