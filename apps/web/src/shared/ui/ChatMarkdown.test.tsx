import { render } from '@testing-library/react';
import { expect, test } from 'vitest';
import { ChatMarkdown } from './ChatMarkdown';

test('formats bold, lists and paragraphs of a consultant message', () => {
  const { container } = render(
    <ChatMarkdown markdown={'先確認兩件事：\n\n**1.** 站會\n\n- 優先序\n- 預算'} />,
  );
  expect(container.querySelector('strong')).toHaveTextContent('1.');
  expect([...container.querySelectorAll('li')].map((item) => item.textContent)).toEqual([
    '優先序',
    '預算',
  ]);
  expect(container.textContent).not.toContain('**');
});

test('raw HTML stays literal text and never becomes an element', () => {
  const original = '<img src=x onerror="alert(1)">';
  const { container } = render(<ChatMarkdown markdown={`${original}\n\n請說明工作。`} />);
  expect(container.textContent).toContain(original);
  expect(container.querySelector('img,script,iframe')).toBeNull();
});

test('links do not navigate and remote images never load', () => {
  const { container } = render(
    <ChatMarkdown
      markdown={'[說明](https://evil.example/a) ![追蹤](https://evil.example/p.png)'}
    />,
  );
  expect(container.querySelector('a,img,[href],[src]')).toBeNull();
  expect(container.textContent).toContain('說明（https://evil.example/a）');
  expect(container.textContent).toContain('追蹤');
});

test('headings become bold paragraphs, not a document outline', () => {
  const { container } = render(<ChatMarkdown markdown={'# 大標\n\n內文'} />);
  expect(container.querySelector('h1,h2,h3')).toBeNull();
  expect(container.querySelector('p strong')).toHaveTextContent('大標');
});
