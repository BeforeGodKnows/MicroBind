import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  timeout: 60000,
  workers: 1,
  reporter: [
    ["list"],
    ["json", { outputFile: "../out/validation/browser-tests.json" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:4173",
    viewport: { width: 1440, height: 1000 },
    launchOptions: {
      executablePath: process.env.MICROBIND_CHROMIUM || undefined,
    },
    trace: "retain-on-failure",
  },
});
