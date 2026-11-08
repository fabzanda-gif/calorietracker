import { expect, test, type Page } from "@playwright/test";
import type { HomeSummaryResponse } from "../lib/api/day";

// Real AuthProvider, Supabase SDK, AuthGate and UI; mocked network boundaries.
// These tests always run in CI without production accounts or secrets.
const user = {
  id: "00000000-0000-0000-0000-000000000001", aud: "authenticated",
  role: "authenticated", email: "test@sanosync.example",
  app_metadata: { provider: "email" }, user_metadata: { name: "Test" },
  created_at: "2026-01-01T00:00:00Z",
};
const accessToken = [
  { alg: "HS256", typ: "JWT" },
  { sub: user.id, exp: 4102444800, role: "authenticated", aud: "authenticated" },
].map((value) => Buffer.from(JSON.stringify(value)).toString("base64url")).join(".") + ".test-signature";

function summary(withMeal: boolean): HomeSummaryResponse {
  return {
    date: "2026-11-08", context: null,
    engagement: { state: "active", days_since_last_meal: 0 }, special_period: null,
    hero: { kind: "normal", title: "La tua giornata", message: "Tutto aggiornato", icon: "✓" },
    budget: { daily_budget_kcal: 2000, consumed_kcal: withMeal ? 300 : 0,
      available_kcal: withMeal ? 1700 : 2000, maintenance_kcal: 2200,
      protein_consumed_g: 20, protein_target_g: 100, protein_remaining_g: 80 },
    profile_goal: { goal_mode: "loss", goal_adjustment_kcal: 200, bmr: 1600,
      protein_target_g: 100, profile_complete_for_budget: true },
    latest_weight: null,
    meals: withMeal ? [{ id: "meal-1", meal_type: "Colazione", name: "Yogurt di prova", calories: 300 }] : [],
    activities: [], planned_today: [], planned_tomorrow: [],
    meta: { history_days_used: 0, ai_calls: 0, average_activity_kcal_7d: 0 },
  };
}

async function mockServices(page: Page) {
  let withMeal = true;
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/auth/v1/**", async (route) => {
    if (route.request().url().includes("/logout")) {
      await route.fulfill({ status: 204 });
      return;
    }
    await route.fulfill({ json: route.request().url().includes("/token") ? {
      access_token: accessToken, refresh_token: "test-refresh-token",
      token_type: "bearer", expires_in: 3600, user,
    } : user });
  });
  await page.route("http://localhost:8000/**", async (route) => {
    expect(route.request().headers().authorization).toBe(`Bearer ${accessToken}`);
    const path = new URL(route.request().url()).pathname;
    let json: unknown;
    if (path === "/profile") json = { id: user.id, metadata: user.user_metadata };
    else if (path === "/onboarding/status") json = { completed: true, preferred_days: [], priority_muscles: [] };
    else if (path.startsWith("/home-summary/")) json = summary(withMeal);
    else if (path === "/meals/meal-1" && route.request().method() === "DELETE") {
      withMeal = false;
      json = { deleted: true };
    } else if (path === "/weekly-schedule") json = { days: {}, items: [], week_start: "2026-11-02" };
    else if (path === "/progress/nutrition") json = { items: [], summary: {
      logged_days: 0, average_consumed_kcal: 0, days_within_budget: 0, days_with_budget: 0,
    } };
    else if (path === "/auth-events/login") json = { notified: true };
    else if (path === "/notifications/vapid-public-key") json = { public_key: "test" };
    else if (["/activities/planned", "/special-periods", "/weight"].includes(path)) json = { items: [], count: 0 };
    else throw new Error(`Missing API fixture: ${route.request().method()} ${path}`);
    await route.fulfill({ json });
  });
  return errors;
}

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Accedi", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Test");
  await expect(page.getByText("Yogurt di prova", { exact: true })).toBeVisible();
}

test("login and public legal pages remain accessible", async ({ page }) => {
  await mockServices(page);
  await page.goto("/");
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByRole("button", { name: "Accedi", exact: true })).toBeVisible();
  for (const path of ["/privacy", "/terms"]) {
    await page.goto(path);
    await expect(page.getByLabel("Password")).toHaveCount(0);
    await expect(page.locator("main")).toBeVisible();
  }
});

test("signed-in users can navigate the current primary areas", async ({ page }) => {
  const errors = await mockServices(page);
  await signIn(page);
  for (const path of ["/plan", "/food", "/insights", "/"]) {
    await page.locator(`a[href="${path}"]`).first().click();
    await expect(page).toHaveURL(new RegExp(path === "/" ? "/$" : `${path}$`));
    await expect(page.locator("main h1")).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("meal deletion updates the current home and survives reload", async ({ page }) => {
  const errors = await mockServices(page);
  await signIn(page);
  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Elimina", exact: true }).click();
  await expect(page.getByText("Yogurt di prova", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Test");
  await expect(page.getByRole("heading", { name: "Giornata sotto controllo", exact: true })).toBeVisible();
  await expect(page.getByText("Yogurt di prova", { exact: true })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("logout removes access to authenticated pages", async ({ page }) => {
  await mockServices(page);
  await signIn(page);
  await page.getByRole("button", { name: /Esci/i }).click();
  await expect(page.getByLabel("Password")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Password")).toBeVisible();
});
