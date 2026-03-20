import { test, expect } from "@playwright/test";

/** dynamic import + R3F 청크 로드 여유 */
const UI_READY_MS = 60_000;

test.describe("God View (Phase 5.4)", () => {
  test("페이지 로드 및 세계 생성 UI", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /Organic4D/ })
    ).toBeVisible({ timeout: UI_READY_MS });
    await expect(
      page.getByRole("button", { name: "세계 생성" })
    ).toBeVisible({ timeout: UI_READY_MS });
    await expect(
      page.getByRole("button", { name: "실행 (WebSocket 스트림)" })
    ).toBeVisible({ timeout: UI_READY_MS });
  });

  test("3D 캔버스 또는 폴백(헤드리스 WebGL)", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("button", { name: "세계 생성" })
    ).toBeVisible({ timeout: UI_READY_MS });
    await expect(
      page.locator("canvas").or(page.getByTestId("r3f-scene-fallback"))
    ).toBeVisible({ timeout: UI_READY_MS });
  });
});
