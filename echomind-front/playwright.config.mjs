import { defineConfig } from "@playwright/test";

const portal = "http://127.0.0.1:3019";
const fixture = "http://127.0.0.1:4105";

export default defineConfig({
  testDir: "./test/e2e",
  testMatch: "**/*.e2e.mjs",
  outputDir: ".next/e2e-results",
  workers: 1,
  use: { baseURL: portal },
  webServer: [
    {
      command: "node test/fixtures/chat-server.mjs",
      url: `${fixture}/public/ds04-fixture`,
    },
    {
      command: "node node_modules/next/dist/bin/next dev --webpack --hostname 127.0.0.1 --port 3019",
      url: `${portal}/p/ds04-fixture`,
      env: {
        NEXT_PUBLIC_API_URL: fixture,
        NEXT_PUBLIC_SUPABASE_URL: fixture,
        NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_local_fixture_only",
        NEXT_TELEMETRY_DISABLED: "1",
      },
    },
  ],
});
