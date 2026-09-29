import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { App } from './App';

test('開發殼不把尚未實作的訪談宣稱為可使用', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Caliburn' })).toBeVisible();
  expect(screen.getByRole('heading', { name: '新架構開發中' })).toBeVisible();
  expect(screen.getByText(/尚未開放訪談與 JD 編輯/)).toBeVisible();
});
