import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./frontend/tests/browser",
  testMatch: /messenger-(?:bubbles|voice)\.spec\.ts/,
  workers: 1,
  retries: 0,
  reporter: "line",
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:4187" },
  webServer: {
    cwd: "./frontend",
    command:
      "node node_modules/vite/bin/vite.js --config tests/browser/vite.bubbles.config.js",
    url: "http://127.0.0.1:4187/tests/browser/messenger-bubbles.html",
    reuseExistingServer: false,
    timeout: 60000,
  },
});
