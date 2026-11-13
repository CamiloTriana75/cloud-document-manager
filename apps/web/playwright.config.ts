import { defineConfig, devices } from '@playwright/test';

/** Puerto del dev server de E2E; `E2E_PORT` permite correrlos junto a otro `ng serve`. */
const port = Number(process.env['E2E_PORT'] ?? 4200);
const baseURL = `http://localhost:${port}`;

/**
 * Configuración de Playwright para pruebas E2E en Cloud Document Manager (CDM-50).
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env['CI'],
  retries: process.env['CI'] ? 2 : 0,
  workers: process.env['CI'] ? 1 : undefined,
  reporter: process.env['CI'] ? 'github' : 'list',
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `pnpm exec ng serve --port ${port}`,
    url: baseURL,
    reuseExistingServer: !process.env['CI'],
    timeout: 120 * 1000,
  },
});
