import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { SafeMarkdown } from './SafeMarkdown';

test('renders headings, paragraphs and literal diff code without active HTML or URLs', () => {
  const markdown = [
    '## 來源差異',
    '',
    '保留段落與 **重點**。',
    '',
    '```diff',
    '- 舊內容',
    '+ <img src=x onerror=alert(1)>',
    '```',
    '',
    '<script>alert(1)</script>',
    '',
    '<iframe src="https://evil.example"></iframe>',
    '',
    '[外部連結](https://evil.example) [執行](javascript:alert%281%29)',
    '',
    '[相對連結](/api/change) <https://evil.example/path>',
    '',
    '![追蹤圖片](https://evil.example/pixel.png)',
  ].join('\n');
  const { container } = render(<SafeMarkdown markdown={markdown} />);
  expect(screen.getByRole('heading', { name: '來源差異' })).toBeVisible();
  expect(container.querySelector('strong')).toHaveTextContent('重點');
  expect(container.querySelector('pre code')?.textContent).toBe(
    '- 舊內容\n+ <img src=x onerror=alert(1)>\n',
  );
  expect(container.querySelector('script,iframe,img,a,[href],[src],[onerror]')).toBeNull();
  expect(screen.getByText(/外部連結/)).toBeVisible();
});

/** One entry per line of the first code block: its kind and its text, markers included. */
function diffLines(container: HTMLElement): [string, string][] {
  return [...container.querySelectorAll('[data-diff-line]')].map((line) => [
    line.getAttribute('data-diff-line') ?? '',
    line.textContent,
  ]);
}

test('a fenced diff marks every line as added, removed, hunk, file header or context, markers kept', () => {
  const markdown = [
    '```diff',
    '--- body_before',
    '+++ body_after',
    '@@ -1,3 +1,3 @@',
    ' 不變的一行',
    '-舊的一行',
    '+新的一行',
    '--- 破折號開頭的舊行',
    '\\ No newline at end of file',
    '```',
  ].join('\n');
  const { container } = render(<SafeMarkdown markdown={markdown} />);
  expect(diffLines(container)).toEqual([
    ['meta', '--- body_before'],
    ['meta', '+++ body_after'],
    ['hunk', '@@ -1,3 +1,3 @@'],
    ['context', ' 不變的一行'],
    ['del', '-舊的一行'],
    ['add', '+新的一行'],
    ['del', '--- 破折號開頭的舊行'],
    ['meta', '\\ No newline at end of file'],
  ]);
});

test('other code blocks stay plain text', () => {
  const { container } = render(<SafeMarkdown markdown={'```\n+ 看起來像新增\n```'} />);
  expect(container.querySelector('[data-diff-line]')).toBeNull();
  expect(container.querySelector('pre code')?.textContent).toBe('+ 看起來像新增\n');
});
