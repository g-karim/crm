import { defineConfig, devices } from "@playwright/test";

// Real Vue controls with mocked RPC, separate from authenticated CRM E2E tests.
export default defineConfig({
  testDir: "./frontend/tests/browser",
  testMatch: /messenger-settings\.spec\.ts/,
  workers: 1,
  retries: 0,
  timeout: 60000,
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:4186",
    viewport: { width: 1280, height: 900 },
    screenshot: "only-on-failure",
    serviceWorkers: "block",
  },
  webServer: {
    command: "cd frontend && yarn vite --config tests/browser/vite.config.js",
    url: "http://127.0.0.1:4186/tests/browser/messenger-settings.html",
    reuseExistingServer: false,
    timeout: 60000,
  },
});
