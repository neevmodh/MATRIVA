import { defineConfig } from "@playwright/test";

if (!process.env.SMOKE_WEB_URL || !process.env.SMOKE_API_URL) {
  throw new Error("Run through python scripts/docker_smoke.py --browser");
}

export default defineConfig({
  testDir: "./tests/production",
  workers: 1,
  timeout: 60_000,
  use: { baseURL: process.env.SMOKE_WEB_URL, trace: "retain-on-failure" },
});
