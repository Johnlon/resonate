import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
});

test('app shell renders — side panel and graph grid are populated', async ({ page }) => {
  await expect(page.locator('#side fieldset').first()).toBeVisible();
  await expect(page.locator('#ggrid .gpanel').first()).toBeVisible();
  await expect(page.locator('#stat')).not.toBeEmpty();
});

test('in-browser self-test passes all three physics gates', async ({ page }) => {
  const logs = [];
  page.on('console', msg => logs.push(msg.text()));
  await page.goto('/');
  await page.waitForFunction(() => window._selfTestDone === true, { timeout: 5000 })
    .catch(() => {});
  const selfTest = logs.find(l => l.includes('[Resonate self-test]'));
  const gate1 = logs.find(l => l.includes('GATE1'));
  const gate2 = logs.find(l => l.includes('GATE2'));
  const gate3 = logs.find(l => l.includes('GATE3'));
  expect(gate1).toMatch(/PASS/);
  expect(gate2).toMatch(/PASS/);
  expect(gate3).toMatch(/PASS/);
});

test('preset selector loads a different driver and re-renders', async ({ page }) => {
  await page.locator('text=Edit ✎').click();
  await page.locator('#preset').selectOption('Dayton DCS205-4 8" sub');
  // Fs input should now show 28.8 Hz (the DCS205 resonant frequency)
  await expect(page.locator('input[data-bind="Fs"]')).toHaveValue(/28/);
});

test('box type change to sealed re-renders enclosure panel', async ({ page }) => {
  await page.locator('#boxtype').selectOption('sealed');
  await expect(page.locator('#side')).toContainText('Qtc');
});

test('box type change to vented shows vent controls', async ({ page }) => {
  await page.locator('#boxtype').selectOption('vented');
  await expect(page.locator('#side')).toContainText('Vent diameter');
  await expect(page.locator('#side')).toContainText('Fb');
});

test('share link encodes state in URL hash', async ({ page }) => {
  await page.locator('#btnShare').click();
  await expect(page).toHaveURL(/#s=/);
});

test('engine module exports are accessible from the page', async ({ page }) => {
  const result = await page.evaluate(async () => {
    const { deriveDriver, RHO, C } = await import('/src/core/index.js');
    const d = deriveDriver({ Fs:37, Qts:0.38, Qes:0.40, Qms:7.0,
                             Vas:0.030, Sd:0.0133, Re:5.6, Le:0.7e-3,
                             Xmax:0.005, Pe:60, Z:8 });
    return { Bl: +d.Bl.toFixed(4), RHO };
  });
  expect(result.RHO).toBe(1.184);
  expect(result.Bl).toBeGreaterThan(5);
});
