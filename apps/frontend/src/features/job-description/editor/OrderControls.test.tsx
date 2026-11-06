import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { OrderControls } from './OrderControls';

const items = [
  { id: 'a', label: '甲' },
  { id: 'b', label: '乙' },
  { id: 'c', label: '丙' },
  { id: 'd', label: '丁' },
] as const;

function simulateDisabledControlBlur() {
  // jsdom 不會像瀏覽器一樣，在控制停用後自動將焦點退回 body。
  document.body.tabIndex = -1;
  document.body.focus();
  document.body.removeAttribute('tabindex');
}

it('直接顯示移動按鈕，無須打開排序表單', () => {
  render(
    <OrderControls id="b" label="乙" items={items} disabled={false} onMove={vi.fn()} />,
  );
  expect(screen.getByRole('button', { name: '上移乙' })).toBeVisible();
  expect(screen.getByRole('button', { name: '下移乙' })).toBeVisible();
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
});

it('只有一筆時不顯示無效排序工具，新增第二筆後才顯示', () => {
  const props = { id: 'a', label: '甲', disabled: false, onMove: vi.fn() };
  const view = render(<OrderControls {...props} items={items.slice(0, 1)} />);
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  view.rerender(<OrderControls {...props} items={items.slice(0, 2)} />);
  expect(screen.getByRole('button', { name: '下移甲' })).toBeEnabled();
});

it.each([
  { id: 'b', label: '乙', direction: '上移', beforeId: 'a' },
  { id: 'b', label: '乙', direction: '下移', beforeId: 'd' },
  { id: 'c', label: '丙', direction: '下移', beforeId: null },
])(
  '$direction$label 使用 beforeId=$beforeId 移動一個位置',
  async ({ id, label, direction, beforeId }) => {
    const onMove = vi.fn().mockResolvedValue(true);
    const user = userEvent.setup();
    render(
      <OrderControls
        id={id}
        label={label}
        items={items}
        disabled={false}
        onMove={onMove}
      />,
    );
    await user.click(screen.getByRole('button', { name: `${direction}${label}` }));
    expect(onMove).toHaveBeenCalledExactlyOnceWith(beforeId);
    expect(screen.getByRole('status')).toHaveTextContent(`已調整「${label}」的位置。`);
  },
);

it.each([
  { id: 'a', label: '甲', upDisabled: true, downDisabled: false },
  { id: 'd', label: '丁', upDisabled: false, downDisabled: true },
])('首尾邊界停用無法移動的方向：$label', ({ id, label, upDisabled, downDisabled }) => {
  render(
    <OrderControls
      id={id}
      label={label}
      items={items}
      disabled={false}
      onMove={vi.fn()}
    />,
  );
  expect(screen.getByRole('button', { name: `上移${label}` })).toHaveProperty(
    'disabled',
    upDisabled,
  );
  expect(screen.getByRole('button', { name: `下移${label}` })).toHaveProperty(
    'disabled',
    downDisabled,
  );
});

it('停用期間不送出移動', () => {
  const onMove = vi.fn();
  render(<OrderControls id="b" label="乙" items={items} disabled onMove={onMove} />);
  const up = screen.getByRole('button', { name: '上移乙' });
  const down = screen.getByRole('button', { name: '下移乙' });
  expect(up).toBeDisabled();
  expect(down).toBeDisabled();
  fireEvent.click(up);
  fireEvent.click(down);
  expect(onMove).not.toHaveBeenCalled();
});

it('移動未確認前連點只送出一次，確認後恢復操作', async () => {
  let confirmMove: (value: boolean) => void = () => undefined;
  const result = new Promise<boolean>((resolve) => {
    confirmMove = resolve;
  });
  const onMove = vi.fn().mockReturnValue(result);
  const user = userEvent.setup();
  render(
    <OrderControls id="b" label="乙" items={items} disabled={false} onMove={onMove} />,
  );
  const up = screen.getByRole('button', { name: '上移乙' });
  const down = screen.getByRole('button', { name: '下移乙' });
  await user.dblClick(down);
  expect(onMove).toHaveBeenCalledExactlyOnceWith('d');
  expect(up).toBeDisabled();
  expect(down).toBeDisabled();
  expect(screen.getByRole('status')).toBeEmptyDOMElement();
  simulateDisabledControlBlur();
  expect(document.body).toHaveFocus();

  await act(async () => {
    confirmMove(true);
    await result;
  });
  expect(up).toBeEnabled();
  expect(down).toBeEnabled();
  expect(screen.getByRole('status')).toHaveTextContent('已調整「乙」的位置。');
  expect(down).toHaveFocus();
});

it.each([
  { direction: '上移', reordered: [items[1], items[0], items[2]], available: '下移' },
  { direction: '下移', reordered: [items[0], items[2], items[1]], available: '上移' },
])(
  '移到邊界後，$direction 改為聚焦另一個可用方向',
  async ({ direction, reordered, available }) => {
    let finish: (value: boolean) => void = () => undefined;
    const response = new Promise<boolean>((resolve) => {
      finish = resolve;
    });
    const props = { id: 'b', label: '乙', disabled: false, onMove: () => response };
    const view = render(<OrderControls {...props} items={items.slice(0, 3)} />);
    const user = userEvent.setup();
    const chosen = screen.getByRole('button', { name: `${direction}乙` });
    await user.click(chosen);
    simulateDisabledControlBlur();
    expect(document.body).toHaveFocus();
    view.rerender(<OrderControls {...props} items={reordered} />);

    await act(async () => {
      finish(true);
      await response;
    });
    expect(chosen).toBeDisabled();
    expect(screen.getByRole('button', { name: `${available}乙` })).toHaveFocus();
  },
);

it('移動期間使用者移到其他控制，完成後不搶回焦點', async () => {
  let finish: (value: boolean) => void = () => undefined;
  const response = new Promise<boolean>((resolve) => {
    finish = resolve;
  });
  render(
    <>
      <OrderControls
        id="b"
        label="乙"
        items={items}
        disabled={false}
        onMove={() => response}
      />
      <button type="button">其他操作</button>
    </>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '下移乙' }));
  const other = screen.getByRole('button', { name: '其他操作' });
  await user.click(other);
  await act(async () => {
    finish(true);
    await response;
  });
  expect(other).toHaveFocus();
});

it('原控制已離開文件時，不將焦點轉移到重新建立的排序控制', async () => {
  let finish: (value: boolean) => void = () => undefined;
  const response = new Promise<boolean>((resolve) => {
    finish = resolve;
  });
  const props = { id: 'a', label: '甲', disabled: false, onMove: () => response };
  const view = render(<OrderControls {...props} items={items} />);
  const user = userEvent.setup();
  const chosen = screen.getByRole('button', { name: '下移甲' });
  await user.click(chosen);
  simulateDisabledControlBlur();
  view.rerender(<OrderControls {...props} items={items.slice(0, 1)} />);
  view.rerender(<OrderControls {...props} items={items} />);
  expect(chosen.isConnected).toBe(false);

  await act(async () => {
    finish(true);
    await response;
  });
  expect(document.body).toHaveFocus();
});

it('移動失敗時保留錯誤提示並恢復操作', async () => {
  const onMove = vi.fn().mockRejectedValue(new Error('failed'));
  const user = userEvent.setup();
  render(
    <OrderControls id="b" label="乙" items={items} disabled={false} onMove={onMove} />,
  );
  await user.click(screen.getByRole('button', { name: '上移乙' }));
  expect(screen.getByRole('status')).toHaveTextContent('無法調整位置');
  expect(screen.getByRole('button', { name: '上移乙' })).toBeEnabled();
  expect(screen.getByRole('button', { name: '下移乙' })).toBeEnabled();
});
