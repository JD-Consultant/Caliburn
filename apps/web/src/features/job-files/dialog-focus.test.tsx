import type { ReactNode } from 'react';
import { createTheme } from '@mui/material/styles';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { CreateJobFileDialog } from './CreateJobFileDialog';
import { RenameJobFileDialog } from './RenameJobFileDialog';

const clients: QueryClient[] = [];

function renderDialog(dialog: ReactNode) {
  const client = new QueryClient();
  clients.push(client);
  return render(<QueryClientProvider client={client}>{dialog}</QueryClientProvider>);
}

function finishEntering(): void {
  // Advance the real MUI transition at a chosen interaction boundary; no wall-clock wait.
  act(() => {
    vi.advanceTimersByTime(createTheme().transitions.duration.enteringScreen);
  });
}

beforeEach(() => {
  sessionStorage.clear();
  vi.useFakeTimers();
});
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.useRealTimers();
});

test('建立表單尚未操作時，轉場完成仍會定位名稱欄', () => {
  renderDialog(<CreateJobFileDialog onCreated={vi.fn()} onClose={vi.fn()} />);
  finishEntering();
  expect(screen.getByLabelText(/職務檔案名稱/)).toHaveFocus();
});

test('建立轉場在姓名輸入途中完成，不把後續字元輸入檔名', async () => {
  renderDialog(<CreateJobFileDialog onCreated={vi.fn()} onClose={vi.fn()} />);
  const name = screen.getByLabelText(/職務檔案名稱/);
  const employee = screen.getByLabelText(/受訪員工姓名/);
  fireEvent.change(name, { target: { value: '合成職務' } });
  act(() => employee.focus());
  fireEvent.change(employee, { target: { value: '合成' } });
  expect(employee).toHaveFocus();

  finishEntering();
  vi.useRealTimers();
  await userEvent.keyboard('員工');

  expect(name).toHaveValue('合成職務');
  expect(employee).toHaveValue('合成員工');
  expect(employee).toHaveFocus();
});

test('改名轉場完成不搶走使用者已選擇的返回按鈕焦點', () => {
  renderDialog(
    <RenameJobFileDialog
      file={{
        job_file_id: '20000000-0000-4000-8000-000000000002',
        display_name: '合成職務',
        employee_name: '合成員工',
        created_at: '2026-09-29T10:00:00Z',
        name_revision: 1,
      }}
      onClose={vi.fn()}
      onRefresh={vi.fn()}
    />,
  );
  const back = screen.getByRole('button', { name: '返回清單' });
  act(() => back.focus());
  finishEntering();
  expect(back).toHaveFocus();
});
