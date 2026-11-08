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
  const activity = { id: "activity-1", date: new Date().toISOString().slice(0, 10),
    activity_name: "Corsa del parco", activity_type: "Corsa", burned_calories: 300,
    duration_seconds: 1800, distance_meters: 5000, route_points: [], series_points: [] };
  let withMeal = true;
  const routine: Record<string, string> = { monday: "home" };
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
    } else if (path === "/weekly-schedule") {
      if (route.request().method() === "PUT") {
        const labels = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
        for (const day of route.request().postDataJSON().days) routine[labels[day.day_of_week - 1]] = day.context;
      }
      json = { days: routine, items: [], week_start: "2026-11-02" };
    }
    else if (path === "/progress/nutrition") json = { items: [], summary: {
      logged_days: 0, average_consumed_kcal: 0, days_within_budget: 0, days_with_budget: 0,
    } };
    else if (path === "/activities/overview") json = { items: [activity], energy_days: [], summary: {} };
    else if (path === "/activities/range") json = { items: [activity], count: 1 };
    else if (path === "/activities/comment") json = { comment: "Attività registrata.", source: "fallback" };
    else if (path === "/activities/training-plans" || path === "/strength/plans") json = { items: [], count: 0 };
    else if (path.startsWith("/activities/movement/")) json = { total_steps: 0, net_daily_steps: 0, estimated_training_steps: 0, applied_step_offset: 0, step_calories: 0 };
    else if (path === "/coach/reconcile") json = { policy: "balanced", load_events: [], adjustments: [], history: [], summary: { events: 0, proposed: 0, auto_applied: 0 } };
    else if (path === "/coach/preferences") json = { priority: "balanced" };
    else if (path === "/weight/latest") json = { item: null };
    else if (path.endsWith("/status") && path.startsWith("/integrations/")) json = { connected: false, configured: false };
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
  for (const path of ["/activities", "/food", "/insights", "/"]) {
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


for (const viewport of [{ name: "desktop", width: 1280, height: 900 }, { name: "mobile", width: 390, height: 844 }]) {
  test(`activity recap and nested programs on ${viewport.name}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    const errors = await mockServices(page);
    const futureCalls: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/activities/planned")) futureCalls.push(request.url());
    });
    await signIn(page);
    await page.locator('a[href="/activities"]:visible').first().click();
    await expect(page.getByRole("heading", { name: "Attività", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Ultimi 30 giorni", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Attività registrate", exact: true })).toBeVisible();
    await expect(page.getByText("Corsa del parco", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("tab", { name: "Palestra", exact: true })).toHaveCount(0);
    await expect(page.locator('a[href="/plan"]')).toHaveCount(0);
    expect(futureCalls).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`activity-recap-${viewport.name}.png`), fullPage: false });
    await page.getByRole("link", { name: "Programmi di allenamento →", exact: true }).click();
    await expect(page).toHaveURL(/\/activities\/programs$/);
    await expect(page.getByRole("heading", { name: "Programmi", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Corsa", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: "Attività registrate", exact: true })).toHaveCount(0);
    await page.getByRole("tab", { name: "Palestra", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Programma forza", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Palestra", exact: true })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("tab", { name: "Palestra", exact: true }).press("ArrowLeft");
    await expect(page.getByRole("tab", { name: "Corsa", exact: true })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("tab", { name: "Corsa", exact: true }).press("ArrowRight");
    await expect(page.getByRole("tab", { name: "Palestra", exact: true })).toHaveAttribute("aria-selected", "true");
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`activity-programs-${viewport.name}.png`), fullPage: false });
    await page.getByRole("link", { name: "← Attività", exact: true }).click();
    await expect(page).toHaveURL(/\/activities$/);
    expect(errors).toEqual([]);
  });
}

test("old Plan links redirect to Activities", async ({ page }) => {
  await mockServices(page);
  await signIn(page);
  await page.goto("/plan");
  await expect(page).toHaveURL(/\/activities$/);
  await expect(page.getByRole("heading", { name: "Attività", exact: true })).toBeVisible();
});

test("weekly exceptions and special periods stay in the profile", async ({ page }) => {
  const errors = await mockServices(page);
  await signIn(page);
  await page.goto("/profile#planning-settings");
  const weekly = page.locator("#planning-settings");
  await weekly.locator("summary").click();
  await weekly.getByLabel("Lunedì", { exact: true }).selectOption("office");
  await weekly.getByRole("button", { name: "Salva questa settimana", exact: true }).click();
  await expect(weekly.getByRole("status")).toContainText("Routine della settimana aggiornata");
  await expect(page.locator("#periodi-speciali")).toBeVisible();
  await page.reload();
  await weekly.locator("summary").click();
  await expect(weekly.getByLabel("Lunedì", { exact: true })).toHaveValue("office");
  expect(errors).toEqual([]);
});
