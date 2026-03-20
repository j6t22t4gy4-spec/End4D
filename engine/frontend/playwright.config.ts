import { defineConfig, devices } from "@playwright/test";

const isCI = !!process.env.CI;
/** 로컬에서 3000 점유 시 충돌 방지. `PW_PORT=3000 npm run test:e2e` 로 기존 dev 재사용 가능 */
const PW_PORT = process.env.PW_PORT ?? "3333";
const baseURL = `http://localhost:${PW_PORT}`;

/**
 * Organic4D God View E2E
 * - 로컬: 기본 포트 {PW_PORT} 에서 dev 자동 기동 (또는 `PW_PORT=3000` + 이미 `npm run dev` 실행 시 재사용)
 * - CI: `build && start` 동일 포트
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  workers: isCI ? 1 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    /* 헤드리스 Chromium에서 WebGL 실패 완화 (Three.js / R3F) */
    launchOptions: {
      args: [
        "--ignore-gpu-blocklist",
        "--enable-gpu-rasterization",
        "--disable-dev-shm-usage",
      ],
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: isCI
    ? {
        command: `npm run build && npx next start -p ${PW_PORT}`,
        url: baseURL,
        reuseExistingServer: false,
        timeout: 300_000,
      }
    : {
        command: `npm run dev -- -p ${PW_PORT}`,
        url: baseURL,
        reuseExistingServer: true,
        timeout: 180_000,
      },
});
