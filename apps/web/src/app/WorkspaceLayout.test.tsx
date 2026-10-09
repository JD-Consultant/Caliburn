/** Responsive pane semantics preserve mounted drafts and background subscriptions. */
import { useEffect, useState } from 'react';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { WorkspaceLayout } from './WorkspaceLayout';

function mediaQuery(initial: boolean) {
  let matches = initial;
  const listeners = new Set<() => void>();
  vi.stubGlobal('matchMedia', (query: string) => ({
    media: query,
    get matches() {
      return matches;
    },
    addEventListener: (_event: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_event: string, listener: () => void) => listeners.delete(listener),
  }));
  return (next: boolean) =>
    act(() => {
      matches = next;
      listeners.forEach((listener) => listener());
    });
}

afterEach(() => vi.unstubAllGlobals());

test('narrow tabs label panels and keyboard switching and resizing preserve mounted drafts', async () => {
  const resize = mediaQuery(true);
  const mount = vi.fn();
  const unmount = vi.fn();
  function Draft() {
    const [value, setValue] = useState('');
    useEffect(() => {
      mount();
      return unmount;
    }, []);
    return (
      <input aria-label="草稿" value={value} onChange={(event) => setValue(event.target.value)} />
    );
  }
  render(<WorkspaceLayout bar={null} interview={<Draft />} document={<p>JD正文</p>} />);
  const panel = screen.getByRole('tabpanel', { name: '訪談' });
  expect(panel).toHaveAttribute('aria-labelledby', 'tab-interview');
  expect(screen.getByRole('tab', { name: '訪談' })).toHaveAttribute('aria-controls', panel.id);
  const draft = screen.getByRole('textbox', { name: '草稿' });
  await userEvent.type(draft, '未送出');
  screen.getByRole('tab', { name: '訪談' }).focus();
  await userEvent.keyboard('{ArrowRight}{Enter}');
  expect(screen.getByRole('tabpanel', { name: 'JD' })).toBeVisible();
  expect(draft).not.toBeVisible();
  expect(draft).toHaveValue('未送出');
  expect(mount).toHaveBeenCalledTimes(1);
  expect(unmount).not.toHaveBeenCalled();
  resize(false);
  expect(screen.getByRole('region', { name: '訪談區' })).not.toHaveAttribute('aria-labelledby');
  expect(screen.getByRole('region', { name: '職務說明書區' })).not.toHaveAttribute(
    'aria-labelledby',
  );
  expect(draft).toBeVisible();
  expect(unmount).not.toHaveBeenCalled();
  resize(true);
  expect(screen.getByRole('tabpanel', { name: 'JD' })).toBeVisible();
  await userEvent.click(screen.getByRole('tab', { name: '訪談' }));
  expect(draft).toBeVisible();
  expect(draft).toHaveValue('未送出');
  expect(unmount).not.toHaveBeenCalled();
});
