const { test, expect } = require('@playwright/test');

test('has title', async ({ page }) => {
  await page.setContent('<title>Playwright</title><h1>Hello</h1>');
  await expect(page).toHaveTitle('Playwright');
});
