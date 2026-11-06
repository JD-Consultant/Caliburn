import { test, expect } from './fixtures';

for (const width of [1440, 390, 320]) {
  test(`正式新 Workspace 的 Memory 空狀態與鍵盤焦點（${width}px）`, async ({
    page,
    synthetic,
  }, testInfo) => {
    const workspace = await synthetic.createWorkspace('Memory 空發布驗證');
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({
      reducedMotion: 'reduce',
      colorScheme: width === 390 ? 'dark' : 'light',
    });
    await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
    const opener = page.getByRole('button', { name: '工作記憶', exact: true });
    await opener.focus();
    await page.keyboard.press('Enter');
    const dialog = page.getByRole('dialog', { name: '目前已發布的 Memory' });
    await expect(dialog.getByText('尚無已發布的 Memory。')).toBeVisible();
    await expect(dialog.getByText(/正在整理|整理失敗/)).toHaveCount(0);
    const dimensions = await page.evaluate(() => ({
      width: window.innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.width);
    await testInfo.attach(`memory-empty-${width}`, {
      body: await page.screenshot({ animations: 'disabled' }),
      contentType: 'image/png',
    });
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(opener).toBeFocused();
    if (width === 320) {
      await page.emulateMedia({ forcedColors: 'active' });
      await opener.click();
      await expect(
        page.getByRole('dialog').getByText('尚無已發布的 Memory。'),
      ).toBeVisible();
      await page.getByRole('button', { name: '關閉', exact: true }).click();
      await expect(opener).toBeFocused();
    }
  });
}
