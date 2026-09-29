import { expect, test } from 'vitest';
import { detailChanges, makeDetailDraft } from './task-draft';

test('成果與要求各自比對：保留 ID、只傳變動、移除不重建其他明細', () => {
  const original = [
    { detail_id: 'a', text: '原成果' },
    { detail_id: 'b', text: '保留成果' },
  ];
  const rows = makeDetailDraft(original);
  expect(detailChanges(original, rows, 'outcome')).toEqual([]);
  expect(
    detailChanges(
      original,
      [
        { key: 'a', detailId: 'a', text: '新成果' },
        { key: 'new', text: '附加成果' },
      ],
      'outcome',
    ),
  ).toEqual([
    { action: 'remove_detail', detail_id: 'b' },
    { action: 'revise_detail', detail_id: 'a', text: '新成果' },
    { action: 'add_detail', kind: 'outcome', text: '附加成果' },
  ]);
  expect(detailChanges([], [{ key: 'new', text: '完成條件' }], 'requirement')).toEqual([
    { action: 'add_detail', kind: 'requirement', text: '完成條件' },
  ]);
});
