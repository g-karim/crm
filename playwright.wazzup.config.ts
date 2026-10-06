import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { loadWazzupFixture } from "./frontend/tests/browser/wazzup-local-fixture";

const fixture = loadWazzupFixture();

// The backend runner owns the isolated site, database, worker and HTTP servers.
// This project never starts against the developer's bench by default.
export default defineConfig({
  testDir: "./frontend/tests/browser",
  testMatch: /wazzup-local\.spec\.ts/,
  workers: 1,
  retries: 0,
  timeout: 180000,
  expect: { timeout: 15000 },
  reporter: "list",
  preserveOutput: "always",
  outputDir: path.join(
    process.env.WAZZUP_E2E_ARTIFACTS || "/tmp/wazzup-local-playwright",
    "playwright",
  ),
  use: {
    ...devices["Desktop Chrome"],
    baseURL: fixture.base_url,
    viewport: { width: 1440, height: 1000 },
    actionTimeout: 15000,
    navigationTimeout: 30000,
    serviceWorkers: "block",
    // The complete app imports telemetry code even when telemetry is disabled.
    // Keep browser DNS offline while allowing only the runner's loopback hosts.
    launchOptions: {
      args: [
        "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost",
        "--no-proxy-server",
        "--disable-background-networking",
      ],
    },
    // Authentication is real. Do not record the synthetic credentials or grants.
    trace: "off",
    video: "off",
    screenshot: "off",
  },
});
