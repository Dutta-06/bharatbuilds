// Optional browser integration check against the real SAM/API backend.
// Install with: npm install --no-save --package-lock=false playwright
import { chromium } from 'playwright';
import assert from 'node:assert/strict';

const browser = await chromium.launch({ headless: true, channel: process.platform === 'win32' ? 'msedge' : 'chromium' });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
try {
  await page.goto(process.env.TIDEWISE_DASHBOARD_URL || 'http://127.0.0.1:5173/#/operations');
  await page.getByRole('heading', { name: 'Power & Operations', exact: true }).waitFor();
  const operate = async (name) => {
    await page.getByRole('button', { name, exact: true }).click();
    await page.getByText('Facility state and scheduling decisions persisted.', { exact: true }).waitFor({ timeout: 120000 });
  };
  await operate('Reset demo');
  await operate('Grid failure');
  await operate('Activate generator');
  await page.getByText('Generator backup', { exact: true }).waitFor();
  assert.match(await page.locator('.readout').filter({ hasText: 'Post-decision demand' }).innerText(), /27\s*kW/);
  assert.match(await page.locator('.readout').filter({ hasText: 'Deferred IT demand' }).innerText(), /28\s*kW/);
  assert.match(await page.getByRole('row').filter({ hasText: 'ML Training' }).innerText(), /CHECKPOINT_AND_DEFER/);
  assert.match(await page.getByRole('row').filter({ hasText: 'ETL' }).innerText(), /CONTINUE/);
  await operate('Advance 90 minutes');
  assert.match(await page.locator('.readout').filter({ hasText: 'Generator-period demand deferred' }).innerText(), /42\s*kWh/);
  await operate('Restore grid');
  await page.getByText('Grid recovery', { exact: true }).waitFor();
  await operate('Confirm stable grid (+30s)');
  assert.match(await page.getByRole('row').filter({ hasText: 'ML Training' }).innerText(), /running/i);
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.getByRole('heading', { name: 'Power & Operations', exact: true }).isVisible());
  await page.getByRole('link', { name: 'Queue', exact: true }).click();
  await page.getByRole('heading', { name: 'Queue', exact: true }).waitFor();
  await page.locator('a[href="#/jobs/dg-demo-training"]:visible').first().click();
  await page.getByRole('heading', { name: 'ML Training', exact: true }).waitFor();
  assert.match(await page.locator('main').innerText(), /SIMULATED/);
  await page.getByRole('link', { name: 'Surface', exact: true }).click();
  await page.waitForTimeout(1000);
  assert.ok(!page.url().endsWith('/operations'));
  assert.deepEqual(errors, []);
  // Verify the displayed API error state using a deliberate transport failure.
  await page.route('**/facilities*', (route) => route.abort());
  await page.getByRole('link', { name: 'Power & Operations', exact: true }).click();
  await page.getByRole('alert').waitFor();
  assert.match(await page.getByRole('alert').innerText(), /Can't reach the Tidewise API/);
  console.log('PASS: real API-backed generator/recovery demo, 55 -> 27 kW, 42 kWh, mobile layout, queue/job navigation and API error feedback');
} finally {
  await browser.close();
}
