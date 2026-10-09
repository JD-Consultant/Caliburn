import { beforeEach, expect, test } from 'vitest';
import { pendingCreation, pendingRename } from './job-file-commands';

const fileId = '10000000-0000-4000-8000-000000000001';
const commandId = '20000000-0000-4000-8000-000000000002';
const nextId = '30000000-0000-4000-8000-000000000003';
const creation = { command_id: commandId, display_name: '合成職務', employee_name: '合成員工' };
const rename = { command_id: commandId, expected_name_revision: 1, display_name: '合成新名稱' };

beforeEach(() => sessionStorage.clear());

test('建立 ACK 只移除相符原命令；缺少紀錄不再授權畫面回呼', () => {
  expect(pendingCreation.acknowledge(creation)).toBe('changed');
  pendingCreation.retain(creation);
  expect(pendingCreation.acknowledge(creation)).toBe('cleared');
  expect(pendingCreation.read()).toBeNull();
  expect(pendingCreation.acknowledge(creation)).toBe('changed');
});

test.each([
  { ...creation, command_id: nextId },
  { ...creation, display_name: '同 ID 的不同職務' },
  { ...creation, employee_name: '同 ID 的不同員工' },
])('建立 ACK 不移除不同識別或不同 intent：%j', (next) => {
  pendingCreation.retain(next);
  expect(pendingCreation.acknowledge(creation)).toBe('changed');
  expect(pendingCreation.read()).toEqual(next);
});

test('改名 ACK 只移除相符檔案命令；確認刪檔後的晚到 ACK 不授權回呼', () => {
  pendingRename(fileId).retain(rename);
  expect(pendingRename(nextId).acknowledge(rename)).toBe('changed');
  expect(pendingRename(fileId).read()).toEqual(rename);
  expect(pendingRename(fileId).acknowledge(rename)).toBe('cleared');
  expect(pendingRename(fileId).read()).toBeNull();
  pendingRename(fileId).retain(rename);
  pendingRename(fileId).clear();
  expect(pendingRename(fileId).acknowledge(rename)).toBe('changed');
});

test.each([
  { ...rename, command_id: nextId },
  { ...rename, display_name: '同 ID 的不同名稱' },
  { ...rename, expected_name_revision: 2 },
])('改名 ACK 不移除不同識別或不同 intent：%j', (next) => {
  pendingRename(fileId).retain(next);
  expect(pendingRename(fileId).acknowledge(rename)).toBe('changed');
  expect(pendingRename(fileId).read()).toEqual(next);
});

test('建立與改名的原意比對不受 JSON 欄位順序影響', () => {
  pendingCreation.retain({
    employee_name: creation.employee_name,
    display_name: creation.display_name,
    command_id: creation.command_id,
  });
  expect(pendingCreation.acknowledge(creation)).toBe('cleared');
  pendingRename(fileId).retain({
    display_name: rename.display_name,
    command_id: rename.command_id,
    expected_name_revision: rename.expected_name_revision,
  });
  expect(pendingRename(fileId).acknowledge(rename)).toBe('cleared');
});
