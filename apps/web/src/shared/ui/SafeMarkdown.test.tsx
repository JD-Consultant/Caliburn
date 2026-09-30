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
